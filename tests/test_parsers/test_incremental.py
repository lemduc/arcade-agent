"""Incremental Python parsing must produce a graph identical to a full parse."""

from pathlib import Path

from arcade_agent.incremental import ExtractCache
from arcade_agent.parsers.python import PythonParser


def _project(tmp_path: Path) -> list[Path]:
    (tmp_path / "app" / "a").mkdir(parents=True)
    (tmp_path / "app" / "b").mkdir(parents=True)
    for d in (tmp_path / "app", tmp_path / "app" / "a", tmp_path / "app" / "b"):
        (d / "__init__.py").write_text("")
    (tmp_path / "app" / "a" / "model.py").write_text(
        "class User:\n    def name(self):\n        return 'x'\n"
    )
    (tmp_path / "app" / "b" / "service.py").write_text(
        "from app.a.model import User\n\n"
        "class Service:\n    def make(self):\n        return User()\n"
    )
    return list(tmp_path.rglob("*.py"))


def _sig(g):
    ents = sorted((e.fqn, e.kind, e.package, e.superclass) for e in g.entities.values())
    edges = sorted((e.source, e.target, e.relation) for e in g.edges)
    return (ents, edges, sorted((k, tuple(sorted(v))) for k, v in g.packages.items()))


def test_incremental_matches_full_cold(tmp_path):
    files = _project(tmp_path)
    parser = PythonParser()
    full = parser.parse(files, tmp_path)
    incr = parser.parse_incremental(files, tmp_path, ExtractCache(tmp_path))
    assert _sig(full) == _sig(incr)


def test_incremental_matches_full_warm_and_after_edit(tmp_path):
    files = _project(tmp_path)
    parser = PythonParser()
    cache = ExtractCache(tmp_path)
    parser.parse_incremental(files, tmp_path, cache)          # warm the cache
    warm = parser.parse_incremental(files, tmp_path, cache)   # reuse
    assert _sig(parser.parse(files, tmp_path)) == _sig(warm)
    assert cache.stats["reused"] > 0  # the warm run actually hit the cache

    # Edit one file; incremental must match a fresh full parse.
    svc = tmp_path / "app" / "b" / "service.py"
    svc.write_text(svc.read_text() + "\nEXTRA = 1\n")
    after = parser.parse_incremental(files, tmp_path, ExtractCache(tmp_path))
    assert _sig(parser.parse(files, tmp_path)) == _sig(after)


def test_extract_cache_reextracts_only_changed(tmp_path):
    files = _project(tmp_path)
    parser = PythonParser()
    cache = ExtractCache(tmp_path)
    parser.parse_incremental(files, tmp_path, cache)  # cold: extracts all
    model = tmp_path / "app" / "a" / "model.py"
    model.write_text(model.read_text() + "\nclass Admin(User):\n    pass\n")
    cache.stats = {"reused": 0, "extracted": 0}
    parser.parse_incremental(files, tmp_path, cache)  # only model.py changed
    assert cache.stats["extracted"] == 1
    assert cache.stats["reused"] >= 1
