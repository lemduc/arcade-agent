"""Dogfooding benchmark for H1: Architecture.component_of linear scan.

Measures component_dependencies() on:
1. arcade-agent analyzing itself (real dogfood)
2. Synthetic scaled graphs (asymptotic proof)

Compares the current implementation vs a membership-index version,
and asserts both produce byte-identical results.
"""
import random
import time

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover


def component_dependencies_indexed(arch: Architecture, dep_graph: DependencyGraph):
    """Proposed O(n + E) implementation: build membership dict once."""
    m = {fqn: comp.name for comp in arch.components for fqn in comp.entities}
    comp_edges = {
        (m[e.source], m[e.target])
        for e in dep_graph.edges
        if e.source in m and e.target in m and m[e.source] != m[e.target]
    }
    return sorted(comp_edges)


def timeit(fn, *args, repeat=5):
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        result = fn(*args)
        best = min(best, time.perf_counter() - t0)
    return best, result


def synthetic(n_entities: int, n_components: int, edges_per_entity: int = 4):
    rng = random.Random(42)
    g = DependencyGraph()
    fqns = [f"pkg{i % n_components}.mod{i // 50}.Class{i}" for i in range(n_entities)]
    for i, fqn in enumerate(fqns):
        pkg = f"pkg{i % n_components}"
        g.entities[fqn] = Entity(
            fqn=fqn, name=f"Class{i}", package=pkg,
            file_path=f"{pkg}/f{i}.py", kind="class", language="python",
        )
    for fqn in fqns:
        for _ in range(edges_per_entity):
            g.edges.append(Edge(source=fqn, target=rng.choice(fqns), relation="import"))
    comps = [[] for _ in range(n_components)]
    for i, fqn in enumerate(fqns):
        comps[i % n_components].append(fqn)
    from arcade_agent.algorithms.architecture import Component
    arch = Architecture(
        components=[
            Component(name=f"Comp{c}", responsibility="", entities=members)
            for c, members in enumerate(comps)
        ],
        algorithm="synthetic",
    )
    return g, arch


print("=" * 72)
print("PART 1 — DOGFOOD: arcade-agent analyzing arcade-agent (src/arcade_agent)")
print("=" * 72)
graph = parse("src/arcade_agent", language="python")
arch = recover(graph, algorithm="pkg")
print(f"graph: {graph.num_entities} entities, {graph.num_edges} edges; "
      f"architecture: {len(arch.components)} components (pkg)")

t_old, r_old = timeit(arch.component_dependencies, graph, repeat=20)
t_new, r_new = timeit(lambda: component_dependencies_indexed(arch, graph), repeat=20)
assert r_old == r_new, "MISMATCH — results differ!"
print(f"current : {t_old*1000:8.3f} ms")
print(f"indexed : {t_new*1000:8.3f} ms")
print(f"speedup : {t_old/t_new:8.1f}x   (results identical: {r_old == r_new})")

print()
print("=" * 72)
print("PART 2 — SYNTHETIC SCALE-UP (asymptotic behaviour, edges = 4n)")
print("=" * 72)
print(f"{'n_entities':>10} {'n_comps':>8} {'current(ms)':>12} {'indexed(ms)':>12} {'speedup':>9} {'identical':>10}")
for n, c in [(500, 12), (2000, 25), (5000, 40), (10000, 60)]:
    g, a = synthetic(n, c)
    reps = 3 if n <= 5000 else 1
    t_o, r_o = timeit(a.component_dependencies, g, repeat=reps)
    t_n, r_n = timeit(lambda: component_dependencies_indexed(a, g), repeat=reps)
    print(f"{n:>10} {c:>8} {t_o*1000:>12.1f} {t_n*1000:>12.2f} {t_o/t_n:>8.0f}x {str(r_o==r_n):>10}")

print()
print("PART 3 — full-pipeline impact on dogfood repo "
      "(detect_smells + compute_metrics, which call component_dependencies internally)")
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.compute_metrics import compute_metrics

t0 = time.perf_counter()
smells = detect_smells(arch, graph)
metrics = compute_metrics(arch, graph)
t_pipeline = time.perf_counter() - t0
print(f"smells: {len(smells)}, metrics: {len(metrics)}, pipeline time: {t_pipeline*1000:.1f} ms "
      f"(n={graph.num_entities} — small repo, so H1 matters at scale, not here)")
