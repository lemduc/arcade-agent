"""Shared data models for architecture analysis.

Re-exports from algorithms for backwards compatibility.
"""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.smells import SmellInstance, SmellType

__all__ = [
    "Architecture",
    "Component",
    "MetricResult",
    "SmellInstance",
    "SmellType",
]
