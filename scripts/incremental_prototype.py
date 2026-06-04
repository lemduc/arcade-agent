#!/usr/bin/env python3
"""Prototype harness for incremental Python parsing.

1. Generates a synthetic large Python project (N modules with cross-imports).
2. EQUIVALENCE: asserts the incremental parse yields an identical graph to a full
   parse — cold (empty cache), warm (unchanged), and after editing one file.
3. BENCHMARK: times a cold full parse vs a warm incremental parse where one file
   changed, to show the re-analysis cost after a single edit.

Run with arcade-agent's venv interpreter:
    python scripts/incremental_prototype.py [--files 800]
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arcade_agent.incremental import ExtractCache
from arcade_agent.parsers.python import PythonParser


def gen_project(root: Path, n: int, pkgs: int = 10) -> list[Path]:
    """Create n modules across `pkgs` packages; each imports a class from the
    next module so the graph has real cross-file edges."""
    files = []
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "app" / "__init__.py").write_text("")
    for p in range(pkgs):
        (root / "app" / f"pkg{p}").mkdir(exist_ok=True)
        (root / "app" / f"pkg{p}" / "__init__.py").write_text("")
    for i in range(n):
        p = i % pkgs
        nxt = (i + 1) % n
        np = nxt % pkgs
        f = root / "app" / f"pkg{p}" / f"mod{i}.py"
        # A more realistic module: several classes (each with methods) + helpers,
        # so per-file parse cost reflects real source, not a 5-line toy.
        body = [f"from app.pkg{np}.mod{nxt} import Klass{nxt}\n"]
        for c in range(4):
            body.append(f"\nclass Klass{i}_{c}:")
            body.append("    def __init__(self, x=0):")
            body.append("        self.x = x")
            for m in range(5):
                body.append(f"    def method_{m}(self, a, b):")
                body.append(f"        y = Klass{nxt}()")
                body.append(f"        return self.x + a + b + {m} + helper{i}(a)")
        body.append(f"\ndef helper{i}(x):")
        body.append("    total = 0")
        for k in range(8):
            body.append(f"    total += x * {k}")
        body.append("    return total\n")
        # keep one top-level Klass{i} so the cross-import target name resolves
        body.append(f"\nclass Klass{i}(Klass{i}_0):\n    pass\n")
        f.write_text("\n".join(body))
        files.append(f)
    return files


def signature(g) -> tuple:
    """A comparable, order-independent signature of a DependencyGraph."""
    ents = tuple(sorted(
        (e.fqn, e.name, e.kind, e.package, e.file_path, e.superclass,
         tuple(e.interfaces or []), tuple(sorted(e.imports or [])))
        for e in g.entities.values()
    ))
    edges = tuple(sorted((e.source, e.target, e.relation) for e in g.edges))
    pkgs = tuple(sorted((k, tuple(sorted(v))) for k, v in g.packages.items()))
    return (ents, edges, pkgs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=800)
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="incr_proto_"))
    try:
        root = tmp / "proj"
        files = gen_project(root, args.files)
        parser = PythonParser()
        print(f"Generated {len(files)} modules under {root}")

        # ---- EQUIVALENCE -----------------------------------------------------
        full = parser.parse(files, root)
        cache = ExtractCache(root)
        incr_cold = parser.parse_incremental(files, root, cache)        # cold cache
        incr_warm = parser.parse_incremental(files, root, ExtractCache(root))  # warm

        ok_cold = signature(full) == signature(incr_cold)
        ok_warm = signature(full) == signature(incr_warm)

        # Edit one file, re-run incremental; compare to a fresh full parse.
        edited = files[len(files) // 2]
        edited.write_text(edited.read_text() + "\nEXTRA = 42\n")
        full_after = parser.parse(files, root)
        incr_after = parser.parse_incremental(files, root, ExtractCache(root))
        ok_edit = signature(full_after) == signature(incr_after)

        print("\n=== EQUIVALENCE (incremental graph == full graph) ===")
        print(f"  cold cache        : {'PASS' if ok_cold else 'FAIL'}")
        print(f"  warm (unchanged)  : {'PASS' if ok_warm else 'FAIL'}")
        print(f"  after 1-file edit : {'PASS' if ok_edit else 'FAIL'}")
        print(f"  graph size        : {full.num_entities} entities, {full.num_edges} edges")

        # ---- BENCHMARK -------------------------------------------------------
        # Restore + a clean warm cache, then change exactly one file.
        edited.write_text(edited.read_text())  # no-op write to bump nothing
        bench_cache = ExtractCache(tmp / "proj_bench_cache")

        t0 = time.perf_counter()
        parser.parse(files, root)                          # cold full parse
        cold = time.perf_counter() - t0

        # warm the incremental cache once
        parser.parse_incremental(files, root, bench_cache)
        warm_stats_seed = dict(bench_cache.stats)
        # now change ONE file and re-run incrementally
        edited.write_text(edited.read_text() + "\nANOTHER = 1\n")
        bench_cache.stats = {"reused": 0, "extracted": 0}
        t0 = time.perf_counter()
        parser.parse_incremental(files, root, bench_cache)  # warm: 1 file changed
        warm = time.perf_counter() - t0

        print("\n=== BENCHMARK ===")
        print(f"  cold full parse           : {cold*1000:8.1f} ms  ({len(files)} files)")
        print(f"  warm incremental (1 edit) : {warm*1000:8.1f} ms  "
              f"(reused {bench_cache.stats['reused']}, re-extracted "
              f"{bench_cache.stats['extracted']})")
        if warm > 0:
            print(f"  speedup                   : {cold/warm:8.1f}x")

        all_ok = ok_cold and ok_warm and ok_edit
        print(f"\nRESULT: {'ALL EQUIVALENCE CHECKS PASS' if all_ok else 'EQUIVALENCE FAILURE'}")
        sys.exit(0 if all_ok else 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
