"""Tool: Compare architectures across versions (A2A analysis)."""

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.matching import compute_a2a_similarity, match_components
from arcade_agent.tools.registry import tool


@tool(
    name="compare",
    description="Compare two architectures (A2A analysis). Matches components using "
    "the Hungarian algorithm and tracks additions, removals, splits, and merges.",
)
def compare(
    arch_a: Architecture,
    arch_b: Architecture,
) -> dict:
    """Compare two architectures and report differences.

    Uses the Hungarian algorithm to find optimal component matching based
    on entity overlap, then reports additions, removals, and changes.

    Args:
        arch_a: Source architecture (e.g., version N).
        arch_b: Target architecture (e.g., version N+1).

    Returns:
        Dict with overall similarity, component matches, and summary stats.
    """
    matches = match_components(arch_a, arch_b)
    overall_similarity = compute_a2a_similarity(arch_a, arch_b)

    # Classify changes
    matched = [m for m in matches if m["source"] and m["target"]]
    added = [m for m in matches if not m["source"]]
    removed = [m for m in matches if not m["target"]]

    # Detect splits and merges
    splits = []
    merges = []
    for m in matched:
        if m["similarity"] < 0.5 and len(m["entities_added"]) > len(m["entities_removed"]):
            merges.append(m)
        elif m["similarity"] < 0.5 and len(m["entities_removed"]) > len(m["entities_added"]):
            splits.append(m)

    return {
        "overall_similarity": overall_similarity,
        "matches": matches,
        "summary": {
            "total_matches": len(matched),
            "components_added": len(added),
            "components_removed": len(removed),
            "possible_splits": len(splits),
            "possible_merges": len(merges),
            "arch_a_components": len(arch_a.components),
            "arch_b_components": len(arch_b.components),
        },
    }
