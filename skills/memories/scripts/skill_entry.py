from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from agentic_memories import (
    MemoryResult,
    Registry,
    Triage,
    invoke_recall,
    invoke_remember,
    smoke_test,
)


def registry() -> Registry:
    return Registry.load(os.getenv("MEMORIES_PATH", "./memories"))


def list_memory_types() -> list[dict[str, Any]]:
    return [summary.model_dump() for summary in registry().list()]


def triage(input_text: str, top_k: int = 3) -> list[dict[str, Any]]:
    return [
        candidate.model_dump()
        for candidate in Triage(registry()).rank(input_text=input_text, top_k=top_k)
    ]


def describe(memory_type: str) -> dict[str, Any]:
    return registry().get(memory_type).model_dump(mode="json")


def remember(memory_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = invoke_remember(memory_type, payload, registry(), tool_invoker)
    return result.model_dump(exclude_none=True)


def recall(memory_type: str, query: str | dict[str, Any]) -> dict[str, Any]:
    result = invoke_recall(memory_type, query, registry(), tool_invoker)
    return result.model_dump(exclude_none=True)


def startup_smoke_test() -> dict[str, Any]:
    return smoke_test(registry(), tool_invoker).model_dump(exclude_none=True)


def tool_invoker(memory_type: str, call: dict[str, Any]) -> MemoryResult:
    if "query" in call:
        return _recall(memory_type)

    payload = call.get("payload", {})
    if "content" not in payload:
        return MemoryResult(
            status="incompatible",
            reason="Demo tool requires a content field",
            diagnostics={"expected_schema": {"content": "str"}},
        )

    transformed = _append_sss(payload)
    if call.get("dry_run"):
        return MemoryResult(status="ok", data=[transformed])

    storage_dir = Path("./memory_storage") / memory_type
    storage_dir.mkdir(parents=True, exist_ok=True)
    memory_id = str(uuid4())
    (storage_dir / f"{memory_id}.json").write_text(
        json.dumps(transformed, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return MemoryResult(status="ok", memory_id=memory_id, data=[transformed])


def _recall(memory_type: str) -> MemoryResult:
    storage_dir = Path("./memory_storage") / memory_type
    if not storage_dir.exists():
        return MemoryResult(status="ok", data=[])
    data = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(storage_dir.glob("*.json"))
    ]
    return MemoryResult(status="ok", data=data)


def _append_sss(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _append_sss(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_append_sss(item) for item in value]
    return f"{value}sss"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: skill_entry.py <operation> '<json arguments>'")

    operation = sys.argv[1]
    args = json.loads(sys.argv[2])
    operations = {
        "list_memory_types": lambda: list_memory_types(),
        "triage": lambda: triage(**args),
        "describe": lambda: describe(**args),
        "remember": lambda: remember(**args),
        "recall": lambda: recall(**args),
        "smoke_test": lambda: startup_smoke_test(),
    }
    if operation not in operations:
        raise SystemExit(f"Unknown operation: {operation}")
    print(json.dumps(operations[operation](), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
