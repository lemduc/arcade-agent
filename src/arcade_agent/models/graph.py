"""Dependency graph data models."""

from dataclasses import dataclass, field


@dataclass
class Entity:
    """A source code entity (class, interface, function, module, etc.)."""

    fqn: str
    name: str
    package: str
    file_path: str
    kind: str  # class, interface, enum, function, module
    language: str
    imports: list[str] = field(default_factory=list)
    superclass: str | None = None
    interfaces: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)


@dataclass
class Edge:
    """A dependency edge between two entities."""

    source: str  # FQN
    target: str  # FQN
    relation: str  # import, extends, implements, calls, uses


@dataclass
class DependencyGraph:
    """Dependency graph extracted from source code."""

    entities: dict[str, Entity] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    packages: dict[str, list[str]] = field(default_factory=dict)

    @property
    def num_entities(self) -> int:
        return len(self.entities)

    @property
    def num_edges(self) -> int:
        return len(self.edges)

    def to_adjacency(self) -> dict[str, list[str]]:
        """Convert to adjacency list (ignoring edge types)."""
        adj: dict[str, list[str]] = {fqn: [] for fqn in self.entities}
        for edge in self.edges:
            if edge.source in adj:
                adj[edge.source].append(edge.target)
        return adj

    def to_edge_tuples(self) -> list[tuple[str, str, str]]:
        """Convert edges to tuples for compatibility."""
        return [(e.source, e.target, e.relation) for e in self.edges]

    def merge(self, other: "DependencyGraph") -> "DependencyGraph":
        """Merge another graph into this one, returning a new graph."""
        entities = {**self.entities, **other.entities}
        edges = self.edges + other.edges
        packages: dict[str, list[str]] = {}
        for pkg, fqns in self.packages.items():
            packages.setdefault(pkg, []).extend(fqns)
        for pkg, fqns in other.packages.items():
            packages.setdefault(pkg, []).extend(fqns)
        return DependencyGraph(entities=entities, edges=edges, packages=packages)
