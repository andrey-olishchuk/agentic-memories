# Memories

Use this skill to discover and use `MEMORY.md` memory types.

When you have data to remember, first call `triage`, then call `describe` to read the schema, then call `remember`.

Available operations:

- `list_memory_types()` returns discovered memory types with name, purpose, description, and schema.
- `triage(input_text)` ranks candidate memory types.
- `describe(memory_type)` returns the full manifest.
- `remember(memory_type, payload)` sends the payload to the routed memory tool.
- `recall(memory_type, query)` sends a recall query to the routed memory tool.

If `MemoryResult.status == "incompatible"`, read `diagnostics.expected_schema`, build a corrected payload, and retry `remember`.

Tool discovery follows the same model as skills: scan the `memories/` folder for subfolders containing `MEMORY.md`. There is no `bindings.yaml` and no registration step.
