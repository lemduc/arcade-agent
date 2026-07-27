"""Tool adapter and compatibility exports for source ingestion."""

from arcade_agent.source.ingest import IngestedRepo, ingest
from arcade_agent.tooling.registry import tool

tool(
    name="ingest",
    description="Prepare source code for analysis. Accepts git URL or local path. "
    "Auto-detects source roots, filters out test/vendored code by default, "
    "and accepts exact custom directory exclusions.",
)(ingest)

__all__ = ["IngestedRepo", "ingest"]
