"""Architecture quality metric data models."""

from dataclasses import dataclass, field


@dataclass
class MetricResult:
    """Result of computing an architecture quality metric."""

    name: str
    value: float
    details: dict = field(default_factory=dict)
