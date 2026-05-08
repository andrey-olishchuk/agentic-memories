from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import Manifest


class ManifestError(ValueError):
    pass


def load_manifest(path: str | Path) -> Manifest:
    manifest_path = Path(path)
    text = manifest_path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text, manifest_path)
    data = _parse_simple_yaml(frontmatter)
    try:
        return Manifest.model_validate({**data, "body": body.strip(), "path": manifest_path})
    except ValidationError as exc:
        raise ManifestError(f"Invalid MEMORY.md at {manifest_path}: {exc}") from exc


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ManifestError(f"{path} must start with YAML frontmatter delimited by ---")

    try:
        _, frontmatter, body = text.split("---\n", 2)
    except ValueError as exc:
        raise ManifestError(f"{path} is missing closing frontmatter delimiter") from exc
    return frontmatter, body


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset used by MEMORY.md frontmatter.

    The manifest spec only needs nested maps, booleans, strings, and simple
    scalar type names such as list[str]. Keeping this parser narrow avoids a
    runtime YAML dependency in the core package.
    """

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            raise ManifestError(f"Invalid frontmatter line: {raw_line!r}")

        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ManifestError(f"Invalid indentation near line: {raw_line!r}")

        parent = stack[-1][1]
        if raw_value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(raw_value)

    return root


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value
