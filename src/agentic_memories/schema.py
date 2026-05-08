from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model

SUPPORTED_TYPES = {
    "str",
    "int",
    "float",
    "bool",
    "datetime",
    "date",
    "list[str]",
    "list[float]",
    "dict",
}


def schema_model(name: str, schema: dict[str, str]) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    for field_name, type_name in schema.items():
        fields[field_name] = (_python_type(type_name), ...)

    model_name = "".join(part.capitalize() for part in name.split("_")) + "Payload"
    return create_model(
        model_name,
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def sample_payload(schema: dict[str, str]) -> dict[str, Any]:
    return {field_name: _sample_value(type_name) for field_name, type_name in schema.items()}


def schema_as_jsonable(schema: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(schema),
        "properties": {
            field_name: _json_type(type_name) for field_name, type_name in schema.items()
        },
    }


def _python_type(type_name: str) -> Any:
    normalized = type_name.strip()
    if normalized == "str":
        return str
    if normalized == "int":
        return int
    if normalized == "float":
        return float
    if normalized == "bool":
        return bool
    if normalized == "datetime":
        return datetime
    if normalized == "date":
        return date
    if normalized == "list[str]":
        return list[str]
    if normalized == "list[float]":
        return list[float]
    if normalized == "dict":
        return dict[str, Any]
    raise ValueError(f"Unsupported MEMORY.md schema type: {type_name!r}")


def _sample_value(type_name: str) -> Any:
    normalized = type_name.strip()
    if normalized == "str":
        return "sample"
    if normalized == "int":
        return 1
    if normalized == "float":
        return 1.0
    if normalized == "bool":
        return True
    if normalized == "datetime":
        return "2026-01-01T00:00:00Z"
    if normalized == "date":
        return "2026-01-01"
    if normalized == "list[str]":
        return ["sample"]
    if normalized == "list[float]":
        return [1.0]
    if normalized == "dict":
        return {"sample": "value"}
    raise ValueError(f"Unsupported MEMORY.md schema type: {type_name!r}")


def _json_type(type_name: str) -> dict[str, Any]:
    normalized = type_name.strip()
    if normalized in {"str", "datetime", "date"}:
        return {"type": "string"}
    if normalized == "int":
        return {"type": "integer"}
    if normalized == "float":
        return {"type": "number"}
    if normalized == "bool":
        return {"type": "boolean"}
    if normalized == "list[str]":
        return {"type": "array", "items": {"type": "string"}}
    if normalized == "list[float]":
        return {"type": "array", "items": {"type": "number"}}
    if normalized == "dict":
        return {"type": "object"}
    raise ValueError(f"Unsupported MEMORY.md schema type: {type_name!r}")
