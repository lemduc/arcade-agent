"""Tests for architecture membership and component dependency lookup."""

from arcade_agent.algorithms.architecture import Architecture, Component


def test_membership_matches_component_lookup_and_reflects_mutation(sample_architecture):
    entity = "com.example.calc.Calculator"

    assert sample_architecture.membership()[entity] == sample_architecture.component_of(entity)

    sample_architecture.components[0].entities.append("com.example.calc.NewCalculator")
    assert sample_architecture.membership()["com.example.calc.NewCalculator"] == "Calc"


def test_membership_preserves_first_component_for_duplicate_entity():
    architecture = Architecture(
        components=[
            Component(name="First", responsibility="", entities=["pkg.Entity"]),
            Component(name="Second", responsibility="", entities=["pkg.Entity"]),
        ]
    )

    assert architecture.component_of("pkg.Entity") == "First"
    assert architecture.membership()["pkg.Entity"] == "First"


def test_component_dependencies_uses_membership_index(sample_architecture, sample_graph):
    assert sample_architecture.component_dependencies(sample_graph) == [("Calc", "Util")]
