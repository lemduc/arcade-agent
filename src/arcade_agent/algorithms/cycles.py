"""Strongly-connected-component based cycle detection."""

import networkx as nx

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.parsers.graph import DependencyGraph


def detect_dependency_cycles(
    architecture: Architecture,
    dep_graph: DependencyGraph,
) -> list[list[str]]:
    """Detect dependency cycles at the component level using Kosaraju's algorithm.

    Args:
        architecture: The recovered architecture.
        dep_graph: The dependency graph.

    Returns:
        List of cycles, where each cycle is a sorted list of component names.
    """
    G = nx.DiGraph()
    for comp in architecture.components:
        G.add_node(comp.name)
    for src_comp, tgt_comp in architecture.component_dependencies(dep_graph):
        G.add_edge(src_comp, tgt_comp)

    cycles = []
    for scc in nx.strongly_connected_components(G):
        if len(scc) > 1:
            cycles.append(sorted(scc))

    return cycles
