---
name: improve-architecture-metrics
description: 'Improve arcade-agent architecture metrics and CI self-analysis results. Use when asked to improve RCI, TurboMQ, smell count, component structure, PR metric evolution, self-dogfooding CI comments, or architectural quality in this repository.'
argument-hint: 'Goal or constraint, for example: improve RCI without changing public API'
user-invocable: true
---

# Improve Architecture Metrics

Use this skill when the task is to improve the repository's architectural metrics, reduce detected smells, or make the PR self-analysis comment show better evolution against baseline.

This skill is specific to this repository. It uses the existing self-analysis pipeline in `scripts/run_self_analysis.py`, the baseline comparison in `scripts/compare_baseline.py`, and the CI workflow in `.github/workflows/ci.yml`.

## Primary Goals

- Increase `RCI` and `TurboMQ` where possible.
- Reduce architectural smells, especially `Concern Overload`.
- Reduce unnecessary cross-component coupling and noisy dependency edges.
- Preserve correctness: tests, lint, and public behavior still matter more than cosmetic metric gains.

## Metric Semantics

Treat these as the default optimization direction unless the task says otherwise.

- `RCI`: higher is better.
- `TurboMQ`: higher is better.
- `BasicMQ`: higher is better.
- `InterConnectivity`: lower is usually better.
- `TwoWayPairRatio`: lower is better.
- `Concern Overload` smell count: lower is better.
- `Components`, `Entities`, `Edges`: neutral by themselves; interpret them only in architectural context.
- `IntraConnectivity`: context-sensitive. Do not optimize it in isolation.

## Workflow

1. Establish the current baseline.
   Run the local self-analysis first:

   ```bash
   python scripts/run_self_analysis.py --output-json arcade_analysis_results.json --output-html arcade_analysis_report.html
   ```

2. Read the result before changing code.
   Focus on:
   - `metrics`
   - `smells`
   - component sizes and balance
   - suspicious parser edges or over-grouped recovery output

3. Identify root-cause improvements.
   Prefer changes that actually improve architecture quality, for example:
   - remove false-positive dependency edges
   - reduce component overlap or accidental coupling
   - improve package-based recovery grouping
   - split logic that causes `Concern Overload`
   - tighten CI summary logic so the PR comment reflects improvement correctly

4. Make the smallest meaningful code change.
   Avoid gaming the metrics with changes that make the code worse or harder to maintain.

5. Re-run verification.
   Use the repo's normal validation flow:

   ```bash
   pytest
   ruff check src/ tests/
   python scripts/run_self_analysis.py --output-json arcade_analysis_results.json --output-html arcade_analysis_report.html
   ```

6. Compare before and after when a baseline file is available.

   ```bash
   python scripts/compare_baseline.py arcade_analysis_results.json baseline.json --output pr_comment.md
   ```

7. Report outcome in terms of actual deltas.
   State which metrics improved, which regressed, and what code change caused the movement.

## Decision Rules

- Do not claim improvement without rerunning the self-analysis.
- Do not optimize only the comment format if the request is about real architectural quality.
- If metrics conflict, prioritize correctness and smell reduction over superficial score movement.
- If the best fix is structural and large, explain the tradeoff and stage it in small safe steps.
- If a metric goes down for a good architectural reason, say so explicitly.

## Repository-Specific Targets

- Python parser dependency extraction in `src/arcade_agent/parsers/python.py`
- Recovery/grouping behavior in `src/arcade_agent/tools/recover.py`
- Metric presentation and CI comment generation in `scripts/compare_baseline.py`
- Self-analysis pipeline in `.github/workflows/ci.yml`

## Good Task Triggers

- improve the metrics
- improve RCI
- reduce smell count
- improve TurboMQ
- make PR self-analysis look better
- reduce concern overload
- improve architecture quality
- improve CI metric evolution comment

## Expected Output

After using this skill, provide:

- the code changes made
- the metrics before and after
- any smells added or removed
- whether CI/PR comment behavior changed
- remaining risks or next structural improvements