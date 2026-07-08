#!/usr/bin/env python3
"""Backward-compatible wrapper for the packaged baseline comparison CLI."""

from arcade_agent.ci.compare_baseline import *  # noqa: F403
from arcade_agent.ci.compare_baseline import main


if __name__ == "__main__":
    main()
