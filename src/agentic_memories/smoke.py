from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .invoke import ToolInvoker, _as_memory_result
from .models import MemoryResult, SmokeCase, SmokeReport
from .registry import Registry
from .schema import sample_payload


class SmokeTestError(RuntimeError):
    def __init__(self, message: str, report: SmokeReport | None = None):
        super().__init__(message)
        self.report = report


def smoke_test(
    registry: Registry,
    tool_invoker: ToolInvoker,
    dry_run: bool = True,
) -> SmokeReport:
    cases: list[SmokeCase] = []

    for manifest in registry:
        payload = sample_payload(manifest.schema)
        result = _invoke_smoke_case(manifest.name, payload, tool_invoker, dry_run)
        cases.append(
            SmokeCase(
                memory_type=manifest.name,
                sample_payload=payload,
                result=result,
            )
        )

    report = SmokeReport(
        ok=all(case.result.status == "ok" for case in cases),
        cases=cases,
    )
    incompatible = [case.memory_type for case in cases if case.result.status == "incompatible"]
    if incompatible:
        raise SmokeTestError(
            "Startup smoke test found incompatible memory tools: "
            + ", ".join(incompatible),
            report=report,
        )
    return report


def _invoke_smoke_case(
    memory_type: str,
    payload: dict[str, Any],
    tool_invoker: ToolInvoker,
    dry_run: bool,
) -> MemoryResult:
    try:
        return _as_memory_result(
            tool_invoker(memory_type, {"payload": payload, "dry_run": dry_run})
        )
    except ValidationError as exc:
        raise SmokeTestError(
            f"Tool for memory type {memory_type!r} returned an invalid MemoryResult",
            report=SmokeReport(
                ok=False,
                cases=[
                    SmokeCase(
                        memory_type=memory_type,
                        sample_payload=payload,
                        result=MemoryResult(
                            status="incompatible",
                            reason=str(exc),
                            diagnostics={
                                "expected_schema": "MemoryResult",
                                "expected_result_contract": "MemoryResult",
                            },
                        ),
                    )
                ],
            ),
        ) from exc
