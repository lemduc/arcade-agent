"""Tool registry and discovery."""

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints

_TOOLS: dict[str, "ToolDef"] = {}


@dataclass
class ToolDef:
    """Definition of a registered tool."""

    name: str
    description: str
    fn: Callable
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)


def tool(name: str, description: str) -> Callable:
    """Decorator to register a function as a tool."""

    def decorator(fn: Callable) -> Callable:
        _TOOLS[name] = ToolDef(
            name=name,
            description=description,
            fn=fn,
            input_schema=_schema_from_hints(fn),
            output_schema=_schema_from_return(fn),
        )
        return fn

    return decorator


def get_tool(name: str) -> ToolDef:
    """Get a registered tool by name."""
    if name not in _TOOLS:
        raise KeyError(f"Tool '{name}' not found. Available: {list(_TOOLS.keys())}")
    return _TOOLS[name]


def list_tools() -> list[ToolDef]:
    """List all registered tools."""
    return list(_TOOLS.values())


_PYTHON_TYPE_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _type_to_json_schema(tp: Any) -> dict:
    """Convert a Python type hint to a JSON schema fragment."""
    origin = getattr(tp, "__origin__", None)

    if tp in _PYTHON_TYPE_TO_JSON:
        return {"type": _PYTHON_TYPE_TO_JSON[tp]}

    if origin is list:
        args = getattr(tp, "__args__", ())
        items = _type_to_json_schema(args[0]) if args else {}
        return {"type": "array", "items": items}

    if origin is dict:
        return {"type": "object"}

    # Union types (e.g., str | None)
    if origin is type(str | None):
        args = getattr(tp, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            schema = _type_to_json_schema(non_none[0])
            schema["nullable"] = True
            return schema

    return {"type": "object", "description": str(tp)}


def _schema_from_hints(fn: Callable) -> dict:
    """Extract JSON schema for function parameters from type hints."""
    try:
        hints = get_type_hints(fn)
    except Exception:
        return {}

    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        if param_name == "return":
            continue

        tp = hints.get(param_name, str)
        prop = _type_to_json_schema(tp)

        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop["default"] = param.default

        properties[param_name] = prop

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _schema_from_return(fn: Callable) -> dict:
    """Extract JSON schema for function return type."""
    try:
        hints = get_type_hints(fn)
    except Exception:
        return {}

    ret = hints.get("return")
    if ret is None:
        return {}
    return _type_to_json_schema(ret)
