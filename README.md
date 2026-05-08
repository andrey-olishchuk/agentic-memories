# Universal Memory Manifest System (MEMORY.md)

## Overview

A universal, framework-agnostic mechanism for declaring memory types as self-describing folders containing MEMORY.md manifests — structurally analogous to the Agent Skills standard (agentskills.io) where capabilities are declared via SKILL.md.

The system follows the same mental model as skills: drop a folder with a manifest, and the agent discovers, triages, and uses the new memory type without code changes. **There is no separate binding layer or bindings file. Tool discovery for memory types follows the exact same mechanism as skill discovery.**

The system has four independently-implementable components:

- **memories Skill** — entry-point skill following the Agent Skills standard
- **Default MEMORY.md Set** — folder structure with example memory type manifests  
- **agentic-memories Python Library** — pip-installable, framework-agnostic library for loading, validating, and triaging memory manifests
- **Example Scripts** — direct, skill-based, and Pydantic AI demonstrations of end-to-end flow

---

## Design Principles (Apply to All Components)

- **Declarative over procedural.** Memory types are defined as files, not code — exactly like skills.
- **Structural symmetry with skills.** A memory type folder mirrors a skill folder: a manifest at the root, optional supporting files, discoverable by scanning a directory. **Discovery works identically to skill discovery — no bindings file, no registration step.**
- **Semantic separation.** MEMORY.md describes what a memory is for and its declared shape; tools handle how it is stored.
- **Opaque payload contract.** Tools receive `{"payload": <dict>}` and are the sole authority on whether the payload is acceptable. They return a standardized `MemoryResult`.
- **Reliability without rigidity.** Three mechanisms ensure correctness: standardized result contract, soft pre-validation against manifest schema, and startup smoke tests.
- **Two-step flow.** The agent (1) triages to find the right memory type via the skill, then (2) invokes the corresponding tool with a payload.
- **Framework-agnostic core.** The Python library has no dependency on any specific agent framework.

---

## Folder Layout (Reference)

```
./agent_workspace/
  skills/
    memories/
      SKILL.md
      scripts/
    <other_skills>/
      SKILL.md
  memories/                      # mirrors skills/ — each subfolder is one memory type
    default/
      MEMORY.md
  tools/
```

The `memories/` directory mirrors how `skills/` is organized. Each subfolder is one memory type, identified by the `name` field in its MEMORY.md frontmatter. **There is no `bindings.yaml`. Tool resolution is handled by the same discovery mechanism used for skills — the folder structure is the declaration.**

The `skills/memories/` folder is an optional agent-facing adapter. Systems that do not want to use Agent Skills can run with only `memories/` plus the `agentic-memories` library by loading the registry directly and calling `invoke_remember` / `invoke_recall`.

---

## Reliability Mechanisms (Mandatory Across Components)

1. **Standardized MemoryResult contract.** Every tool returns the same result shape (`status`, `memory_id`, `data`, `reason`, `diagnostics`, `retry_after_seconds`).
2. **Soft pre-validation against the manifest schema.** Before invoking a tool, the library validates the payload and logs a warning if it doesn't match — but proceeds anyway. The tool remains the runtime authority.
3. **Startup smoke test.** On system initialization, the library generates a sample payload from each manifest's schema and invokes each discoverable tool with `dry_run: true`. Any incompatible result raises a clear startup error.

---

## Component 1: The memories Skill

**Purpose:** A standard agentic skill that gives any agent the ability to use the memory manifest system.

**Skill operations the agent can invoke:**

- `list_memory_types()` — return all available memory types with name, purpose, and schema summary
- `triage(input_text)` — return ranked candidate memory types with relevance scores
- `describe(memory_type)` — return the full manifest for one memory type
- `remember(memory_type, payload)` — route the payload to the corresponding tool, return MemoryResult
- `recall(memory_type, query)` — route the query to the corresponding read tool, return MemoryResult with data

**Implementation notes:**

- The skill is thin — it delegates all logic to the agentic-memories library via a small Python script bundled in the skill folder.
- SKILL.md body must instruct: *"When you have data to remember, first call `triage`, then call `describe` to read the schema, then call `remember`."*
- The skill must instruct the agent how to handle `MemoryResult.status == "incompatible"` — read `diagnostics.expected_schema` and retry.
- **Tool discovery follows the Agent Skills model exactly: the library scans the `memories/` folder for MEMORY.md manifests; no bindings file or explicit tool registration is needed.**

**Deliverables:**

- `skills/memories/SKILL.md`
- `skills/memories/scripts/skill_entry.py`
- `skills/memories/README.md`

---

## Component 2: The Default MEMORY.md Set

**Default universal memory:**

Every installation should include `memories/default/MEMORY.md`. This is the baseline memory type for agentic input: a very small, universal place to save "some text" or stringified JSON when no more specific memory type is needed. Skills and memory tools should assume this `default` memory exists unless a deployment explicitly removes it.

Minimal shape:

```yaml
---
name: default
description: Universal default memory for arbitrary agentic input
purpose: factual
schema:
  content: str
recall_hints:
  typical_query: Free-text lookup across saved default memories
  recency_matters: true
lifecycle:
  importance: medium
  forgettable: true
---

# Default Memory

Use this memory for simple text notes or stringified JSON payloads that do not fit a more specific memory type.
```

**Manifest format:**

```yaml
---
name: <unique_snake_case_identifier>
description: <one-line human-readable purpose>
purpose: <observational | procedural | episodic | factual | preferential | corrective>
schema:
  <field_name>: <type>
recall_hints:
  typical_query: <string>
  recency_matters: <bool>
lifecycle:
  importance: <low | medium | high>
  forgettable: <bool>
---

# <Memory Type Name>

<Markdown body>
```

**Notes:**
- The `schema` block uses simple type names: `str`, `int`, `float`, `bool`, `datetime`, `date`, `list[str]`, `list[float]`, `dict`.
- Frontmatter MUST NOT contain storage strategy, backend, or implementation hints.
- The markdown body is loaded into agent context when the memory type is active.

**Default memory types to ship:**

- `default` — universal fallback memory for simple text or stringified JSON input

**Deliverables:**

- `memories/default/MEMORY.md` as the required baseline memory
- `memories/README.md`

---

## Component 3: The agentic-memories Python Library

**Package:** `agentic-memories` — `pip install agentic-memories`

**Core public API:**

```python
from agentic_memories import (
    Registry,        # loads and indexes MEMORY.md folders
    Triage,          # ranks memory types by relevance
    MemoryResult,    # standardized result contract (Pydantic model)
    invoke_remember, # routes a payload to the discovered tool
    invoke_recall,   # routes a query to the discovered tool
    smoke_test,      # runs startup smoke tests
)
```

**Registry:**

- `Registry.load(path: str) -> Registry` — scan a `memories/` folder, parse all MEMORY.md files. **Discovery works exactly as skill discovery: a subfolder with a MEMORY.md is sufficient. No bindings file required.**
- `.list() -> list[ManifestSummary]`
- `.get(name: str) -> Manifest`
- `.schema_model_for(name: str) -> type[BaseModel]`

> **No `Bindings` class.** The user's `tool_invoker` callable is responsible for routing by memory type name, exactly as a skill runner routes by skill name.

**Triage:**

- `Triage(registry: Registry, llm_client: Callable)`
- `.rank(input_text: str, top_k: int = 3) -> list[TriageCandidate]`
- Non-LLM fallback ranking (keyword/embedding) MUST also be available.

**MemoryResult:**

```python
class MemoryResult(BaseModel):
    status: Literal["ok", "incompatible", "transient_error", "permanent_error"]
    memory_id: str | None = None
    data: list[dict] | None = None
    reason: str | None = None
    diagnostics: dict | None = None   # MUST include 'expected_schema' on incompatible
    retry_after_seconds: int | None = None
```

**`invoke_remember(memory_type, payload, registry, tool_invoker) -> MemoryResult`:**

1. Look up manifest in registry. Not found → `permanent_error`.
2. Soft-validate payload; log warning on mismatch, proceed.
3. Call `tool_invoker(memory_type, {"payload": payload})`. **Memory type name is the routing key — no binding lookup needed.**
4. Return tool's `MemoryResult` unchanged.

`invoke_recall` follows the same pattern with a `query` argument.

**`smoke_test(registry, tool_invoker, dry_run: bool = True) -> SmokeReport`:**

For each discovered memory type, generate a sample payload, invoke tool_invoker with `dry_run=True`, collect results. Used at startup to catch manifest/tool drift.

**Library MUST NOT:**
- Depend on any specific LLM SDK or agent framework
- Implement any storage backend
- Know how to invoke tools directly
- Read or require a `bindings.yaml`

**Memory-only usage:**

The library supports deployments that do not install or invoke `skills/memories/`. In that mode, the application loads `Registry.load("./memories")`, chooses a memory type itself or through `Triage`, and calls `invoke_remember` / `invoke_recall` directly with its own `tool_invoker`.

**Deliverables:**
- `agentic_memories/` Python package source
- `pyproject.toml`
- Unit tests: manifest parsing, schema model generation, soft validation, invoke flows, smoke test, triage
- `README.md`

---

## Component 4: Example Scripts

**Skill-based example flow (`examples/example_with_skill.py`):**

1. Load the memories skill folder (read SKILL.md for context).
2. Invoke `skills/memories/scripts/skill_entry.py` as the skill adapter.
3. The skill loads the registry from `./memories/` — **no `bindings.yaml`; discovery is folder-based**.
4. Call the skill's `triage(input_text)` operation. With the default set, it should select `default`.
5. Call the skill's `describe("default")` operation and use OpenAI to construct a payload conforming to the manifest schema.
6. Call the skill's `remember("default", {"content": <text_or_stringified_json>})` operation.
7. The skill routes to `tool_invoker(memory_type_name, {"payload": <payload>})`, as a skill runner would.
8. Tool walks every field recursively, concatenates `"sss"` to every value, saves to `./memory_storage/<memory_type>/<uuid>.json`, returns `MemoryResult(status="ok")`.
9. Print `MemoryResult` to stdout.

**Memory-only example flow (`examples/example_direct_memories.py`):**

1. Load the registry directly with `Registry.load("./memories")`.
2. Run `smoke_test(registry, tool_invoker, dry_run=True)` at startup.
3. Use `Triage(registry, llm_client=...)` to choose the best memory type for the task.
4. Recall the latest stored haiku from the selected memory type.
5. Use OpenAI to construct the next haiku payload matching the selected manifest schema.
6. Call `invoke_remember(memory_type, payload, registry, tool_invoker)` directly.
7. Tool saves the payload to `./memory_storage/<memory_type>/<uuid>.json` and returns `MemoryResult(status="ok")`.
8. Print `MemoryResult` to stdout.

**Pydantic AI example flow (`examples/example_pydantic_ai_memories.py`):**

1. Load the registry directly with `Registry.load("./memories")`.
2. Run `smoke_test(registry, tool_invoker, dry_run=True)` at startup.
3. Create a Pydantic AI `Agent` with memory tools for triaging, describing, recalling, and remembering MEMORY.md records.
4. Instruct the model to call the `triage_memory` tool, use the ranked candidate, recall the latest haiku, write the next haiku, and store it.
5. The tools call `invoke_recall` and `invoke_remember`; the application does not select or write records directly.
6. Print the agent's final structured summary after the remember tool succeeds.

**Constraints:**
- Direct examples: only `openai`, `agentic-memories`, `python-dotenv`, and stdlib.
- Framework example: `pydantic-ai`, `agentic-memories`, and `python-dotenv`.
- Runnable files: `python examples/example_with_skill.py`, `python examples/example_direct_memories.py`, and `python examples/example_pydantic_ai_memories.py`.
- OpenAI credentials via environment variables.
- **No `bindings.yaml`.** `tool_invoker` is a plain Python callable dispatching by memory type name.
- All examples run `smoke_test` at startup.
- Logs soft-validation warning if payload mismatches schema, then proceeds.

**Deliverables:**
- `examples/example_with_skill.py`
- `examples/example_direct_memories.py`
- `examples/example_pydantic_ai_memories.py`
- `skills/memories/` — the memories skill used by the example
- `memories/default/MEMORY.md` — the only default memory type
- `README.md`
- Skill example hardcoded input: `"User said they prefer concise responses with no emoji"`

---

## Out of Scope

- Specific storage backends — these are the user's tools
- Session/working memory or session-close consolidation
- Pre-analyzer integration with a reasoning loop
- Production framework-specific adapters (LangChain, etc.)
- Lifecycle automation (decay, TTL, consolidation)
- Authentication, multi-tenancy, access control
- A2A protocol integration
- Web UI or dashboard
- **A `bindings.yaml` or any explicit binding/registration mechanism**

---

## Implementation Order (Suggested)

1. **Component 3** — agentic-memories library (everything else depends on it)
2. **Component 2** — default MEMORY.md set (can be drafted in parallel)
3. **Component 1** — memories skill (depends on library being installable)
4. **Component 4** — example script (integration test for all three)
