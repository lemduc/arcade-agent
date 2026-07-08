#!/usr/bin/env python3
"""Backward-compatible wrapper for the packaged self-analysis CLI."""

from arcade_agent.ci.run_self_analysis import _filter_non_architectural_entities, main


if __name__ == "__main__":
    main()
