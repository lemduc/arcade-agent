"""Tests for the TypeScript / JavaScript parser."""

import pytest

ts = pytest.importorskip("tree_sitter_typescript")
from arcade_agent.parsers.typescript import TypeScriptParser  # noqa: E402


def _project(tmp_path):
    (tmp_path / "models").mkdir()
    (tmp_path / "services").mkdir()
    (tmp_path / "models" / "user.ts").write_text(
        "export class User { constructor(public id: number) {} }\n"
        "export interface IRepo { find(id: number): User; }\n"
    )
    (tmp_path / "services" / "userService.ts").write_text(
        'import { User, IRepo } from "../models/user";\n'
        "export class UserService implements IRepo {\n"
        "  find(id: number): User { return new User(id); }\n"
        "}\n"
        "export function makeUser(id: number): User { return new User(id); }\n"
    )
    return list(tmp_path.rglob("*.ts"))


def test_ts_parser_properties():
    parser = TypeScriptParser()
    assert parser.language == "typescript"
    assert ".ts" in parser.file_extensions
    assert ".tsx" in parser.file_extensions


def test_ts_parser_entities(tmp_path):
    parser = TypeScriptParser()
    graph = parser.parse(_project(tmp_path), tmp_path)
    names = {e.name for e in graph.entities.values()}
    assert {"User", "IRepo", "UserService", "makeUser"} <= names
    kinds = {e.name: e.kind for e in graph.entities.values()}
    assert kinds["User"] == "class"
    assert kinds["IRepo"] == "interface"
    assert kinds["makeUser"] == "function"


def test_ts_parser_cross_file_edges(tmp_path):
    parser = TypeScriptParser()
    graph = parser.parse(_project(tmp_path), tmp_path)
    rels = {(e.source.split(".")[-1], e.target.split(".")[-1], e.relation) for e in graph.edges}
    # import edge across files and an implements edge
    assert ("UserService", "User", "import") in rels
    assert ("UserService", "IRepo", "implements") in rels


def test_ts_parser_packages_by_directory(tmp_path):
    parser = TypeScriptParser()
    graph = parser.parse(_project(tmp_path), tmp_path)
    assert "models" in graph.packages
    assert "services" in graph.packages
