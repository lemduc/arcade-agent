"""Serialize and deserialize Architecture objects for baseline storage."""

import json
from pathlib import Path

from arcade_agent.models.architecture import Architecture, Component


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
