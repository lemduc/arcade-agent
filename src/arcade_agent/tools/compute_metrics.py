"""Tool: Compute architecture quality metrics."""

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.coupling import compute_all_metrics
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool


@tool(
    name="compute_metrics",
    description="Calculate architecture quality metrics including RCI, TurboMQ, "
    "BasicMQ, connectivity, and coupling ratios.",
)
def compute_metrics(
    architecture: Architecture,
    dep_graph: DependencyGraph,
) -> list[MetricResult]:
    """Compute architecture quality metrics.

    Calculates 6 decay metrics from ARCADE Core:
    - RCI: Ratio of Cohesive Interactions (higher = more cohesive)
    - TurboMQ: Modularization Quality (higher = better modularization)
    - BasicMQ: Basic Modularization Quality (higher = better)
    - IntraConnectivity: Average internal connection density (higher = better)
    - InterConnectivity: Average external coupling density (lower = better)
    - TwoWayPairRatio: Fraction of bidirectional deps (lower = cleaner layering)

    Args:
        architecture: The recovered architecture.
        dep_graph: The dependency graph.

    Returns:
        List of MetricResult objects.
    """
    return compute_all_metrics(architecture, dep_graph)
