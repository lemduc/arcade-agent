"""Ingest source code for analysis."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from git import Repo

from arcade_agent.source.filtering import (
    ExcludedDirectories,
    is_excluded_source_path,
    normalize_exclude_dirs,
)


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
    exclude_tests: bool = True
    exclude_dirs: list[str] = field(default_factory=list)
    temp_root: Path | None = None
    """Directory to delete on cleanup, if it differs from `path`.

    `path` may be narrowed to a detected source root (e.g. `src/`,
    `src/main/java`) so parsers can derive correct package-relative FQNs.
    When ingestion materialised a whole extra tree (e.g. `ref=` extraction),
    that tree's root belongs here so cleanup removes the entire tree rather
    than just the narrowed subdirectory. None means `path` itself is what
    was materialised and should be removed.
    """

    def cleanup(self) -> None:
        """Remove the temporary directory if applicable."""
        if self.is_temp:
            target = self.temp_root or self.path
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)


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

# Per-language source roots. Only languages with a parser belong here; generic
# roots (including src/main/scala) are still probed via _SOURCE_ROOTS.
_LANG_PREFERRED_ROOTS: dict[str, str] = {
    "java": "src/main/java",
    "kotlin": "src/main/kotlin",
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

def _detect_language(
    path: Path,
    exclude_tests: bool = True,
    exclude_dirs: ExcludedDirectories = (),
) -> str | None:
    """Auto-detect the primary language from file extensions."""
    ext_counts: dict[str, int] = {}
    for f in path.rglob("*"):
        if (
            f.is_file()
            and f.suffix in _EXT_TO_LANG
            and not is_excluded_source_path(
                f,
                path,
                exclude_defaults=exclude_tests,
                exclude_dirs=exclude_dirs,
            )
        ):
            ext_counts[f.suffix] = ext_counts.get(f.suffix, 0) + 1

    if not ext_counts:
        return None

    best_ext = max(ext_counts, key=ext_counts.get)  # type: ignore[arg-type]
    return _EXT_TO_LANG.get(best_ext)


def _detect_languages(
    path: Path,
    exclude_tests: bool = True,
    exclude_dirs: ExcludedDirectories = (),
) -> list[str]:
    """Detect all languages present under path (sorted)."""
    found: set[str] = set()
    for f in path.rglob("*"):
        if (
            f.is_file()
            and f.suffix in _EXT_TO_LANG
            and not is_excluded_source_path(
                f,
                path,
                exclude_defaults=exclude_tests,
                exclude_dirs=exclude_dirs,
            )
        ):
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


def _discover_files(
    path: Path,
    language: str | None = None,
    exclude_tests: bool = True,
    source_root: Path | None = None,
    exclude_dirs: ExcludedDirectories = (),
) -> list[Path]:
    """Discover source files for the given language.

    Args:
        path: Project root directory.
        language: Language to filter for.
        exclude_tests: Whether to exclude test/vendor directories.
        source_root: Override source root (search here instead of path).
        exclude_dirs: Additional exact project-relative directory exclusions.
    """
    search_path = source_root if source_root else path

    if language and language in _LANG_EXTENSIONS:
        extensions = _LANG_EXTENSIONS[language]
    else:
        extensions = list(_EXT_TO_LANG.keys())

    files = []
    for ext in extensions:
        for f in sorted(search_path.rglob(f"*{ext}")):
            if is_excluded_source_path(
                f,
                path,
                exclude_defaults=exclude_tests,
                exclude_dirs=exclude_dirs,
            ):
                continue
            files.append(f)
    return files


def _validate_known_languages(languages: list[str]) -> list[str]:
    """Reject unknown language names before discovery expands to all extensions."""
    unknown = [lang for lang in languages if lang not in _LANG_EXTENSIONS]
    if unknown:
        available = ", ".join(sorted(_LANG_EXTENSIONS))
        raise ValueError(
            f"Unknown language(s): {', '.join(unknown)}. Supported: {available}"
        )
    return languages


def _resolve_languages(
    path: Path,
    language: str | None,
    languages: list[str] | None,
    exclude_tests: bool,
    exclude_dirs: ExcludedDirectories,
) -> list[str]:
    if language is not None and languages is not None:
        raise ValueError("Pass only one of language and languages")
    if languages is not None:
        if not languages:
            raise ValueError("languages must be non-empty")
        return _validate_known_languages(list(languages))
    if language == "multi":
        detected = _detect_languages(path, exclude_tests, exclude_dirs)
        if not detected:
            raise ValueError(f"Could not detect languages in {path}")
        return detected
    if language:
        return _validate_known_languages([language])
    primary = _detect_language(path, exclude_tests, exclude_dirs)
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


def _materialize_ref(repo_path: Path, ref: str) -> Path:
    """Extract a git ref into a fresh temp directory.

    Uses ``git archive`` so the caller's working tree, index and HEAD are
    untouched. The extracted tree has no ``.git`` directory, which is why the
    caller supplies the version rather than detecting it from tags.

    Args:
        repo_path: Path to a git repository.
        ref: A commit SHA, tag or branch name.

    Returns:
        Path to the extracted tree. Caller owns cleanup.

    Raises:
        ValueError: If *repo_path* is not a git repository, or *ref* is unknown.
    """
    if not (repo_path / ".git").exists():
        raise ValueError(f"{repo_path} is not a git repository; cannot use ref={ref!r}")

    resolved = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if resolved.returncode != 0:
        tags = subprocess.run(
            ["git", "-C", str(repo_path), "tag", "--list"],
            capture_output=True,
            text=True,
        ).stdout.split()
        available = ", ".join(tags) if tags else "none"
        raise ValueError(f"Unknown ref {ref!r} in {repo_path}. Available tags: {available}")

    # Archive the resolved SHA, not the raw *ref* string: this closes a
    # TOCTOU window between verification and archival, and avoids passing a
    # user-controlled string starting with "-" to `git archive` as an
    # argument.
    resolved_sha = resolved.stdout.strip()

    dest = Path(tempfile.mkdtemp(prefix="arcade_agent_ref_"))
    try:
        archive = subprocess.run(
            ["git", "-C", str(repo_path), "archive", resolved_sha],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["tar", "-x", "-C", str(dest)],
            input=archive.stdout,
            check=True,
            capture_output=True,
        )
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return dest


def ingest(
    source: str,
    language: str | None = None,
    languages: list[str] | None = None,
    work_dir: str | None = None,
    exclude_tests: bool = True,
    source_root: str | None = None,
    exclude_dirs: list[str] | None = None,
    ref: str | None = None,
) -> IngestedRepo:
    """Ingest a repository from a URL or local path.

    Args:
        source: Git repo URL or local directory path.
        language: Override language detection (java, python, typescript, c, go,
            kotlin, or "multi" to ingest every detected language).
        languages: Explicit language list for polyglot ingest (e.g. ["java", "kotlin"]).
            Mutually exclusive with *language*.
        work_dir: Directory to clone into. Uses temp dir if None. Ignored when
            *ref* is set.
        exclude_tests: Exclude test/vendor/build directories (default: True).
        source_root: Override source root (e.g., 'src/main/java'). Auto-detected if None.
        exclude_dirs: Additional exact project-relative directories to exclude
            (e.g. ["integrationTest", "src/e2e"]).
        ref: Optional git commit, tag or branch to analyse instead of the
            working tree. Extracted to a temp directory; the caller's working
            tree is never modified.

    Returns:
        IngestedRepo with path, name, version, and source file list.

    Raises:
        ValueError: If *ref* is given but *source* is not a local directory,
            is not a git repository, or *ref* does not resolve to a commit.
    """
    if ref is not None:
        source_path = Path(source)
        if not source_path.is_dir():
            raise ValueError(f"ref={ref!r} requires a local repository path, got {source!r}")
        extracted = _materialize_ref(source_path, ref)
        try:
            repo = _ingest_local(
                extracted,
                language=language,
                languages=languages,
                exclude_tests=exclude_tests,
                source_root=Path(source_root) if source_root else None,
                exclude_dirs=normalize_exclude_dirs(exclude_dirs),
            )
        except BaseException:
            shutil.rmtree(extracted, ignore_errors=True)
            raise
        # The extracted tree lives in a mkdtemp directory, so _ingest_local
        # derives a meaningless name like "arcade_agent_ref_x1y2z3" — name the
        # repo after the source repository instead.
        repo.name = source_path.resolve().name
        repo.version = ref
        repo.is_temp = True
        repo.temp_root = extracted
        return repo

    source_path = Path(source)
    sr = Path(source_root) if source_root else None
    normalized_exclude_dirs = normalize_exclude_dirs(exclude_dirs)
    if source_path.is_dir():
        return _ingest_local(
            source_path,
            language,
            languages,
            exclude_tests,
            sr,
            normalized_exclude_dirs,
        )
    return _clone_and_ingest(
        source,
        language,
        languages,
        Path(work_dir) if work_dir else None,
        exclude_tests,
        sr,
        normalized_exclude_dirs,
    )


def _ingest_local(
    path: Path,
    language: str | None = None,
    languages: list[str] | None = None,
    exclude_tests: bool = True,
    source_root: Path | None = None,
    exclude_dirs: ExcludedDirectories = (),
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

    resolved = _resolve_languages(
        path,
        language,
        languages,
        exclude_tests,
        exclude_dirs,
    )
    return _build_ingested_repo(
        project_root=path,
        name=name,
        version=version,
        versions=versions,
        is_temp=False,
        languages=resolved,
        exclude_tests=exclude_tests,
        source_root=source_root,
        exclude_dirs=exclude_dirs,
    )


def _clone_and_ingest(
    url: str,
    language: str | None = None,
    languages: list[str] | None = None,
    work_dir: Path | None = None,
    exclude_tests: bool = True,
    source_root: Path | None = None,
    exclude_dirs: ExcludedDirectories = (),
) -> IngestedRepo:
    """Clone a remote repo and ingest it."""
    name = _repo_name_from_url(url)

    caller_supplied_work_dir = work_dir is not None
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

    resolved = _resolve_languages(
        clone_path,
        language,
        languages,
        exclude_tests,
        exclude_dirs,
    )
    ingested = _build_ingested_repo(
        project_root=clone_path,
        name=name,
        version=version,
        versions=versions,
        is_temp=True,
        languages=resolved,
        exclude_tests=exclude_tests,
        source_root=source_root,
        exclude_dirs=exclude_dirs,
    )
    # `_build_ingested_repo` may narrow `.path` to a detected source root
    # (e.g. `src/main/java`); without `temp_root`, cleanup() would then
    # rmtree only that subdirectory and leak the rest of the clone,
    # including `.git`. `clone_path` is always what was cloned, so it is
    # always a safe cleanup target regardless of narrowing.
    #
    # When `work_dir` was auto-created (the caller didn't supply one), it
    # contains nothing but `clone_path`, so cleaning up the whole auto
    # directory also avoids leaving an empty temp-dir shell behind after
    # `clone_path` is removed. When `work_dir` was supplied by the caller,
    # it must never be the cleanup target -- only `clone_path`, exactly as
    # before this fix.
    ingested.temp_root = clone_path if caller_supplied_work_dir else work_dir
    return ingested


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
    exclude_dirs: ExcludedDirectories,
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
                _discover_files(
                    project_root,
                    lang,
                    exclude_tests,
                    search_root,
                    exclude_dirs,
                )
            )
        # Preserve stable order while dropping duplicates across languages.
        source_files = list(dict.fromkeys(source_files))
    else:
        source_files = _discover_files(
            project_root,
            None,
            exclude_tests,
            effective_root,
            exclude_dirs,
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
        exclude_tests=exclude_tests,
        exclude_dirs=["/".join(parts) for parts in exclude_dirs],
    )
