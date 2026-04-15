"""Serialize and deserialize analysis objects for storage and transport."""

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from arcade_agent.models.architecture import Architecture, Component
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity


def save_architecture(arch: Architecture, path: Path) -> None:
    """Write an Architecture to a JSON file.

    Creates parent directories if they don't exist.

    Args:
        arch: The architecture to serialize.
        path: Destination file path.
    """
    data = {
        "algorithm": arch.algorithm,
        "rationale": arch.rationale,
        "metadata": arch.metadata,
        "components": [
            {
                "name": c.name,
                "responsibility": c.responsibility,
                "entities": c.entities,
            }
            for c in arch.components
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def load_architecture(path: Path) -> Architecture:
    """Read an Architecture from a JSON file.

    Args:
        path: Path to the baseline JSON file.

    Returns:
        The deserialized Architecture.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    data = json.loads(path.read_text())
    components = [
        Component(
            name=c["name"],
            responsibility=c.get("responsibility", ""),
            entities=c.get("entities", []),
        )
        for c in data.get("components", [])
    ]
    return Architecture(
        components=components,
        rationale=data.get("rationale", ""),
        algorithm=data.get("algorithm", ""),
        metadata=data.get("metadata", {}),
    )


# ---------------------------------------------------------------------------
# DependencyGraph serialization
# ---------------------------------------------------------------------------


def save_graph(graph: DependencyGraph, path: Path) -> None:
    """Write a DependencyGraph to a JSON file.

    Args:
        graph: The dependency graph to serialize.
        path: Destination file path.
    """
    data = graph_to_dict(graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def load_graph(path: Path) -> DependencyGraph:
    """Read a DependencyGraph from a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        The deserialized DependencyGraph.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    data = json.loads(path.read_text())
    return dict_to_graph(data)


def graph_to_dict(graph: DependencyGraph) -> dict:
    """Convert a DependencyGraph to a JSON-serializable dict."""
    return {
        "entities": {
            fqn: {
                "fqn": e.fqn,
                "name": e.name,
                "package": e.package,
                "file_path": e.file_path,
                "kind": e.kind,
                "language": e.language,
                "imports": e.imports,
                "superclass": e.superclass,
                "interfaces": e.interfaces,
                "properties": e.properties,
            }
            for fqn, e in graph.entities.items()
        },
        "edges": [
            {"source": e.source, "target": e.target, "relation": e.relation}
            for e in graph.edges
        ],
        "packages": graph.packages,
    }


def dict_to_graph(data: dict) -> DependencyGraph:
    """Reconstruct a DependencyGraph from a dict."""
    entities = {
        fqn: Entity(
            fqn=e["fqn"],
            name=e["name"],
            package=e["package"],
            file_path=e["file_path"],
            kind=e["kind"],
            language=e["language"],
            imports=e.get("imports", []),
            superclass=e.get("superclass"),
            interfaces=e.get("interfaces", []),
            properties=e.get("properties", {}),
        )
        for fqn, e in data.get("entities", {}).items()
    }
    edges = [
        Edge(source=e["source"], target=e["target"], relation=e["relation"])
        for e in data.get("edges", [])
    ]
    packages: dict[str, list[str]] = data.get("packages", {})
    return DependencyGraph(entities=entities, edges=edges, packages=packages)


def architecture_to_dict(arch: Architecture) -> dict:
    """Convert an Architecture to a JSON-serializable dict."""
    return {
        "algorithm": arch.algorithm,
        "rationale": arch.rationale,
        "metadata": arch.metadata,
        "components": [
            {
                "name": c.name,
                "responsibility": c.responsibility,
                "entities": c.entities,
            }
            for c in arch.components
        ],
    }


def dict_to_architecture(data: dict) -> Architecture:
    """Reconstruct an Architecture from a dict."""
    components = [
        Component(
            name=c["name"],
            responsibility=c.get("responsibility", ""),
            entities=c.get("entities", []),
        )
        for c in data.get("components", [])
    ]
    return Architecture(
        components=components,
        rationale=data.get("rationale", ""),
        algorithm=data.get("algorithm", ""),
        metadata=data.get("metadata", {}),
    )


# ---------------------------------------------------------------------------
# Generic result serializer (for MCP transport)
# ---------------------------------------------------------------------------


def serialize_result(obj: Any) -> Any:
    """Convert any tool return value to a JSON-safe structure.

    Handles dataclasses, Path objects, lists, dicts, and primitives.

    Args:
        obj: The object to serialize.

    Returns:
        A JSON-serializable Python object (dict, list, str, int, float, bool, None).
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, DependencyGraph):
        return graph_to_dict(obj)
    if isinstance(obj, Architecture):
        return architecture_to_dict(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return _serialize_dataclass_dict(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): serialize_result(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_result(item) for item in obj]
    return str(obj)


def _serialize_dataclass_dict(d: dict) -> dict:
    """Recursively clean a dict produced by dataclasses.asdict."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _serialize_dataclass_dict(v)
        elif isinstance(v, list):
            out[k] = [_serialize_dataclass_dict(i) if isinstance(i, dict) else i for i in v]
        elif isinstance(v, Path):
            out[k] = str(v)
        else:
            out[k] = v
    return out
