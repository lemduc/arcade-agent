"""Tests for the diff_impact tool."""

import pytest

from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity
from arcade_agent.tools.diff_impact import _basename, _paths_match, diff_impact


def test_basename():
    assert _basename("a/b/c.java") == "c.java"
    assert _basename("c.java") == "c.java"
    assert _basename("a\\b\\c.java") == "c.java"


def test_paths_match_exact():
    assert _paths_match("MathHelper.java", "MathHelper.java")


def test_paths_match_suffix():
    assert _paths_match("MathHelper.java", "src/main/java/MathHelper.java")
    assert _paths_match("src/main/java/MathHelper.java", "MathHelper.java")


def test_paths_match_basename():
    assert _paths_match("src/util/MathHelper.java", "other/MathHelper.java")


def test_paths_match_no_match():
    assert not _paths_match("MathHelper.java", "Calculator.java")


def test_diff_impact_happy_path(sample_graph, sample_architecture):
    result = diff_impact(
        sample_graph, ["MathHelper.java"], architecture=sample_architecture,
    )
    assert result["matched_files"] == ["MathHelper.java"]
    assert result["unmatched_files"] == []
    assert result["num_changed_entities"] == 1
    assert result["changed_entities"][0]["fqn"] == "com.example.util.MathHelper"
    # Both calculators depend on MathHelper.
    assert result["affected_components"] == ["Util"]
    dep_fqns = {d["fqn"] for d in result["downstream_dependents"]}
    assert dep_fqns == {
        "com.example.calc.Calculator",
        "com.example.calc.AdvancedCalculator",
    }
    assert result["num_downstream"] == 2
    for d in result["downstream_dependents"]:
        assert d["distance"] == 1
        assert d["via_relation"] == "import"


def test_diff_impact_broken_contracts(sample_graph):
    result = diff_impact(sample_graph, ["MathHelper.java"])
    assert len(result["broken_contracts"]) == 1
    contract = result["broken_contracts"][0]
    assert contract["fqn"] == "com.example.util.MathHelper"
    assert contract["num_dependents"] == 2
    assert "com.example.calc.Calculator" in contract["dependents"]


def test_diff_impact_via_relation_extends(sample_graph):
    # Changing Calculator: AdvancedCalculator extends it.
    result = diff_impact(sample_graph, ["Calculator.java"])
    assert result["num_downstream"] == 1
    dep = result["downstream_dependents"][0]
    assert dep["fqn"] == "com.example.calc.AdvancedCalculator"
    assert dep["via_relation"] == "extends"


def test_diff_impact_tolerant_path(sample_graph):
    # A full repo-relative path should still match the bare file name.
    result = diff_impact(sample_graph, ["src/main/java/com/example/util/MathHelper.java"])
    assert result["matched_files"] == [
        "src/main/java/com/example/util/MathHelper.java"
    ]
    assert result["num_changed_entities"] == 1


def test_diff_impact_no_match(sample_graph):
    result = diff_impact(sample_graph, ["Nonexistent.java"])
    assert result["matched_files"] == []
    assert result["unmatched_files"] == ["Nonexistent.java"]
    assert result["num_changed_entities"] == 0
    assert result["downstream_dependents"] == []
    assert result["broken_contracts"] == []


def test_diff_impact_empty_input(sample_graph):
    result = diff_impact(sample_graph, [])
    assert result["changed_files"] == []
    assert result["matched_files"] == []
    assert result["unmatched_files"] == []
    assert result["num_changed_entities"] == 0
    assert result["affected_components"] == []


def test_diff_impact_no_architecture(sample_graph):
    result = diff_impact(sample_graph, ["MathHelper.java"])
    # Without architecture, affected_components is empty but analysis still runs.
    assert result["affected_components"] == []
    assert result["num_downstream"] == 2


@pytest.fixture
def chain_graph():
    """A linear dependency chain A -> B -> C -> D (source depends on target)."""
    entities = {}
    for name in ("A", "B", "C", "D"):
        fqn = f"d.{name}"
        entities[fqn] = Entity(
            fqn=fqn,
            name=name,
            package="d",
            file_path=f"{name}.py",
            kind="class",
            language="python",
        )
    edges = [
        Edge(source="d.A", target="d.B", relation="calls"),
        Edge(source="d.B", target="d.C", relation="calls"),
        Edge(source="d.C", target="d.D", relation="calls"),
    ]
    return DependencyGraph(
        entities=entities, edges=edges, packages={"d": list(entities)}
    )


def test_diff_impact_depth_cap(chain_graph):
    # Changing D at max_depth=2 reaches C (dist1) and B (dist2) but not A.
    result = diff_impact(chain_graph, ["D.py"], max_depth=2)
    by_fqn = {d["fqn"]: d for d in result["downstream_dependents"]}
    assert set(by_fqn) == {"d.C", "d.B"}
    assert by_fqn["d.C"]["distance"] == 1
    assert by_fqn["d.B"]["distance"] == 2
    # First-hop relation is preserved across hops.
    assert by_fqn["d.B"]["via_relation"] == "calls"


def test_diff_impact_full_depth(chain_graph):
    result = diff_impact(chain_graph, ["D.py"], max_depth=3)
    by_fqn = {d["fqn"]: d for d in result["downstream_dependents"]}
    assert by_fqn["d.A"]["distance"] == 3


@pytest.fixture
def cyclic_graph():
    """A 2-node cycle A <-> B to verify traversal terminates."""
    entities = {
        "c.A": Entity(
            fqn="c.A", name="A", package="c", file_path="A.py",
            kind="class", language="python",
        ),
        "c.B": Entity(
            fqn="c.B", name="B", package="c", file_path="B.py",
            kind="class", language="python",
        ),
    }
    edges = [
        Edge(source="c.A", target="c.B", relation="uses"),
        Edge(source="c.B", target="c.A", relation="uses"),
    ]
    return DependencyGraph(
        entities=entities, edges=edges, packages={"c": list(entities)}
    )


def test_diff_impact_cycle_terminates(cyclic_graph):
    # Must not infinite-loop; B depends on A, and A depends on B (excluded as changed).
    result = diff_impact(cyclic_graph, ["A.py"])
    assert result["num_downstream"] == 1
    assert result["downstream_dependents"][0]["fqn"] == "c.B"
