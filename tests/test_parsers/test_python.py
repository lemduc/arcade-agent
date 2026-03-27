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
