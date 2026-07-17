"""Tool: Ingest source code for analysis."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from git import Repo

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
    languages: list[str] = field(default_factory=list)
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
    "go": [".go"],
    "kotlin": [".kt", ".kts"],
}

# Reverse mapping
_EXT_TO_LANG: dict[str, str] = {}
for lang, exts in _LANG_EXTENSIONS.items():
    for ext in exts:
        _EXT_TO_LANG[ext] = lang

_LANG_PREFERRED_ROOTS: dict[str, str] = {
    "java": "src/main/java",
    "kotlin": "src/main/kotlin",
    "scala": "src/main/scala",
}

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


def _detect_languages(path: Path) -> list[str]:
    """Detect all languages present under path (sorted)."""
    found: set[str] = set()
    for f in path.rglob("*"):
        if f.is_file() and f.suffix in _EXT_TO_LANG:
            found.add(_EXT_TO_LANG[f.suffix])
    return sorted(found)


def _detect_source_root(path: Path, language: str | None = None) -> Path:
    """Detect the main source root directory.

    Prefers a language-specific Maven/Gradle root when *language* is set.
    Falls back to well-known roots, then the project root.
    """
    if language:
        preferred = _LANG_PREFERRED_ROOTS.get(language)
        if preferred and (path / preferred).is_dir():
            return path / preferred

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


def _resolve_languages(
    path: Path,
    language: str | None,
    languages: list[str] | None,
) -> list[str]:
    if language is not None and languages is not None:
        raise ValueError("Pass only one of language and languages")
    if languages is not None:
        if not languages:
            raise ValueError("languages must be non-empty")
        return list(languages)
    if language == "multi":
        detected = _detect_languages(path)
        if not detected:
            raise ValueError(f"Could not detect languages in {path}")
        return detected
    if language:
        return [language]
    primary = _detect_language(path)
    return [primary] if primary else []


def _detect_version(repo: "Repo") -> str:
    """Detect the latest version tag from a repo."""
    try:
        tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
        if tags:
            return str(tags[-1])
    except Exception:
        pass
    return "HEAD"


def _detect_versions(repo: "Repo") -> list[str]:
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
    languages: list[str] | None = None,
    work_dir: str | None = None,
    exclude_tests: bool = True,
    source_root: str | None = None,
) -> IngestedRepo:
    """Ingest a repository from a URL or local path.

    Args:
        source: Git repo URL or local directory path.
        language: Override language detection (java, python, typescript, c, go,
            kotlin, or "multi" to ingest every detected language).
        languages: Explicit language list for polyglot ingest (e.g. ["java", "kotlin"]).
            Mutually exclusive with *language*.
        work_dir: Directory to clone into. Uses temp dir if None.
        exclude_tests: Exclude test/vendor/build directories (default: True).
        source_root: Override source root (e.g., 'src/main/java'). Auto-detected if None.

    Returns:
        IngestedRepo with path, name, version, and source file list.
    """
    source_path = Path(source)
    sr = Path(source_root) if source_root else None
    if source_path.is_dir():
        return _ingest_local(source_path, language, languages, exclude_tests, sr)
    return _clone_and_ingest(
        source,
        language,
        languages,
        Path(work_dir) if work_dir else None,
        exclude_tests,
        sr,
    )


def _ingest_local(
    path: Path,
    language: str | None = None,
    languages: list[str] | None = None,
    exclude_tests: bool = True,
    source_root: Path | None = None,
) -> IngestedRepo:
    """Ingest a local directory."""
    name = path.name
    version = "local"
    versions: list[str] = []

    try:
        from git import Repo
        repo = Repo(path)
        version = _detect_version(repo)
        versions = _detect_versions(repo)
    except Exception:
        pass

    resolved = _resolve_languages(path, language, languages)
    return _build_ingested_repo(
        project_root=path,
        name=name,
        version=version,
        versions=versions,
        is_temp=False,
        languages=resolved,
        exclude_tests=exclude_tests,
        source_root=source_root,
    )


def _clone_and_ingest(
    url: str,
    language: str | None = None,
    languages: list[str] | None = None,
    work_dir: Path | None = None,
    exclude_tests: bool = True,
    source_root: Path | None = None,
) -> IngestedRepo:
    """Clone a remote repo and ingest it."""
    name = _repo_name_from_url(url)

    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="arcade_agent_"))
    clone_path = work_dir / name

    from git import GitCommandError, Repo
    repo = Repo.clone_from(url, clone_path, depth=1)

    version = _detect_version(repo)
    versions = _detect_versions(repo)

    if version != "HEAD":
        try:
            repo.git.checkout(version)
        except GitCommandError:
            pass

    resolved = _resolve_languages(clone_path, language, languages)
    return _build_ingested_repo(
        project_root=clone_path,
        name=name,
        version=version,
        versions=versions,
        is_temp=True,
        languages=resolved,
        exclude_tests=exclude_tests,
        source_root=source_root,
    )


def _build_ingested_repo(
    *,
    project_root: Path,
    name: str,
    version: str,
    versions: list[str],
    is_temp: bool,
    languages: list[str],
    exclude_tests: bool,
    source_root: Path | None,
) -> IngestedRepo:
    multilang = len(languages) > 1

    if source_root is not None:
        effective_root = source_root
        search_root = source_root
        result_path = source_root
    elif multilang:
        # Keep the project root so every language-specific tree stays visible.
        effective_root = None
        search_root = None
        result_path = project_root
    elif exclude_tests and languages:
        detected = _detect_source_root(project_root, languages[0])
        if detected != project_root:
            effective_root = detected
            search_root = detected
            result_path = detected
        else:
            effective_root = None
            search_root = None
            result_path = project_root
    else:
        effective_root = None
        search_root = None
        result_path = project_root

    source_files: list[Path] = []
    if languages:
        for lang in languages:
            source_files.extend(
                _discover_files(project_root, lang, exclude_tests, search_root)
            )
        # Preserve stable order while dropping duplicates across languages.
        source_files = list(dict.fromkeys(source_files))
    else:
        source_files = _discover_files(
            project_root, None, exclude_tests, effective_root
        )

    primary = languages[0] if len(languages) == 1 else (
        "multi" if languages else None
    )

    return IngestedRepo(
        path=result_path,
        name=name,
        version=version,
        is_temp=is_temp,
        source_files=source_files,
        language=primary,
        languages=languages,
        versions=versions,
    )
