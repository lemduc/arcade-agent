"""Small display-formatting helpers shared across tools and CI scripts."""

from typing import Any


def display_value(value: Any) -> Any:
    """Coerce an enum-like value to its plain scalar.

    Several domain fields (e.g. ``SmellInstance.smell_type``) are annotated
    ``str`` but actually hold enum members, so ``str(member)`` would
    otherwise leak as ``"SmellType.DEPENDENCY_CYCLE"`` in rendered markdown
    or any JSON serialisation.

    Args:
        value: A value that may be an enum member or already a plain scalar.

    Returns:
        ``value.value`` if *value* has a ``.value`` attribute (enum member),
        otherwise *value* unchanged.
    """
    return value.value if hasattr(value, "value") else value
