"""Architectural smell data models."""

from dataclasses import dataclass, field
from enum import Enum


class SmellType(str, Enum):
    """Types of architectural smells detected by ARCADE."""

    DEPENDENCY_CYCLE = "Dependency Cycle"
    CONCERN_OVERLOAD = "Concern Overload"
    SCATTERED_FUNCTIONALITY = "Scattered Parasitic Functionality"
    LINK_OVERLOAD = "Link/Upstream Overload"


@dataclass
class SmellInstance:
    """A detected architectural smell."""

    smell_type: str
    severity: str  # "high", "medium", "low"
    affected_components: list[str] = field(default_factory=list)
    description: str = ""
    explanation: str = ""
    suggestion: str = ""
