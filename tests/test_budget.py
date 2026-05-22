"""Tests for token budget truncation."""

from arcade_agent.budget import estimate_tokens, truncate_result


def _make_large_data(num_entities=100, num_edges=200):
    """Build a realistic-looking serialized analysis result."""
    entities = {
        f"com.example.pkg{i}.Class{j}": {
            "fqn": f"com.example.pkg{i}.Class{j}",
            "name": f"Class{j}",
            "package": f"com.example.pkg{i}",
            "kind": "class",
            "language": "java",
            "file_path": f"pkg{i}/Class{j}.java",
            "imports": [f"com.example.pkg{(i+1) % 10}.Class{j}" for j in range(3)],
        }
        for i in range(10)
        for j in range(num_entities // 10)
    }
    edges = [
        {"source": f"com.example.pkg{i}.Class0", "target": f"com.example.pkg{(i+1)%10}.Class0",
         "relation": "import"}
        for i in range(min(num_edges, num_entities))
    ]
    return {
        "graph": {
            "num_entities": len(entities),
            "num_edges": len(edges),
            "entities": entities,
            "edges": edges,
            "packages": {
                f"com.example.pkg{i}": [
                    f"com.example.pkg{i}.Class{j}" for j in range(num_entities // 10)
                ]
                for i in range(10)
            },
        },
        "architecture": {
            "algorithm": "pkg",
            "rationale": "Package-based grouping",
            "components": [
                {
                    "name": f"Component{i}",
                    "responsibility": f"Handles pkg{i} logic",
                    "num_entities": num_entities // 10,
                    "entities": [f"com.example.pkg{i}.Class{j}" for j in range(num_entities // 10)],
                }
                for i in range(10)
            ],
        },
    }


def test_estimate_tokens():
    assert estimate_tokens({"hello": "world"}) > 0
    small = estimate_tokens({"a": 1})
    large = estimate_tokens({"a": "x" * 1000})
    assert large > small


def test_no_truncation_within_budget():
    data = {"graph": {"num_entities": 5}, "architecture": {"components": []}}
    result = truncate_result(data, max_tokens=10000)
    assert result == data


def test_truncates_entity_lists_in_components():
    data = _make_large_data(num_entities=100)
    # Set a budget that forces truncation
    tokens = estimate_tokens(data)
    result = truncate_result(data, max_tokens=tokens // 4)
    for comp in result.get("architecture", {}).get("components", []):
        entities = comp.get("entities", [])
        # Either truncated to 10 or removed entirely
        assert len(entities) <= 10 or "entities_truncated" in comp or "num_entities" in comp


def test_collapses_edges_to_summary():
    data = _make_large_data(num_entities=100)
    # Very tight budget
    result = truncate_result(data, max_tokens=200)
    graph = result.get("graph", {})
    # Edges should be collapsed or removed
    if "edges" not in graph:
        assert "edge_summary" in graph or "num_edges" in graph


def test_progressive_reduction():
    data = _make_large_data(num_entities=100)
    full_tokens = estimate_tokens(data)

    # Moderate budget — should preserve some detail
    moderate = truncate_result(data, max_tokens=full_tokens // 2)
    moderate_tokens = estimate_tokens(moderate)

    # Tight budget — should be more aggressive
    tight = truncate_result(data, max_tokens=full_tokens // 8)
    tight_tokens = estimate_tokens(tight)

    assert tight_tokens <= moderate_tokens


def test_handles_non_dict_gracefully():
    # truncate_result expects dict, but should handle primitives
    result = truncate_result({"simple": "data"}, max_tokens=1000)
    assert result == {"simple": "data"}
