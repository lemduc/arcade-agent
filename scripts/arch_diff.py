#!/usr/bin/env python3
"""Backward-compatible wrapper for the packaged architecture drift CLI."""

from arcade_agent.ci.arch_diff import build_report, main


if __name__ == "__main__":
    main()
