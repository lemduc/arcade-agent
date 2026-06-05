"""Tests for the Go parser."""

import pytest

go = pytest.importorskip("tree_sitter_go")
from arcade_agent.parsers.go import GoParser  # noqa: E402


def _project(tmp_path):
    (tmp_path / "store").mkdir()
    (tmp_path / "auth").mkdir()
    (tmp_path / "store" / "db.go").write_text(
        "package store\n"
        "type DB struct { Host string }\n"
        "func Open() *DB { return &DB{} }\n"
    )
    (tmp_path / "auth" / "auth.go").write_text(
        "package auth\n"
        'import "example.com/app/store"\n'
        "type User struct { ID int }\n"
        "func Login(s *store.DB) *User { return New(1) }\n"
        "func New(id int) *User { return &User{ID: id} }\n"
    )
    return list(tmp_path.rglob("*.go"))


def test_go_parser_properties():
    parser = GoParser()
    assert parser.language == "go"
    assert ".go" in parser.file_extensions


def test_go_parser_entities(tmp_path):
    parser = GoParser()
    graph = parser.parse(_project(tmp_path), tmp_path)
    names = {e.name for e in graph.entities.values()}
    assert {"DB", "Open", "User", "Login", "New"} <= names
    kinds = {e.name: e.kind for e in graph.entities.values()}
    assert kinds["DB"] == "struct"
    assert kinds["Login"] == "function"


def test_go_parser_packages_are_directories(tmp_path):
    parser = GoParser()
    graph = parser.parse(_project(tmp_path), tmp_path)
    assert "store" in graph.packages
    assert "auth" in graph.packages


def test_go_parser_cross_and_intra_package_edges(tmp_path):
    parser = GoParser()
    graph = parser.parse(_project(tmp_path), tmp_path)
    rels = {(e.source.split(".")[-1], e.target.split(".")[-1]) for e in graph.edges}
    assert ("Login", "DB") in rels   # cross-package via qualified type *store.DB
    assert ("Login", "New") in rels  # intra-package call
