from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from .models import TriageCandidate
from .registry import Registry

LLMClient = Callable[[str], str | list[dict[str, Any]] | dict[str, Any]]


class Triage:
    def __init__(self, registry: Registry, llm_client: LLMClient | None = None):
        self.registry = registry
        self.llm_client = llm_client

    def rank(self, input_text: str, top_k: int = 3) -> list[TriageCandidate]:
        if self.llm_client is not None:
            llm_candidates = self._rank_with_llm(input_text, top_k)
            if llm_candidates:
                return llm_candidates
        return self._rank_with_keywords(input_text, top_k)

    def _rank_with_llm(self, input_text: str, top_k: int) -> list[TriageCandidate]:
        prompt = self._prompt(input_text, top_k)
        response = self.llm_client(prompt) if self.llm_client else []
        try:
            raw_candidates = json.loads(response) if isinstance(response, str) else response
            if isinstance(raw_candidates, dict):
                raw_candidates = raw_candidates.get("candidates", [])
            candidates = [
                TriageCandidate.model_validate(candidate)
                for candidate in raw_candidates
                if candidate.get("name") in self.registry
            ]
            return sorted(candidates, key=lambda item: item.score, reverse=True)[:top_k]
        except Exception:
            return []

    def _rank_with_keywords(self, input_text: str, top_k: int) -> list[TriageCandidate]:
        input_tokens = _tokens(input_text)
        candidates: list[TriageCandidate] = []

        for manifest in self.registry:
            corpus = " ".join(
                [
                    manifest.name,
                    manifest.description,
                    manifest.purpose,
                    manifest.recall_hints.typical_query,
                    " ".join(manifest.schema),
                    manifest.body,
                ]
            )
            memory_tokens = _tokens(corpus)
            overlap = input_tokens & memory_tokens
            score = len(overlap) / max(len(input_tokens), 1)
            if manifest.name == "default":
                score = max(score, 0.2)
            candidates.append(
                TriageCandidate(
                    name=manifest.name,
                    score=min(score, 1.0),
                    reason=(
                        "Matched keywords: " + ", ".join(sorted(overlap)[:8])
                        if overlap
                        else "Default fallback candidate"
                    ),
                )
            )

        return sorted(candidates, key=lambda item: item.score, reverse=True)[:top_k]

    def _prompt(self, input_text: str, top_k: int) -> str:
        memory_types = [
            {
                "name": manifest.name,
                "description": manifest.description,
                "purpose": manifest.purpose,
                "schema": manifest.schema,
            }
            for manifest in self.registry
        ]
        return (
            "Rank MEMORY.md memory types for the user input. "
            "Return only JSON: [{\"name\": str, \"score\": 0..1, \"reason\": str}].\n"
            f"top_k={top_k}\n"
            f"memory_types={json.dumps(memory_types, ensure_ascii=False)}\n"
            f"input={input_text}"
        )


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}
