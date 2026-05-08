# Memories Skill

This is a small Agent Skills style adapter around `agentic-memories`.

For local demos, run:

```bash
python skills/memories/scripts/skill_entry.py triage '{"input_text":"User said they prefer concise responses with no emoji"}'
```

The adapter discovers memory types from `./memories` by default. Override with `MEMORIES_PATH`.
