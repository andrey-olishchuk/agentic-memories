from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from agentic_memories import (
    MemoryResult,
    Registry,
    SmokeTestError,
    Triage,
    invoke_recall,
    invoke_remember,
    smoke_test,
)


def write_memory(root, name: str = "default", schema: str = "  content: str") -> None:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "MEMORY.md").write_text(
        f"""---
name: {name}
description: Test memory
purpose: factual
schema:
{schema}
recall_hints:
  typical_query: Test lookup
  recency_matters: true
lifecycle:
  importance: medium
  forgettable: true
---

# {name}

Use for tests.
""",
        encoding="utf-8",
    )


def test_registry_loads_memory_manifests(tmp_path):
    write_memory(tmp_path)

    registry = Registry.load(str(tmp_path))

    assert [summary.name for summary in registry.list()] == ["default"]
    manifest = registry.get("default")
    assert manifest.schema == {"content": "str"}
    assert manifest.body.startswith("# default")


def test_schema_model_generation_validates_payload(tmp_path):
    write_memory(tmp_path, schema="  content: str\n  tags: list[str]")
    registry = Registry.load(str(tmp_path))
    model = registry.schema_model_for("default")

    payload = model.model_validate({"content": "hello", "tags": ["a"]})

    assert payload.content == "hello"
    with pytest.raises(ValidationError):
        model.model_validate({"content": "hello", "tags": [1], "extra": "nope"})


def test_invoke_remember_soft_validates_and_routes(tmp_path, caplog):
    write_memory(tmp_path)
    registry = Registry.load(str(tmp_path))
    calls = []

    def invoker(memory_type, call):
        calls.append((memory_type, call))
        return MemoryResult(status="ok", memory_id="m1")

    caplog.set_level(logging.WARNING)
    result = invoke_remember("default", {"wrong": "shape"}, registry, invoker)

    assert result.status == "ok"
    assert calls == [("default", {"payload": {"wrong": "shape"}})]
    assert "does not match MEMORY.md schema" in caplog.text


def test_invoke_unknown_memory_type_returns_permanent_error(tmp_path):
    write_memory(tmp_path)
    registry = Registry.load(str(tmp_path))

    result = invoke_remember("missing", {"content": "x"}, registry, lambda *_: {})

    assert result.status == "permanent_error"


def test_invoke_recall_routes_query(tmp_path):
    write_memory(tmp_path)
    registry = Registry.load(str(tmp_path))

    result = invoke_recall(
        "default",
        "concise",
        registry,
        lambda memory_type, call: MemoryResult(
            status="ok",
            data=[{"memory_type": memory_type, "query": call["query"]}],
        ),
    )

    assert result.data == [{"memory_type": "default", "query": "concise"}]


def test_incompatible_memory_result_requires_expected_schema():
    with pytest.raises(ValidationError):
        MemoryResult(status="incompatible", reason="bad payload")


def test_smoke_test_uses_generated_payload_and_dry_run(tmp_path):
    write_memory(tmp_path)
    registry = Registry.load(str(tmp_path))
    calls = []

    def invoker(memory_type, call):
        calls.append((memory_type, call))
        return {"status": "ok"}

    report = smoke_test(registry, invoker, dry_run=True)

    assert report.ok is True
    assert calls == [("default", {"payload": {"content": "sample"}, "dry_run": True})]


def test_smoke_test_raises_on_incompatible_tool(tmp_path):
    write_memory(tmp_path)
    registry = Registry.load(str(tmp_path))

    with pytest.raises(SmokeTestError) as exc_info:
        smoke_test(
            registry,
            lambda *_: MemoryResult(
                status="incompatible",
                reason="bad schema",
                diagnostics={"expected_schema": {"content": "str"}},
            ),
        )

    assert "default" in str(exc_info.value)
    assert exc_info.value.report is not None


def test_triage_keyword_fallback_prefers_specific_memory(tmp_path):
    write_memory(tmp_path)
    write_memory(
        tmp_path,
        name="concise_responses",
        schema="  preference: str",
    )
    registry = Registry.load(str(tmp_path))

    candidates = Triage(registry).rank("User prefers concise responses", top_k=1)

    assert candidates[0].name == "concise_responses"
