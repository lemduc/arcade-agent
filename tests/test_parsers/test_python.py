"""Tests for the Python parser."""

from arcade_agent.parsers.python import PythonParser


def test_python_parser_entities(python_files, fixtures_dir):
    parser = PythonParser()
    graph = parser.parse(python_files, fixtures_dir)

    # Should find classes and functions from app.py and models.py
    assert graph.num_entities >= 3
    entity_names = {e.name for e in graph.entities.values()}
    assert "User" in entity_names or "UserService" in entity_names


def test_python_parser_classes(python_files, fixtures_dir):
    parser = PythonParser()
    graph = parser.parse(python_files, fixtures_dir)

    # Find Product class from models.py
    product_entities = [e for e in graph.entities.values() if e.name == "Product"]
    if product_entities:
        product = product_entities[0]
        assert product.kind == "class"
        assert product.language == "python"
        assert product.superclass == "BaseModel"


def test_python_parser_properties():
    parser = PythonParser()
    assert parser.language == "python"
    assert ".py" in parser.file_extensions


def test_python_parser_skips_empty_init_modules(tmp_path):
    package_dir = tmp_path / "pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text('"""package marker"""\n')
    module_path = package_dir / "service.py"
    module_path.write_text("def run():\n    return 1\n")

    parser = PythonParser()
    graph = parser.parse([package_dir / "__init__.py", module_path], tmp_path)

    assert "pkg" not in graph.entities
    assert "pkg.service.run" in graph.entities


def test_python_parser_extracts_methods(python_files, fixtures_dir):
    parser = PythonParser()
    graph = parser.parse(python_files, fixtures_dir)

    assert "app.UserService.add_user" in graph.entities
    assert graph.entities["app.UserService.add_user"].kind == "method"
    assert graph.entities["app.UserService.add_user"].properties["owner"] == "app.UserService"


def test_python_parser_keeps_decorator_edges(tmp_path):
    package_dir = tmp_path / "pkg"
    package_dir.mkdir()

    registry_path = package_dir / "registry.py"
    registry_path.write_text(
        "def tool(fn):\n"
        "    return fn\n"
    )
    module_path = package_dir / "service.py"
    module_path.write_text(
        "from pkg.registry import tool\n\n"
        "@tool\n"
        "def run():\n"
        "    return 1\n"
    )

    parser = PythonParser()
    graph = parser.parse([registry_path, module_path], tmp_path)

    assert "pkg.service.run" in graph.entities
    assert ("pkg.service.run", "pkg.registry.tool", "import") in graph.to_edge_tuples()
