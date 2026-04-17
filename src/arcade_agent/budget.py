"""Token budget truncation for AI-agent-friendly output."""

import json
from typing import Any


def estimate_tokens(data: Any) -> int:
    """Estimate token count from a JSON-serializable object.

    Uses a rough heuristic of ~4 characters per token.

    Args:
        data: Any JSON-serializable object.

    Returns:
        Estimated token count.
    """
    return len(json.dumps(data, default=str)) // 4


def truncate_result(data: dict, max_tokens: int) -> dict:
    """Progressively reduce output size to fit within a token budget.

    Applies increasingly aggressive reduction strategies:
    1. Return as-is if within budget.
    2. Truncate entity lists in components.
    3. Remove entity-level details from graph (keep counts).
    4. Collapse edges to summary counts.
    5. Keep only component names and entity counts.

    Args:
        data: A dict produced by serialize_result (graph, architecture, etc.).
        max_tokens: Target maximum token count.

    Returns:
        A truncated version of the data that fits within the budget.
    """
    if estimate_tokens(data) <= max_tokens:
        return data

    result = _deep_copy(data)

    # Level 1: Truncate entity lists in architecture components
    if "components" in result.get("architecture", {}):
        for comp in result["architecture"]["components"]:
            entities = comp.get("entities", [])
            if len(entities) > 10:
                comp["entities"] = entities[:10]
                comp["entities_truncated"] = len(entities)
        if estimate_tokens(result) <= max_tokens:
            return result

    # Level 2: Remove full entity details from graph, keep summary
    if "entities" in result.get("graph", {}):
        entities = result["graph"]["entities"]
        if isinstance(entities, dict) and len(entities) > 0:
            first_key = next(iter(entities))
            if isinstance(entities[first_key], dict):
                result["graph"]["num_entities"] = len(entities)
                # Keep only FQN -> kind mapping
                result["graph"]["entities"] = {
                    fqn: e.get("kind", "unknown") if isinstance(e, dict) else e
                    for fqn, e in entities.items()
                }
        if estimate_tokens(result) <= max_tokens:
            return result

    # Level 3: Collapse edges to counts
    if "edges" in result.get("graph", {}):
        edges = result["graph"]["edges"]
        if isinstance(edges, list):
            result["graph"]["num_edges"] = len(edges)
            # Group by relation type
            relation_counts: dict[str, int] = {}
            for e in edges:
                rel = e.get("relation", "unknown") if isinstance(e, dict) else "unknown"
                relation_counts[rel] = relation_counts.get(rel, 0) + 1
            result["graph"]["edge_summary"] = relation_counts
            del result["graph"]["edges"]
        if estimate_tokens(result) <= max_tokens:
            return result

    # Level 4: Remove entity map entirely, keep only counts
    if "entities" in result.get("graph", {}):
        entity_data = result["graph"]["entities"]
        if isinstance(entity_data, dict):
            kind_counts: dict[str, int] = {}
            for v in entity_data.values():
                kind = v if isinstance(v, str) else "unknown"
                kind_counts[kind] = kind_counts.get(kind, 0) + 1
            result["graph"]["entity_summary"] = kind_counts
            del result["graph"]["entities"]
        if estimate_tokens(result) <= max_tokens:
            return result

    # Level 5: Minimize components to name + entity count only
    if "components" in result.get("architecture", {}):
        result["architecture"]["components"] = [
            {
                "name": c.get("name", ""),
                "num_entities": c.get("num_entities", len(c.get("entities", []))),
            }
            for c in result["architecture"]["components"]
        ]
        if estimate_tokens(result) <= max_tokens:
            return result

    # Level 6: Remove packages
    if "packages" in result.get("graph", {}):
        pkgs = result["graph"]["packages"]
        result["graph"]["num_packages"] = len(pkgs) if isinstance(pkgs, dict) else 0
        del result["graph"]["packages"]

    return result


def _deep_copy(data: Any) -> Any:
    """Simple deep copy for JSON-like structures."""
    if isinstance(data, dict):
        return {k: _deep_copy(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_deep_copy(item) for item in data]
    return data
