# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## Unreleased

Ships as **0.3.0** — the next release after 0.2.0. `pyproject.toml` still reads
`0.2.0`; it is bumped as part of cutting the GitHub release that the publish
workflow builds from, not ahead of it.

### Added

- `changelog_architecture` tool: an architectural changelog between two
  recovered versions of a codebase — components added, removed, renamed,
  split or merged; entities that changed component ("responsibility
  shifts"); smells gained or resolved; and metric deltas.
- `algorithms/provenance.py`: entity-provenance-based classification of
  structural change (`classify_structural_changes`), used by both `compare`
  and `changelog_architecture` so the two tools never disagree about which
  components were genuinely added, removed, split or merged.
- `ingest(ref=...)`: materialise a specific commit, tag or branch into a
  temporary tree via `git archive`, without touching the caller's working
  tree, index or HEAD.
- `arcade-arch-diff` now renders the architectural changelog inside its PR
  comment when a baseline exists.

### Breaking

- `compare`'s `summary.possible_splits` / `summary.possible_merges` keys are
  **removed**. Use `summary.splits` / `summary.merges` (counts) and the new
  `structural.split` / `structural.merged` (detail) instead.

  The old keys were derived from the Hungarian algorithm's 1:1 component
  matching (`similarity < 0.5` plus which side's entity count grew), which
  is structurally incapable of representing a split (one source component →
  multiple targets) or a merge (multiple sources → one target): a 1:1
  match can only ever report *one* target or *one* source per component. In
  practice this mislabelled ordinary renames as splits/merges by whichever
  way the entity count happened to move, and double-counted genuine splits
  as both a low-similarity match *and* a separate "added" component.

  `compare`'s return also gains an additive `structural` key — the same
  provenance-derived classification `changelog_architecture` uses — carrying
  the accurate `added` / `removed` / `renamed` / `split` / `merged` /
  `stable` component names. `matches` (the raw Hungarian 1:1 view) is
  unchanged. `summary.components_added` / `summary.components_removed` keep
  their keys but are now provenance-derived: a split product or a merge
  source no longer counts as added/removed, so consumers asserting on the
  old Hungarian-unmatched counts will see different numbers for those
  scenarios.

### Fixed

- `_clone_and_ingest` no longer leaks the cloned repository (including
  `.git`) when `_build_ingested_repo` narrows the ingested path to a
  detected source root (e.g. `src/main/java`); `cleanup()` now removes the
  whole clone.
- `render_changelog_markdown`'s embedded heading no longer collides with the
  drift report's own heading level (`## Architectural changes` inside a
  `## Architecture Drift Report` re-parented the report's `### Smells`
  section); it now accepts `heading_level` and `arcade-arch-diff` passes
  `heading_level=3`.
- `ingest(ref=...)` archives the `git rev-parse`-resolved SHA rather than
  the raw `ref` string, closing a TOCTOU window and a narrow argument-
  injection surface for refs beginning with `-`.

## 0.2.0 and earlier

See GitHub releases: https://github.com/lemduc/arcade-agent/releases
