"""Entity provenance between two recovered architectures.

Answers "where did this component's entities come from", which is a
many-to-many question the 1:1 Hungarian matching in ``matching.py`` cannot
express. Used to classify splits and merges without double counting.
"""

from dataclasses import dataclass

from arcade_agent.algorithms.architecture import Architecture


@dataclass(frozen=True)
class Flow:
    """Entities that moved from one component to another between two versions.

    Attributes:
        source: Component name in the earlier architecture.
        target: Component name in the later architecture.
        entities: Sorted FQNs present in both architectures that took this path.
    """

    source: str
    target: str
    entities: tuple[str, ...]


def entity_flows(arch_a: Architecture, arch_b: Architecture) -> tuple[Flow, ...]:
    """Attribute every entity present in both architectures to a component pair.

    Entities present in only one architecture produce no flow: they are
    additions or deletions, not movements.

    Args:
        arch_a: The earlier architecture.
        arch_b: The later architecture.

    Returns:
        Flows sorted by (source, target), each with sorted entities.
    """
    membership_a = arch_a.membership()
    membership_b = arch_b.membership()

    buckets: dict[tuple[str, str], list[str]] = {}
    for fqn, source in membership_a.items():
        target = membership_b.get(fqn)
        if target is None:
            continue
        buckets.setdefault((source, target), []).append(fqn)

    return tuple(
        Flow(source=source, target=target, entities=tuple(sorted(entities)))
        for (source, target), entities in sorted(buckets.items())
    )
