"""Tool: Ingest source code for analysis."""

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from git import GitCommandError, Repo

from arcade_agent.tools.registry import tool


@dataclass
class IngestedRepo:
    """Result of ingesting a repository."""

    path: Path
    name: str
    version: str
    is_temp: bool = False
    source_files: list[Path] = field(default_factory=list)
    language: str | None = None
    versions: list[str] = field(default_factory=list)

    def cleanup(self) -> None:
        """Remove temporary directory if applicable."""
        if self.is_temp and self.path.exists():
            shutil.rmtree(self.path)


# Language extension mapping
_LANG_EXTENSIONS: dict[str, list[str]] = {
    "java": [".java"],
    "python": [".py"],
    "typescript": [".ts", ".tsx", ".js", ".jsx"],
    "c": [".c", ".h", ".cpp", ".hpp", ".cc", ".cxx"],
}

# Reverse mapping
_EXT_TO_LANG: dict[str, str] = {}
for lang, exts in _LANG_EXTENSIONS.items():
    for ext in exts:
        _EXT_TO_LANG[ext] = lang


def _detect_language(path: Path) -> str | None:
    """Auto-detect the primary language from file extensions."""
    ext_counts: dict[str, int] = {}
    for f in path.rglob("*"):
        if f.is_file() and f.suffix in _EXT_TO_LANG:
            ext_counts[f.suffix] = ext_counts.get(f.suffix, 0) + 1

    if not ext_counts:
        return None

    best_ext = max(ext_counts, key=ext_counts.get)  # type: ignore[arg-type]
    return _EXT_TO_LANG.get(best_ext)


# Well-known source root directories (tried in order)
_SOURCE_ROOTS = [
    "src/main/java",        # Maven/Gradle Java
    "src/main/kotlin",      # Maven/Gradle Kotlin
    "src/main/scala",       # Maven/Gradle Scala
    "src/main",             # Maven generic
    "src",                  # Generic
    "lib",                  # Ruby, some C projects
    "app",                  # Rails, some Python
]

# Directories to exclude
_EXCLUDE_DIRS = {
    "src/test",
    "src/tests",
    "test",
    "tests",
    "node_modules",
    "vendor",
    "third_party",
    "third-party",
    "thirdparty",
    "external",
    "ext-tools",
    "build",
    "dist",
    "target",
    ".git",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "env",
}


def _detect_source_root(path: Path, language: str | None = None) -> Path:
    """Detect the main source root directory.

    Checks for well-known source root patterns (e.g., src/main/java for Maven).
    Falls back to the project root.
    """
    for candidate in _SOURCE_ROOTS:
        root = path / candidate
        if root.is_dir():
            return root
    return path


def _should_exclude(file_path: Path, root: Path) -> bool:
    """Check if a file should be excluded (test, vendored, build artifacts)."""
    try:
        rel = file_path.relative_to(root)
    except ValueError:
        return False

    parts = rel.parts
    for i in range(len(parts)):
        subpath = "/".join(parts[: i + 1])
        if subpath in _EXCLUDE_DIRS:
            return True
        # Also check just the directory name
        if parts[i] in _EXCLUDE_DIRS:
            return True
    return False


def _discover_files(
    path: Path,
    language: str | None = None,
    exclude_tests: bool = True,
    source_root: Path | None = None,
) -> list[Path]:
    """Discover source files for the given language.

    Args:
        path: Project root directory.
        language: Language to filter for.
        exclude_tests: Whether to exclude test/vendor directories.
        source_root: Override source root (search here instead of path).
    """
    search_path = source_root if source_root else path

    if language and language in _LANG_EXTENSIONS:
        extensions = _LANG_EXTENSIONS[language]
    else:
        extensions = list(_EXT_TO_LANG.keys())

    files = []
    for ext in extensions:
        for f in sorted(search_path.rglob(f"*{ext}")):
            if exclude_tests and _should_exclude(f, path):
                continue
            files.append(f)
    return files


def _detect_version(repo: Repo) -> str:
    """Detect the latest version tag from a repo."""
    try:
        tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
        if tags:
            return str(tags[-1])
    except Exception:
        pass
    return "HEAD"


def _detect_versions(repo: Repo) -> list[str]:
    """Detect all version tags from a repo."""
    try:
        tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
        return [str(t) for t in tags]
    except Exception:
        return []


def _repo_name_from_url(url: str) -> str:
    """Extract repository name from a URL."""
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


@tool(
    name="ingest",
    description="Prepare source code for analysis. Accepts git URL or local path. "
    "Auto-detects source roots and filters out test/vendored code.",
)
def ingest(
    source: str,
    language: str | None = None,
    work_dir: str | None = None,
    exclude_tests: bool = True,
    source_root: str | None = None,
) -> IngestedRepo:
    """Ingest a repository from a URL or local path.

    Args:
        source: Git repo URL or local directory path.
        language: Override language detection (java, python, typescript, c).
        work_dir: Directory to clone into. Uses temp dir if None.
        exclude_tests: Exclude test/vendor/build directories (default: True).
        source_root: Override source root (e.g., 'src/main/java'). Auto-detected if None.

    Returns:
        IngestedRepo with path, name, version, and source file list.
    """
    source_path = Path(source)
    sr = Path(source_root) if source_root else None
    if source_path.is_dir():
        return _ingest_local(source_path, language, exclude_tests, sr)
    return _clone_and_ingest(
        source, language, Path(work_dir) if work_dir else None, exclude_tests, sr,
    )


def _ingest_local(
    path: Path,
    language: str | None = None,
    exclude_tests: bool = True,
    source_root: Path | None = None,
) -> IngestedRepo:
    """Ingest a local directory."""
    name = path.name
    version = "local"
    versions: list[str] = []

    try:
        repo = Repo(path)
        version = _detect_version(repo)
        versions = _detect_versions(repo)
    except Exception:
        pass

    if not language:
        language = _detect_language(path)

    # Auto-detect source root if not provided
    effective_root = source_root
    if effective_root is None and exclude_tests:
        detected = _detect_source_root(path, language)
        if detected != path:
            effective_root = detected

    source_files = _discover_files(path, language, exclude_tests, effective_root)

    return IngestedRepo(
        path=effective_root if effective_root else path,
        name=name,
        version=version,
        is_temp=False,
        source_files=source_files,
        language=language,
        versions=versions,
    )


def _clone_and_ingest(
    url: str,
    language: str | None = None,
    work_dir: Path | None = None,
    exclude_tests: bool = True,
    source_root: Path | None = None,
) -> IngestedRepo:
    """Clone a remote repo and ingest it."""
    name = _repo_name_from_url(url)

    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="arcade_agent_"))
    clone_path = work_dir / name

    repo = Repo.clone_from(url, clone_path, depth=1)

    version = _detect_version(repo)
    versions = _detect_versions(repo)

    if version != "HEAD":
        try:
            repo.git.checkout(version)
        except GitCommandError:
            pass

    if not language:
        language = _detect_language(clone_path)

    effective_root = source_root
    if effective_root is None and exclude_tests:
        detected = _detect_source_root(clone_path, language)
        if detected != clone_path:
            effective_root = detected

    source_files = _discover_files(clone_path, language, exclude_tests, effective_root)

    return IngestedRepo(
        path=effective_root if effective_root else clone_path,
        name=name,
        version=version,
        is_temp=True,
        source_files=source_files,
        language=language,
        versions=versions,
    )
