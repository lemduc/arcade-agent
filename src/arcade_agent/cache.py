"""Parse result caching based on file modification times."""

import hashlib
import json
import logging
from pathlib import Path

from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.serialization import dict_to_graph, graph_to_dict

logger = logging.getLogger(__name__)

_CACHE_DIR = ".arcade-cache"


def _cache_dir(project_root: Path) -> Path:
    """Return the cache directory for a project."""
    return project_root / _CACHE_DIR


def cache_key(source_path: str, language: str | None, files: list[str] | None) -> str:
    """Compute a cache key from source path, language, and file mtimes.

    The key is a SHA-256 hash of the sorted file paths and their modification
    times, ensuring the cache is automatically invalidated when any source file
    changes.

    Args:
        source_path: Root directory of the project.
        language: Language being parsed (or None for auto-detect).
        files: Specific files to parse, or None to discover all.

    Returns:
        A hex digest string usable as a cache filename.
    """
    root = Path(source_path).resolve()
    hasher = hashlib.sha256()
    hasher.update(str(root).encode())
    hasher.update((language or "auto").encode())

    if files:
        file_paths = sorted(files)
    else:
        # Hash all source-like files under root
        file_paths = sorted(str(f) for f in root.rglob("*") if f.is_file() and f.suffix in {
            ".java", ".py", ".c", ".cpp", ".h", ".hpp", ".ts", ".tsx", ".js", ".jsx",
        })

    for fp in file_paths:
        p = Path(fp)
        hasher.update(fp.encode())
        if p.exists():
            hasher.update(str(p.stat().st_mtime_ns).encode())

    return hasher.hexdigest()


def get_cached_graph(project_root: str, key: str) -> DependencyGraph | None:
    """Retrieve a cached DependencyGraph if it exists.

    Args:
        project_root: Root directory of the project (cache lives here).
        key: Cache key from cache_key().

    Returns:
        The cached DependencyGraph, or None on cache miss.
    """
    cache_file = _cache_dir(Path(project_root)) / f"{key}.json"
    if not cache_file.exists():
        return None

    try:
        data = json.loads(cache_file.read_text())
        graph = dict_to_graph(data)
        logger.info("Cache hit for %s (%d entities)", key[:12], graph.num_entities)
        return graph
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Corrupt cache file %s, removing", cache_file)
        cache_file.unlink(missing_ok=True)
        return None


def put_cached_graph(project_root: str, key: str, graph: DependencyGraph) -> None:
    """Store a DependencyGraph in the cache.

    Args:
        project_root: Root directory of the project.
        key: Cache key from cache_key().
        graph: The graph to cache.
    """
    cache_dir = _cache_dir(Path(project_root))
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{key}.json"
    cache_file.write_text(json.dumps(graph_to_dict(graph), indent=2) + "\n")
    logger.info("Cached parse result %s (%d entities)", key[:12], graph.num_entities)


def invalidate_cache(project_root: str) -> int:
    """Remove all cached parse results for a project.

    Args:
        project_root: Root directory of the project.

    Returns:
        Number of cache files removed.
    """
    cache_dir = _cache_dir(Path(project_root))
    if not cache_dir.exists():
        return 0
    removed = 0
    for f in cache_dir.glob("*.json"):
        f.unlink()
        removed += 1
    logger.info("Invalidated %d cache entries for %s", removed, project_root)
    return removed
