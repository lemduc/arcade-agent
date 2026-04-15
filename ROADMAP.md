# Roadmap: arcade-agent as an AI Agent Tool

Transform arcade-agent into a token-efficient codebase understanding layer for AI agents.

## Phase 1 — MCP Server (Foundation)

Make tools callable by any MCP-compatible agent (Claude Code, Cursor, etc.)

- [x] **1. Implement MCP server** — Expose tools via Model Context Protocol with session store for complex objects. Tools return compact summaries with session IDs; agents drill into details via `get_full_result`.
- [x] **2. Streaming responses** — Tools return summaries by default; full results retrievable on demand via `get_full_result` tool. Agents control how much data they consume.
- [x] **3. Token-budget parameter** — Every tool accepts an optional `max_tokens` hint. Progressive truncation (entity details → edge summaries → component counts) via `budget.py`.
- [x] **4. Cached parse results** — Cache `DependencyGraph` to JSON in `.arcade-cache/`. Keyed by file paths + mtimes. Auto-invalidates when source files change.

## Phase 2 — Token-Efficient Summaries

Give agents maximum understanding per token spent.

- [ ] **5. `summarize` tool** — Given a repo path, return a structured codebase overview: top-level modules, key classes, entry points, dependency hotspots. One call replaces reading dozens of files.
- [ ] **6. Hierarchical drill-down** — `summarize` returns a tree. Agent can drill into any node (`summarize(path, focus="com.foo.auth")`) for deeper detail without loading everything.
- [ ] **7. `explain_component` tool** — Given a component from recovered architecture, return: responsibility, key entities, public API surface, who depends on it, who it depends on.
- [ ] **8. `find_relevant` tool** — Natural-language query ("how does authentication work?") returns ranked list of files/classes/components using recovered architecture + concern tags.

## Phase 3 — Change-Aware Context

Help agents understand *what changed* and *what matters* without reading full diffs.

- [ ] **9. `diff_impact` tool** — Given a git diff/PR, map changed files to affected components, downstream dependencies, and potentially broken contracts.
- [ ] **10. `changelog_architecture` tool** — Given two commits/tags, produce an architectural changelog: new/removed components, shifted responsibilities, new smells.
- [ ] **11. `blame_component` tool** — Component-level ownership via git blame aggregation.

## Phase 4 — Smart Context Selection

Let agents ask "what do I need to read?" instead of reading everything.

- [ ] **12. `context_for_task` tool** — Input: natural-language task description. Output: minimal set of files the agent needs, ranked by relevance with brief role explanations.
- [ ] **13. `dependency_cone` tool** — Given an entity/file, return full upstream/downstream dependency cone with depth control.
- [ ] **14. `api_surface` tool** — Extract public interfaces only (public methods, exported functions, type signatures) without implementation details.

## Phase 5 — Multi-Language & Scale

Handle real-world polyglot monorepos.

- [ ] **15. TypeScript/JS parser** — Complete the existing stub. Critical for web projects.
- [ ] **16. Go and Rust parsers** — High-demand languages for agent-assisted development.
- [ ] **17. Incremental parsing** — Only re-parse changed files. Essential for large repos.
- [ ] **18. Cross-language dependency tracking** — Java↔Python via gRPC, TS frontend↔Java backend, etc.

## Phase 6 — Agent Protocol Integration

Work everywhere agents work.

- [ ] **19. OpenAI function-calling schema** — Auto-generate from existing registry type hints.
- [ ] **20. LangChain/LangGraph tool wrappers** — Thin adapter using the registry.
- [ ] **21. Claude Agent SDK integration** — Native tool definitions for the Agent SDK.
- [ ] **22. VS Code / IDE extension** — Expose tools as code actions or inline hints.

## Priority Order

| Priority | Items | Rationale |
|----------|-------|-----------|
| **Done** | 1, 2, 3, 4 | MCP server + caching + token budget (Phase 1 complete) |
| **Now** | 5, 6 | Summarize tool + hierarchical drill-down |
| **Next** | 8, 9, 12, 14 | Killer features — surgical context instead of brute-force file reading |
| **Then** | 7, 10, 13, 15 | Deepens utility, expands language coverage |
| **Later** | 11, 16–22 | Scale, polish, ecosystem breadth |
