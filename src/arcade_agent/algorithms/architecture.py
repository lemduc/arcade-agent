"""Architecture data models."""

from dataclasses import dataclass, field

from arcade_agent.parsers.graph import DependencyGraph


@dataclass
class Component:
    """A recovered architectural component."""

    name: str
    responsibility: str
    entities: list[str] = field(default_factory=list)  # FQNs


@dataclass
class Architecture:
    """A recovered software architecture."""

    components: list[Component] = field(default_factory=list)
    rationale: str = ""
    algorithm: str = ""  # pkg, wca, acdc, llm
    metadata: dict = field(default_factory=dict)

    def membership(self) -> dict[str, str]:
        """Build an entity-FQN to component-name index.

        The index is computed on demand so it cannot become stale when callers
        mutate components. ``setdefault`` preserves ``component_of``'s existing
        first-component-wins behavior for malformed architectures that contain
        the same entity more than once.
        """
        membership: dict[str, str] = {}
        for component in self.components:
            for fqn in component.entities:
                membership.setdefault(fqn, component.name)
        return membership

    def component_of(self, fqn: str) -> str | None:
        """Find which component an entity belongs to."""
        for comp in self.components:
            if fqn in comp.entities:
                return comp.name
        return None

    def component_dependencies(
        self, dep_graph: DependencyGraph
    ) -> list[tuple[str, str]]:
        """Compute component-level dependencies from entity-level edges."""
        membership = self.membership()
        comp_edges: set[tuple[str, str]] = set()
        for edge in dep_graph.edges:
            src_comp = membership.get(edge.source)
            tgt_comp = membership.get(edge.target)
            if src_comp and tgt_comp and src_comp != tgt_comp:
                comp_edges.add((src_comp, tgt_comp))
        return sorted(comp_edges)
