"""MCP server adapter — exposes arcade-agent tools via Model Context Protocol."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from arcade_agent.budget import truncate_result
from arcade_agent.serialization import (
    dict_to_architecture,
    dict_to_graph,
    serialize_result,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session store — holds intermediate results so agents can reference by ID
# ---------------------------------------------------------------------------

_session: dict[str, Any] = {}


def _store(obj: Any, label: str = "") -> str:
    """Store an object in the session and return its ID."""
    sid = uuid.uuid4().hex[:12]
    _session[sid] = {"label": label, "value": obj}
    return sid


def _resolve(ref: str | dict | Any, expected_type: str = "") -> Any:
    """Resolve a session reference or pass-through a dict.

    Accepts either a session ID string or an inline dict representation.
    """
    if isinstance(ref, str) and ref in _session:
        return _session[ref]["value"]
    if isinstance(ref, dict):
        if expected_type == "DependencyGraph":
            return dict_to_graph(ref)
        if expected_type == "Architecture":
            return dict_to_architecture(ref)
        return ref
    raise ValueError(
        f"Invalid reference: {ref!r}. Provide a session ID from a previous tool call "
        f"or an inline JSON object."
    )


# ---------------------------------------------------------------------------
# Tool wrappers — each MCP tool maps to an arcade-agent tool
# ---------------------------------------------------------------------------


def _make_summary(obj: Any, label: str) -> dict:
    """Create a compact summary dict with a session ID for later retrieval."""
    sid = _store(obj, label)
    summary: dict[str, Any] = {"session_id": sid, "type": label}

    if hasattr(obj, "num_entities"):
        summary["num_entities"] = obj.num_entities
    if hasattr(obj, "num_edges"):
        summary["num_edges"] = obj.num_edges
    if hasattr(obj, "packages"):
        summary["num_packages"] = len(obj.packages)
    if hasattr(obj, "components"):
        summary["num_components"] = len(obj.components)
        summary["components"] = [
            {"name": c.name, "num_entities": len(c.entities)}
            for c in obj.components
        ]
    if hasattr(obj, "source_files"):
        summary["num_files"] = len(obj.source_files)
    if hasattr(obj, "language"):
        summary["language"] = obj.language
    if hasattr(obj, "name") and isinstance(getattr(obj, "name", None), str):
        summary["name"] = obj.name
    if hasattr(obj, "version"):
        summary["version"] = obj.version
    if hasattr(obj, "algorithm"):
        summary["algorithm"] = obj.algorithm

    return summary


def _apply_budget(data: Any, max_tokens: int | None) -> Any:
    """Apply token budget truncation if requested."""
    if max_tokens is None or not isinstance(data, dict):
        return data
    return truncate_result(data, max_tokens)


def _build_server():  # type: ignore[no-untyped-def]
    """Build and return the FastMCP server instance.

    Separated from module-level so the mcp dependency is only required
    at runtime when actually starting the server.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "MCP support requires the 'mcp' package. "
            "Install with: pip install arcade-agent[mcp]"
        )

    server = FastMCP(
        "arcade-agent",
        instructions=(
            "Software architecture analysis toolkit. "
            "Tools produce complex results stored in a session. "
            "Use session IDs from previous tool outputs as inputs to subsequent tools. "
            "For example: call 'parse' to get a session_id, then pass that session_id "
            "as dep_graph to 'recover'."
        ),
    )

    # -- ingest ----------------------------------------------------------------

    @server.tool()
    def ingest(
        source: str,
        language: str | None = None,
        work_dir: str | None = None,
        exclude_tests: bool = True,
        source_root: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Prepare source code for analysis.

        Accepts a git URL or local path. Auto-detects source roots and filters
        out test/vendored code.

        Args:
            source: Git repo URL or local directory path.
            language: Override language detection (java, python, c, typescript).
            work_dir: Directory to clone into. Uses temp dir if None.
            exclude_tests: Exclude test/vendor/build directories (default True).
            source_root: Override source root (e.g. 'src/main/java').
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.ingest import ingest as _ingest

        result = _ingest(
            source=source,
            language=language,
            work_dir=work_dir,
            exclude_tests=exclude_tests,
            source_root=source_root,
        )
        summary = _make_summary(result, "IngestedRepo")
        return json.dumps(_apply_budget(summary, max_tokens), indent=2)

    # -- parse -----------------------------------------------------------------

    @server.tool()
    def parse(
        source_path: str,
        language: str | None = None,
        files: list[str] | None = None,
        use_cache: bool = True,
        max_tokens: int | None = None,
    ) -> str:
        """Parse source code and extract a dependency graph.

        Returns a session_id referencing the parsed DependencyGraph. Pass this
        session_id as the dep_graph argument to recover, detect_smells, etc.

        Args:
            source_path: Root directory of the project.
            language: Language to parse (java, python, c). Auto-detected if None.
            files: Specific files to parse. Discovers all if None.
            use_cache: Return cached results when source files haven't changed.
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.parse import parse as _parse

        graph = _parse(
            source_path=source_path,
            language=language,
            files=files,
            use_cache=use_cache,
        )
        summary = _make_summary(graph, "DependencyGraph")
        return json.dumps(_apply_budget(summary, max_tokens), indent=2)

    # -- recover ---------------------------------------------------------------

    @server.tool()
    def recover(
        dep_graph: str,
        algorithm: str = "pkg",
        num_clusters: int | None = None,
        similarity_measure: str = "uem",
        pkg_depth: int | None = None,
        hybrid_weight: float = 0.5,
        max_tokens: int | None = None,
    ) -> str:
        """Recover software architecture from a dependency graph.

        Args:
            dep_graph: Session ID from a previous 'parse' call.
            algorithm: Recovery algorithm (pkg, wca, acdc, arc, limbo).
            num_clusters: Target number of clusters (for wca/arc/limbo).
            similarity_measure: Similarity measure for wca (js, uem, scm).
            pkg_depth: Package depth for pkg algorithm.
            hybrid_weight: Semantic/structural blend for arc (0-1).
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.recover import recover as _recover

        graph_obj = _resolve(dep_graph, "DependencyGraph")
        arch = _recover(
            dep_graph=graph_obj,
            algorithm=algorithm,
            num_clusters=num_clusters,
            similarity_measure=similarity_measure,
            pkg_depth=pkg_depth,
            hybrid_weight=hybrid_weight,
        )
        summary = _make_summary(arch, "Architecture")
        return json.dumps(_apply_budget(summary, max_tokens), indent=2)

    # -- detect_smells ---------------------------------------------------------

    @server.tool()
    def detect_smells(
        architecture: str,
        dep_graph: str,
        use_llm: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        """Detect architectural anti-patterns.

        Finds dependency cycles, concern overload, scattered functionality,
        and link overload.

        Args:
            architecture: Session ID from a previous 'recover' call.
            dep_graph: Session ID from a previous 'parse' call.
            use_llm: Use LLM for deeper semantic analysis (default False).
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.detect_smells import detect_smells as _detect

        arch_obj = _resolve(architecture, "Architecture")
        graph_obj = _resolve(dep_graph, "DependencyGraph")
        smells = _detect(
            architecture=arch_obj,
            dep_graph=graph_obj,
            use_llm=use_llm,
        )
        result = serialize_result(smells)
        sid = _store(smells, "SmellList")
        output = {"session_id": sid, "num_smells": len(smells), "smells": result}
        return json.dumps(_apply_budget(output, max_tokens), indent=2)

    # -- compute_metrics -------------------------------------------------------

    @server.tool()
    def compute_metrics(
        architecture: str,
        dep_graph: str,
        max_tokens: int | None = None,
    ) -> str:
        """Calculate architecture quality metrics.

        Computes RCI, TurboMQ, BasicMQ, connectivity, and coupling ratios.

        Args:
            architecture: Session ID from a previous 'recover' call.
            dep_graph: Session ID from a previous 'parse' call.
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.compute_metrics import compute_metrics as _metrics

        arch_obj = _resolve(architecture, "Architecture")
        graph_obj = _resolve(dep_graph, "DependencyGraph")
        metrics = _metrics(architecture=arch_obj, dep_graph=graph_obj)
        result = serialize_result(metrics)
        sid = _store(metrics, "MetricList")
        output = {"session_id": sid, "num_metrics": len(metrics), "metrics": result}
        return json.dumps(_apply_budget(output, max_tokens), indent=2)

    # -- compare ---------------------------------------------------------------

    @server.tool()
    def compare(
        arch_a: str,
        arch_b: str,
        max_tokens: int | None = None,
    ) -> str:
        """Compare two architectures (A2A analysis).

        Matches components using the Hungarian algorithm and tracks additions,
        removals, splits, and merges.

        Args:
            arch_a: Session ID for the first architecture.
            arch_b: Session ID for the second architecture.
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.compare import compare as _compare

        a = _resolve(arch_a, "Architecture")
        b = _resolve(arch_b, "Architecture")
        result = _compare(arch_a=a, arch_b=b)
        serialized = serialize_result(result)
        return json.dumps(_apply_budget(serialized, max_tokens), indent=2)

    # -- query -----------------------------------------------------------------

    @server.tool()
    def query(
        architecture: str,
        dep_graph: str,
        question: str,
        entity: str | None = None,
        component: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Query and explore a recovered architecture.

        Supported questions: component_of, dependencies, dependents, entities,
        most_coupled, summary, largest.

        Args:
            architecture: Session ID from a previous 'recover' call.
            dep_graph: Session ID from a previous 'parse' call.
            question: Query type (component_of, dependencies, dependents, entities,
                most_coupled, summary, largest).
            entity: Entity FQN for entity-specific queries.
            component: Component name for component-specific queries.
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.query import query as _query

        arch_obj = _resolve(architecture, "Architecture")
        graph_obj = _resolve(dep_graph, "DependencyGraph")
        result = _query(
            architecture=arch_obj,
            dep_graph=graph_obj,
            question=question,
            entity=entity,
            component=component,
        )
        serialized = serialize_result(result)
        return json.dumps(_apply_budget(serialized, max_tokens), indent=2)

    # -- visualize -------------------------------------------------------------

    @server.tool()
    def visualize(
        repo_name: str,
        version: str,
        dep_graph: str,
        architecture: str,
        smells: str | None = None,
        metrics: str | None = None,
        output: str = "report.html",
        format: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate architecture reports and diagrams.

        Supports HTML, DOT, JSON, RSF, and Mermaid output formats.

        Args:
            repo_name: Name of the repository.
            version: Version/commit identifier.
            dep_graph: Session ID from a previous 'parse' call.
            architecture: Session ID from a previous 'recover' call.
            smells: Session ID from a previous 'detect_smells' call (optional).
            metrics: Session ID from a previous 'compute_metrics' call (optional).
            output: Output file path (default: report.html).
            format: Output format (html, dot, json, rsf, mermaid). Auto-detected from extension.
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.visualize import visualize as _visualize

        graph_obj = _resolve(dep_graph, "DependencyGraph")
        arch_obj = _resolve(architecture, "Architecture")
        smells_obj = _resolve(smells, "SmellList") if smells else None
        metrics_obj = _resolve(metrics, "MetricList") if metrics else None

        result_path = _visualize(
            repo_name=repo_name,
            version=version,
            dep_graph=graph_obj,
            architecture=arch_obj,
            smells=smells_obj,
            metrics=metrics_obj,
            output=output,
            format=format,
        )
        return json.dumps({"output_path": result_path}, indent=2)

    # -- summarize -------------------------------------------------------------

    @server.tool()
    def summarize(
        source_path: str,
        language: str | None = None,
        focus: str | None = None,
        use_cache: bool = True,
        max_tokens: int | None = None,
    ) -> str:
        """Summarize a codebase for quick understanding.

        Returns package structure, dependency hotspots, and entry points.
        Use the focus parameter to drill into a specific package.

        Args:
            source_path: Root directory of the project.
            language: Language to parse (auto-detected if None).
            focus: Package name to drill into (e.g. "com.example.auth").
            use_cache: Use cached parse results when available.
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.summarize import summarize as _summarize

        result = _summarize(
            source_path=source_path,
            language=language,
            focus=focus,
            use_cache=use_cache,
        )
        serialized = serialize_result(result)
        return json.dumps(_apply_budget(serialized, max_tokens), indent=2)

    # -- explain_component -----------------------------------------------------

    @server.tool()
    def explain_component(
        architecture: str,
        dep_graph: str,
        component: str,
        max_tokens: int | None = None,
    ) -> str:
        """Explain a component from a recovered architecture.

        Shows responsibility, entities, public API surface, dependencies,
        and cohesion metrics.

        Args:
            architecture: Session ID from a previous 'recover' call.
            dep_graph: Session ID from a previous 'parse' call.
            component: Name of the component to explain.
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.explain_component import explain_component as _explain

        arch_obj = _resolve(architecture, "Architecture")
        graph_obj = _resolve(dep_graph, "DependencyGraph")
        result = _explain(
            architecture=arch_obj,
            dep_graph=graph_obj,
            component=component,
        )
        serialized = serialize_result(result)
        return json.dumps(_apply_budget(serialized, max_tokens), indent=2)

    # -- find_relevant ---------------------------------------------------------

    @server.tool()
    def find_relevant(
        dep_graph: str,
        query: str,
        architecture: str | None = None,
        top_k: int = 10,
        max_tokens: int | None = None,
    ) -> str:
        """Find code entities relevant to a natural-language query.

        Searches entity names, packages, and file paths using keyword matching.
        Optionally uses recovered architecture for component context.

        Args:
            dep_graph: Session ID from a previous 'parse' call.
            query: Natural-language query (e.g. "authentication login").
            architecture: Optional session ID from a previous 'recover' call.
            top_k: Maximum number of results to return.
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.find_relevant import find_relevant as _find

        graph_obj = _resolve(dep_graph, "DependencyGraph")
        arch_obj = _resolve(architecture, "Architecture") if architecture else None
        result = _find(
            dep_graph=graph_obj,
            query=query,
            architecture=arch_obj,
            top_k=top_k,
        )
        serialized = serialize_result(result)
        return json.dumps(_apply_budget(serialized, max_tokens), indent=2)

    # -- get_full_result -------------------------------------------------------

    @server.tool()
    def get_full_result(
        session_id: str,
        max_tokens: int | None = None,
    ) -> str:
        """Retrieve the full result of a previous tool call by session ID.

        Use this when you need detailed data beyond the summary returned by
        other tools. For example, to get the full entity list from a parse result.

        Args:
            session_id: Session ID from a previous tool call.
            max_tokens: Optional token budget for the response.
        """
        if session_id not in _session:
            available = list(_session.keys())
            return json.dumps({
                "error": f"Session ID '{session_id}' not found",
                "available_sessions": available,
            })
        entry = _session[session_id]
        serialized = serialize_result(entry["value"])
        result = {"session_id": session_id, "type": entry["label"], "data": serialized}
        return json.dumps(_apply_budget(result, max_tokens), indent=2)

    # -- list_sessions ---------------------------------------------------------

    @server.tool()
    def list_sessions() -> str:
        """List all objects stored in the current session.

        Returns session IDs and their types so you can reference them in
        subsequent tool calls.
        """
        entries = [
            {"session_id": sid, "type": entry["label"]}
            for sid, entry in _session.items()
        ]
        return json.dumps({"sessions": entries}, indent=2)

    return server


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_server = None


def get_server():  # type: ignore[no-untyped-def]
    """Get or create the MCP server singleton."""
    global _server
    if _server is None:
        _server = _build_server()
    return _server


def main() -> None:
    """Run the MCP server on stdio transport."""
    server = get_server()
    server.run()


if __name__ == "__main__":
    main()
