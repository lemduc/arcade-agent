# Parser Robustness Bug Catalog

Reliability: `validated-2x`

This is the living catalog for parser failure classes that can abort or distort
whole-repository analysis. Entries use reproducible fixtures and design-time
prevention rules so the same defect is not rediscovered language by language.

## Design-time checklist

- Traverse untrusted AST depth with explicit stacks or queues, never Python recursion.
- Put every file extraction behind a transactional boundary: publish its entities only
  after extraction succeeds.
- Test nesting deeper than `sys.getrecursionlimit()` for every traversal shape.
- Pair each poisoned input with a healthy sibling file and assert the sibling survives.
- Track non-source inputs such as manifests when they affect graph identity or cache keys.
- Do not add per-parser input caps (file size, node counts) as a stand-in for robustness:
  they drop real code silently, diverge from the other parsers, and never fix the
  traversal defect they appear to mitigate. The per-file exception boundary is the backstop.
- Run focused tests, the full suite, a large real repository, and arcade-agent's own
  self-analysis before publishing parser changes.

## 1. Kotlin deep-expression traversal aborted repository analysis

- **Symptom:** A machine-generated expression with thousands of nested parentheses
  raised `RecursionError`; valid sibling files disappeared because parsing aborted.
- **Root cause:** Recursive AST descent treated source nesting as trusted call-stack depth.
- **Detection:** Parse a deeply nested Kotlin file beside a valid file and assert the
  valid entity remains in the graph.
- **Fix:** Replace recursive descent with explicit stacks and isolate failures per file.
- **Prevention:** Apply the parser hardening skill to every new or materially changed
  tree-sitter traversal.
- First encountered: Kotlin parser follow-up `b7effc5`.
- **Pattern note:** First confirmed instance of cross-language AST depth fragility.

## 2. Rust path/use/module/type traversals repeated the recursion defect

- **Symptom:** Roughly 1,000 nested path segments, use groups, inline modules, or type
  wrappers raised `RecursionError` and killed analysis for healthy sibling files.
- **Root cause:** Four helpers used recursive descent even though `_references` already
  demonstrated the safe iterative pattern; extraction also ran outside the file-level
  exception boundary.
- **Detection:** Parameterize all four AST shapes above the Python recursion limit and
  parse each beside a valid Rust file.
- **Fix:** Use explicit LIFO worklists, publish per-file extraction state transactionally,
  and log-and-skip unexpected file-level failures.
- **Prevention:** Require the shared adversarial matrix and self-dogfood before parser PRs.
- First encountered: Rust parser PR #18 review, 2026-07-21.
- **Pattern note:** Second confirmed cross-language instance. Keep the class on the
  design checklist; wait for a third instance before naming a broader meta-pattern.
