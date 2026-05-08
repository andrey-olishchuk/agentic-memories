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
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent  # type: ignore[reportMissingImports]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORIES_PATH = PROJECT_ROOT / "memories"
STORAGE_ROOT = PROJECT_ROOT / "memory_storage"

EXAMPLE_TASK = (
    "Write and remember a haiku. Before writing, recall the latest haiku "
    "and use it as context so the next haiku continues the sequence while "
    "shifting to another topic."
)


class HaikuMemoryRun(BaseModel):
    selected_memory_type: str = Field(
        description="The MEMORY.md memory type the agent selected by using tools."
    )
    recalled_haiku: str | None = Field(
        description="The latest haiku recalled before writing the new haiku."
    )
    new_haiku: str = Field(description="The new three-line haiku that was stored.")
    memory_id: str = Field(description="The memory id returned by the remember tool.")
    storage_status: str = Field(
        description="The MemoryResult status from storing the haiku."
    )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    registry = Registry.load(str(MEMORIES_PATH))
    smoke_test(registry, tool_invoker, dry_run=True)

    model_name = pydantic_ai_model_name()
    agent = build_memory_agent(model_name, registry)
    result = agent.run_sync(EXAMPLE_TASK)
    output = result.output

    print(f"Selected memory type: {output.selected_memory_type}")
    print("Recalled previous haiku:")
    print(output.recalled_haiku or "(none yet)")
    print("\nStored new haiku:")
    print(output.model_dump_json(indent=2))


def pydantic_ai_model_name() -> str:
    model_name = os.getenv("PYDANTIC_AI_MODEL") or os.getenv(
        "OPENAI_MODEL",
        "gpt-4.1-mini",
    )
    return model_name if ":" in model_name else f"openai:{model_name}"


def build_memory_agent(
    model_name: str,
    registry: Registry,
) -> Agent[None, HaikuMemoryRun]:
    agent = Agent[None, HaikuMemoryRun](
        model_name,
        output_type=HaikuMemoryRun,
        instructions=(
            "You manage memory records through tools only. Do not assume a memory "
            "type or schema from prior knowledge. First call triage_memory with the "
            "task to get ranked candidates from the memory library. Use the top "
            "candidate, then call describe_memory_type to inspect its schema. Call "
            "recall_memory to get the latest haiku from that memory type. Write one "
            "new three-line haiku that continues the "
            "sequence while shifting to another topic. Then call remember_memory to "
            "store the new haiku using a payload that exactly matches the described "
            "schema. Only produce your final structured output after remember_memory "
            "returns ok."
        ),
    )

    @agent.tool_plain
    def triage_memory(input_text: str, top_k: int = 1) -> list[dict[str, Any]]:
        """Rank MEMORY.md memory types for the input text.

        Args:
            input_text: User task or content that needs memory.
            top_k: Maximum number of ranked candidates to return.
        """
        candidates = Triage(registry).rank(input_text=input_text, top_k=top_k)
        return [candidate.model_dump(mode="json") for candidate in candidates]

    @agent.tool_plain
    def describe_memory_type(memory_type: str) -> dict[str, Any]:
        """Return the full manifest for a MEMORY.md memory type.

        Args:
            memory_type: Exact memory type name from triage_memory.
        """
        manifest = registry.get(memory_type)
        return manifest.model_dump(mode="json", exclude={"path"})

    @agent.tool_plain
    def recall_memory(memory_type: str, query: str, limit: int = 1) -> dict[str, Any]:
        """Recall records from a memory type.

        Args:
            memory_type: Exact memory type name from triage_memory.
            query: Free-text query describing what to recall.
            limit: Maximum number of records to return.
        """
        result = invoke_recall(
            memory_type,
            {"query": query, "limit": limit},
            registry,
            tool_invoker,
        )
        return result.model_dump(mode="json", exclude_none=True)

    @agent.tool_plain
    def remember_memory(memory_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Store one record in a memory type.

        Args:
            memory_type: Exact memory type name from triage_memory.
            payload: JSON object matching the schema from describe_memory_type.
        """
        result = invoke_remember(memory_type, payload, registry, tool_invoker)
        return result.model_dump(mode="json", exclude_none=True)

    return agent


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
