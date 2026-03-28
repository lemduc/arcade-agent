"""RSF (Rigi Standard Format) export for ARCADE compatibility.

RSF is a simple text format used by architecture recovery tools:
    contain ComponentName entityFQN
"""

from arcade_agent.algorithms.architecture import Architecture


def export_rsf(architecture: Architecture) -> str:
    """Export architecture as RSF (Rigi Standard Format).

    Each line maps an entity to its containing component:
        contain ComponentName entityFQN

    Args:
        architecture: The recovered architecture.

    Returns:
        RSF format string.
    """
    lines = []
    for comp in architecture.components:
        for fqn in sorted(comp.entities):
            lines.append(f"contain {comp.name} {fqn}")
    return "\n".join(lines)
