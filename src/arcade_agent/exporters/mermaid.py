"""Mermaid.js diagram generation.

``mermaid_node_id`` and ``mermaid_label_text`` are the single source of truth for
turning a component name into Mermaid syntax. Every emitter in the codebase must
use them: an id built one way here and another way elsewhere produces edges that
point at nodes which were never declared.
"""

import hashlib

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.parsers.graph import DependencyGraph

MERMAID_ID_MAX_LEN = 48
MERMAID_LABEL_NAME_MAX_LEN = 48
_MERMAID_DIGEST_LEN = 6


def _name_digest(name: str) -> str:
    """Return a short stable digest so truncated/empty names stay distinguishable."""
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:_MERMAID_DIGEST_LEN]


def _cap_with_digest(value: str, name: str, max_len: int) -> str:
    """Truncate ``value`` to ``max_len``, appending a digest of the full ``name``.

    Plain truncation would merge two components that share a long prefix, so the
    digest keeps the result unique even after the visible part is cut.
    """
    if len(value) <= max_len:
        return value
    keep = max_len - _MERMAID_DIGEST_LEN - 1
    return f"{value[:keep]}_{_name_digest(name)}"


def mermaid_node_id(name: str) -> str:
    """Build a safe, unique-per-name Mermaid node identifier."""
    nid = name.replace(" ", "_").replace("-", "_").replace(".", "_")
    nid = "".join(char for char in nid if char.isalnum() or char == "_")
    if not nid:
        # Symbol-only names all sanitize to nothing; without the digest every
        # such component would share a single node.
        return f"unnamed_{_name_digest(name)}"
    if nid[0].isdigit():
        # Mermaid parses a leading digit as the start of a number, not an id.
        nid = f"n_{nid}"
    return _cap_with_digest(nid, name, MERMAID_ID_MAX_LEN)


def mermaid_label_text(name: str) -> str:
    """Escape a component name for use inside a quoted Mermaid node label."""
    capped = _cap_with_digest(name, name, MERMAID_LABEL_NAME_MAX_LEN)
    # `#` must be escaped first, otherwise it would corrupt the `#quot;` entity.
    return capped.replace("#", "#35;").replace('"', "#quot;")


def _node_id(name: str) -> str:
    """Backwards-compatible alias for :func:`mermaid_node_id`."""
    return mermaid_node_id(name)


def build_mermaid_diagram(
    architecture: Architecture,
    dep_graph: DependencyGraph,
) -> str:
    """Build a Mermaid.js flowchart of the architecture.

    Args:
        architecture: The recovered architecture.
        dep_graph: The dependency graph.

    Returns:
        Mermaid diagram source string.
    """
    lines = ["graph TD"]

    for comp in architecture.components:
        nid = mermaid_node_id(comp.name)
        label = f"{mermaid_label_text(comp.name)}\\n({len(comp.entities)} entities)"
        lines.append(f"    {nid}[\"{label}\"]")

    comp_deps = architecture.component_dependencies(dep_graph)
    seen_edges: set[tuple[str, str]] = set()
    for src, tgt in comp_deps:
        edge_key = (mermaid_node_id(src), mermaid_node_id(tgt))
        if edge_key not in seen_edges:
            lines.append(f"    {edge_key[0]} --> {edge_key[1]}")
            seen_edges.add(edge_key)

    return "\n".join(lines)
