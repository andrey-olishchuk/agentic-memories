from __future__ import annotations

import json
import os
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
from agentic_memories.schema import schema_as_jsonable
from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORIES_PATH = PROJECT_ROOT / "memories"
STORAGE_ROOT = PROJECT_ROOT / "memory_storage"

EXAMPLE_TASK = (
    "Write and remember a haiku. Before writing, recall the latest haiku "
    "and use it as context so the next haiku continues the sequence while "
    "shifting to another topic."
)


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    registry = Registry.load(str(MEMORIES_PATH))
    smoke_test(registry, tool_invoker, dry_run=True)

    client = OpenAI()
    memory_type = choose_memory_type_with_triage(client, registry, EXAMPLE_TASK)
    manifest = registry.get(memory_type)
    previous_haiku = recall_latest_haiku(memory_type, registry)
    payload = build_payload_with_openai(client, previous_haiku, manifest.schema)

    print(f"Selected memory type: {memory_type}")
    print("Recalled previous haiku:")
    print(previous_haiku or "(none yet)")
    print("\nStored new haiku:")
    result = invoke_remember(memory_type, payload, registry, tool_invoker)
    print(result.model_dump_json(indent=2, exclude_none=True))


def choose_memory_type_with_triage(
    client: OpenAI,
    registry: Registry,
    task: str,
) -> str:
    candidates = Triage(registry, llm_client=openai_triage_client(client)).rank(
        task,
        top_k=1,
    )
    return candidates[0].name


def openai_triage_client(client: OpenAI):
    def rank(prompt: str) -> str:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=prompt,
        )
        return response.output_text

    return rank


def recall_latest_haiku(memory_type: str, registry: Registry) -> str | None:
    result = invoke_recall(
        memory_type,
        {"topic": "latest haiku", "limit": 1},
        registry,
        tool_invoker,
    )
    if result.status != "ok" or not result.data:
        return None

    latest_memory = result.data[0]
    content = latest_memory.get("content")
    return content if isinstance(content, str) else None


def build_payload_with_openai(
    client: OpenAI,
    previous_haiku: str | None,
    schema: dict[str, str],
) -> dict[str, Any]:
    previous_context = previous_haiku or "No previous haiku has been stored yet."
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=(
            "Write one new three-line haiku and return it as a MEMORY.md payload. "
            "Use the previous haiku as context, continue the sequence, "
            "but shift to a different topic. "
            "Return JSON matching the schema, with the haiku in the content field.\n\n"
            f"Previous haiku:\n{previous_context}"
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "memory_payload",
                "schema": schema_as_jsonable(schema),
                "strict": True,
            }
        },
    )
    return json.loads(response.output_text)


def tool_invoker(memory_type: str, call: dict[str, Any]) -> MemoryResult:
    if "query" in call:
        return _recall(memory_type, call["query"])

    payload = call.get("payload", {})
    if "content" not in payload:
        return MemoryResult(
            status="incompatible",
            reason="Demo tool requires a content field",
            diagnostics={"expected_schema": {"content": "str"}},
        )

    if call.get("dry_run"):
        return MemoryResult(status="ok", data=[payload])

    storage_dir = STORAGE_ROOT / memory_type
    storage_dir.mkdir(parents=True, exist_ok=True)
    memory_id = str(uuid4())
    (storage_dir / f"{memory_id}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return MemoryResult(status="ok", memory_id=memory_id, data=[payload])


def _recall(memory_type: str, query: str | dict[str, Any]) -> MemoryResult:
    storage_dir = STORAGE_ROOT / memory_type
    if not storage_dir.exists():
        return MemoryResult(status="ok", data=[])

    limit = query.get("limit") if isinstance(query, dict) else None
    paths = sorted(
        storage_dir.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if isinstance(limit, int):
        paths = paths[:limit]

    data = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return MemoryResult(status="ok", data=data)


if __name__ == "__main__":
    main()
