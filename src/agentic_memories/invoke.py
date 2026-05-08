from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from .models import MemoryResult
from .registry import Registry
from .schema import schema_as_jsonable

ToolInvoker = Callable[[str, dict[str, Any]], MemoryResult | dict[str, Any]]

logger = logging.getLogger(__name__)


def invoke_remember(
    memory_type: str,
    payload: dict[str, Any],
    registry: Registry,
    tool_invoker: ToolInvoker,
) -> MemoryResult:
    try:
        manifest = registry.get(memory_type)
    except KeyError:
        return MemoryResult(
            status="permanent_error",
            reason=f"Unknown memory type: {memory_type}",
        )

    _soft_validate_payload(memory_type, payload, registry)
    return _as_memory_result(tool_invoker(manifest.name, {"payload": payload}))


def invoke_recall(
    memory_type: str,
    query: str | dict[str, Any],
    registry: Registry,
    tool_invoker: ToolInvoker,
) -> MemoryResult:
    try:
        manifest = registry.get(memory_type)
    except KeyError:
        return MemoryResult(
            status="permanent_error",
            reason=f"Unknown memory type: {memory_type}",
        )

    return _as_memory_result(tool_invoker(manifest.name, {"query": query}))


def _soft_validate_payload(
    memory_type: str,
    payload: dict[str, Any],
    registry: Registry,
) -> None:
    model = registry.schema_model_for(memory_type)
    try:
        model.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "Payload for memory type %s does not match MEMORY.md schema; proceeding",
            memory_type,
            extra={
                "diagnostics": {
                    "errors": exc.errors(),
                    "expected_schema": schema_as_jsonable(registry.get(memory_type).schema),
                }
            },
        )


def _as_memory_result(value: MemoryResult | dict[str, Any]) -> MemoryResult:
    if isinstance(value, MemoryResult):
        return value
    return MemoryResult.model_validate(value)
