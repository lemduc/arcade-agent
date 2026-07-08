"""Tests for the dependency_cone tool."""

from arcade_agent.tools.dependency_cone import dependency_cone


def test_downstream_from_entity(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.util.MathHelper", direction="downstream"
    )
    assert result["matched_by"] == "entity"
    assert "upstream" not in result
    fqns = {n["fqn"] for n in result["downstream"]["nodes"]}
    assert fqns == {
        "com.example.calc.Calculator",
        "com.example.calc.AdvancedCalculator",
    }
    assert all(n["distance"] == 1 for n in result["downstream"]["nodes"])


def test_upstream_from_entity(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.calc.Calculator", direction="upstream"
    )
    assert "downstream" not in result
    fqns = {n["fqn"] for n in result["upstream"]["nodes"]}
    assert fqns == {"com.example.util.MathHelper"}


def test_both_directions(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.calc.Calculator", direction="both"
    )
    assert "upstream" in result and "downstream" in result
    # Calculator depends on MathHelper; AdvancedCalculator depends on Calculator
    assert {n["fqn"] for n in result["upstream"]["nodes"]} == {
        "com.example.util.MathHelper"
    }
    assert {n["fqn"] for n in result["downstream"]["nodes"]} == {
        "com.example.calc.AdvancedCalculator"
    }


def test_file_seed_resolves_all_entities_in_file(sample_graph):
    result = dependency_cone(
        sample_graph, "MathHelper.java", direction="downstream"
    )
    assert result["matched_by"] == "file"
    assert result["seed_entities"] == ["com.example.util.MathHelper"]
    assert result["downstream"]["num_nodes"] == 2


def test_files_rollup(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.util.MathHelper", direction="downstream"
    )
    assert result["downstream"]["files"] == [
        "AdvancedCalculator.java",
        "Calculator.java",
    ]


def test_max_depth_bounds_walk(sample_graph):
    # From MathHelper downstream: Calculator (d1) and AdvancedCalculator (d1);
    # AdvancedCalculator also reaches via Calculator at d2 but is already d1.
    result = dependency_cone(
        sample_graph, "com.example.util.MathHelper",
        direction="downstream", max_depth=1,
    )
    assert result["downstream"]["num_nodes"] == 2


def test_cycle_is_safe(sample_graph):
    # AdvancedCalculator -> Calculator and both -> MathHelper; ensure finite.
    result = dependency_cone(
        sample_graph, "com.example.calc.Calculator", direction="both", max_depth=10
    )
    assert isinstance(result["downstream"]["num_nodes"], int)


def test_max_nodes_truncates(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.util.MathHelper",
        direction="downstream", max_nodes=1,
    )
    assert result["downstream"]["truncated"] is True
    assert result["downstream"]["num_nodes"] == 1


def test_unresolved_target(sample_graph):
    result = dependency_cone(sample_graph, "does/not/exist.py")
    assert result["matched_by"] is None
    assert result["seed_entities"] == []
    assert "note" in result


def test_invalid_direction(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.calc.Calculator", direction="sideways"
    )
    assert "error" in result
    assert "both" in result["valid_directions"]
