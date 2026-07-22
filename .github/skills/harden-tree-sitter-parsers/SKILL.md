---
name: harden-tree-sitter-parsers
description: Harden new or changed tree-sitter parsers against adversarial nesting, malformed files, partial-state leaks, and stale non-source cache inputs.
reliability: validated-2x
---

# Harden Tree-sitter Parsers

Use this skill for new parser implementations, parser reviews, recursion failures,
or changes to AST traversal and linking.

## Required workflow

1. Inventory every AST traversal helper and classify it as iterative or recursive.
2. Replace source-depth recursion with an explicit stack or queue. Preserve traversal
   order deliberately and avoid repeated tuple/list copying where practical.
3. Extract each file into isolated temporary state. Merge entities, edges, imports,
   packages, and pending links only after the file succeeds.
4. Log skipped files with the failure class; do not silently discard valid siblings.
5. Add adversarial fixtures deeper than `sys.getrecursionlimit()` for every distinct
   traversal shape. Each fixture must be parsed beside a valid sibling file.
6. Test cache invalidation for manifests or configuration that changes graph identity.
7. Run, in order:
   - focused parser and cache tests;
   - Ruff and the full test suite;
   - a large real repository for the target language;
   - arcade-agent self-analysis before/after, reporting metric and smell deltas.
8. Record any newly discovered reusable failure class in `docs/BUG_CATALOG.md`.

## Acceptance invariants

- No `RecursionError` for valid tree-sitter AST depth within the configured file limit.
- One malformed or adversarial file cannot erase healthy sibling entities.
- No partial entities from a failed file enter the final graph.
- No dangling edges, missing method owners, or duplicate package membership.
- Relevant non-source inputs invalidate cached graphs.
- Correctness and explicit failure behavior take precedence over cosmetic metric gains.

## Evidence

- Kotlin follow-up `b7effc5`: iterative deep-expression traversal and sibling survival.
- Rust PR #18: iterative path/use/module/type traversal, transactional file extraction,
  Cargo-aware cache invalidation, and adversarial regression matrix.
