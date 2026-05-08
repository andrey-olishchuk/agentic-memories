from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agentic_memories.schema import schema_as_jsonable
from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_ENTRY = PROJECT_ROOT / "skills" / "memories" / "scripts" / "skill_entry.py"

EXAMPLE_INPUT = "User said they prefer concise responses with no emoji"


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    run_skill("smoke_test", {})
    candidates = run_skill("triage", {"input_text": EXAMPLE_INPUT, "top_k": 1})
    memory_type = candidates[0]["name"]
    manifest = run_skill("describe", {"memory_type": memory_type})
    payload = build_payload_with_openai(EXAMPLE_INPUT, manifest["schema"])
    result = run_skill(
        "remember",
        {"memory_type": memory_type, "payload": payload},
    )
    print(json.dumps(result, indent=2, sort_keys=True))


def run_skill(operation: str, arguments: dict[str, Any]) -> Any:
    completed = subprocess.run(
        [
            sys.executable,
            str(SKILL_ENTRY),
            operation,
            json.dumps(arguments),
        ],
        check=True,
        capture_output=True,
        cwd=PROJECT_ROOT,
        text=True,
    )
    return json.loads(completed.stdout)


def build_payload_with_openai(input_text: str, schema: dict[str, str]) -> dict[str, Any]:
    client = OpenAI()
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=(
            "Convert this input into a MEMORY.md payload. "
            f"Return JSON matching the schema.\nInput: {input_text}"
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


if __name__ == "__main__":
    main()
