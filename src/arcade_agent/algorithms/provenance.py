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


@dataclass(frozen=True)
class Split:
    """One component of the earlier architecture scattered into several later ones.

    Attributes:
        source: Component name in the earlier architecture.
        targets: Sorted later component names that received its entities.
        entities: Target component name -> number of entities received.
    """

    source: str
    targets: tuple[str, ...]
    entities: dict[str, int]


@dataclass(frozen=True)
class Merge:
    """One component of the later architecture drawing from several earlier ones.

    Attributes:
        target: Component name in the later architecture.
        sources: Sorted earlier component names that contributed entities.
        entities: Source component name -> number of entities contributed.
    """

    target: str
    sources: tuple[str, ...]
    entities: dict[str, int]


@dataclass(frozen=True)
class StructuralChanges:
    """Disjoint classification of components across two architectures.

    The **classification** is the six top-level buckets, and it is disjoint:
    every component of the earlier architecture is in exactly one of
    ``removed``, ``split``, ``renamed`` or ``stable``, or is absorbed into a
    ``merged`` entry. Every component of the later architecture is in exactly
    one of ``added``, ``merged``, ``renamed`` or ``stable``, or is a split
    product of a ``split`` entry.

    ``Split.targets`` and ``Merge.sources`` are **descriptive provenance, not
    classification**, and may legitimately name a component that is itself
    classified elsewhere. For example, if ``S`` splits into ``S`` and ``T``,
    and ``T`` separately also draws significant entities from an unrelated
    ``X``, then ``T`` is a genuine merge target with ``sources=("S", "X")`` —
    even though ``S`` is independently reported as a ``split`` entry's
    ``source``. Suppressing ``S`` from ``T``'s sources to force a stricter
    partition would misreport where half of ``T``'s entities came from, which
    is worse than the double-naming. The one-bucket-per-component guarantee
    applies to the six top-level fields only, not to the names nested inside
    ``Split.targets`` / ``Merge.sources``.
    """

    added: tuple[str, ...]
    removed: tuple[str, ...]
    renamed: tuple[tuple[str, str], ...]
    split: tuple[Split, ...]
    merged: tuple[Merge, ...]
    stable: tuple[str, ...]
    flows: tuple[Flow, ...]
    rename_map: dict[str, str]


def classify_structural_changes(
    arch_a: Architecture,
    arch_b: Architecture,
    *,
    min_entities: int = 3,
    min_share: float = 0.20,
) -> StructuralChanges:
    """Classify components into disjoint structural buckets.

    A flow is significant when it carries at least *min_entities* entities, or
    at least *min_share* of the smaller of its two endpoint components measured
    at its own version. Splits and merges take precedence over renames so that
    no structural event is reported twice.

    Args:
        arch_a: The earlier architecture.
        arch_b: The later architecture.
        min_entities: Absolute entity count at which a flow becomes significant.
        min_share: Fractional threshold in (0, 1] as an alternative trigger.

    Returns:
        A StructuralChanges with every field sorted deterministically.

    Raises:
        ValueError: If *min_share* is outside (0, 1].
    """
    if not 0 < min_share <= 1:
        raise ValueError(f"min_share must be in (0, 1], got {min_share}")

    flows = entity_flows(arch_a, arch_b)
    size_a = {c.name: len(c.entities) for c in arch_a.components}
    size_b = {c.name: len(c.entities) for c in arch_b.components}

    def is_significant(flow: Flow) -> bool:
        count = len(flow.entities)
        if count >= min_entities:
            return True
        denominator = min(size_a.get(flow.source, 0), size_b.get(flow.target, 0))
        return denominator > 0 and count / denominator >= min_share

    outgoing: dict[str, list[Flow]] = {}
    incoming: dict[str, list[Flow]] = {}
    for flow in flows:
        if not is_significant(flow):
            continue
        outgoing.setdefault(flow.source, []).append(flow)
        incoming.setdefault(flow.target, []).append(flow)

    split_sources = {name for name, fs in outgoing.items() if len(fs) >= 2}
    merge_targets = {name for name, fs in incoming.items() if len(fs) >= 2}

    splits = tuple(
        Split(
            source=name,
            targets=tuple(sorted(f.target for f in outgoing[name])),
            entities={
                f.target: len(f.entities)
                for f in sorted(outgoing[name], key=lambda f: f.target)
            },
        )
        for name in sorted(split_sources)
    )
    merges = tuple(
        Merge(
            target=name,
            sources=tuple(sorted(f.source for f in incoming[name])),
            entities={
                f.source: len(f.entities)
                for f in sorted(incoming[name], key=lambda f: f.source)
            },
        )
        for name in sorted(merge_targets)
    )

    # Precedence: a lone flow into a merge target means the source was absorbed,
    # not renamed. It is reported inside the merge entry only.
    absorbed = {
        name
        for name, fs in outgoing.items()
        if name not in split_sources and fs[0].target in merge_targets
    }

    renamed: list[tuple[str, str]] = []
    stable: list[str] = []
    for name in sorted(outgoing):
        if name in split_sources or name in absorbed:
            continue
        target = outgoing[name][0].target
        # A lone flow out of a split source makes the target a split product,
        # already reported inside the split entry.
        if len(incoming.get(target, [])) != 1:
            continue
        if name == target:
            stable.append(name)
        else:
            renamed.append((name, target))

    removed = tuple(
        c.name for c in arch_a.components if not outgoing.get(c.name)
    )
    added = tuple(c.name for c in arch_b.components if not incoming.get(c.name))

    rename_map = {source: target for source, target in renamed}
    rename_map.update({name: name for name in stable})

    return StructuralChanges(
        added=tuple(sorted(added)),
        removed=tuple(sorted(removed)),
        renamed=tuple(renamed),
        split=splits,
        merged=merges,
        stable=tuple(stable),
        flows=flows,
        rename_map=rename_map,
    )
