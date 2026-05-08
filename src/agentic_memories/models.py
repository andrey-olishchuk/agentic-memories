from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Purpose = Literal[
    "observational",
    "procedural",
    "episodic",
    "factual",
    "preferential",
    "corrective",
]

Importance = Literal["low", "medium", "high"]
MemoryStatus = Literal["ok", "incompatible", "transient_error", "permanent_error"]


class RecallHints(BaseModel):
    typical_query: str
    recency_matters: bool


class Lifecycle(BaseModel):
    importance: Importance
    forgettable: bool


class ManifestSummary(BaseModel):
    name: str
    description: str
    purpose: Purpose
    schema_: dict[str, str] = Field(alias="schema")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    @property
    def schema(self) -> dict[str, str]:
        return self.schema_


class Manifest(BaseModel):
    name: str
    description: str
    purpose: Purpose
    schema_: dict[str, str] = Field(alias="schema")
    recall_hints: RecallHints
    lifecycle: Lifecycle
    body: str = ""
    path: Path

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    @property
    def schema(self) -> dict[str, str]:
        return self.schema_

    def summary(self) -> ManifestSummary:
        return ManifestSummary(
            name=self.name,
            description=self.description,
            purpose=self.purpose,
            schema=self.schema,
        )


class MemoryResult(BaseModel):
    status: MemoryStatus
    memory_id: str | None = None
    data: list[dict[str, Any]] | None = None
    reason: str | None = None
    diagnostics: dict[str, Any] | None = None
    retry_after_seconds: int | None = None

    @model_validator(mode="after")
    def incompatible_results_include_expected_schema(self) -> "MemoryResult":
        if self.status == "incompatible" and (
            not self.diagnostics or "expected_schema" not in self.diagnostics
        ):
            raise ValueError(
                "MemoryResult(status='incompatible') requires diagnostics.expected_schema"
            )
        return self


class TriageCandidate(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str


class SmokeCase(BaseModel):
    memory_type: str
    sample_payload: dict[str, Any]
    result: MemoryResult


class SmokeReport(BaseModel):
    ok: bool
    cases: list[SmokeCase]
