"""Shared data models for architecture analysis."""

from arcade_agent.models.architecture import Architecture, Component
from arcade_agent.models.graph import DependencyGraph, Edge, Entity
from arcade_agent.models.metrics import MetricResult
from arcade_agent.models.smells import SmellInstance, SmellType

__all__ = [
    "Architecture",
    "Component",
    "DependencyGraph",
    "Edge",
    "Entity",
    "MetricResult",
    "SmellInstance",
    "SmellType",
]
