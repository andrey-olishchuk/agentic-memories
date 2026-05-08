from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .manifest import ManifestError, load_manifest
from .models import Manifest, ManifestSummary
from .schema import schema_model


class Registry:
    def __init__(self, manifests: dict[str, Manifest], root: Path):
        self._manifests = manifests
        self.root = root

    @classmethod
    def load(cls, path: str) -> "Registry":
        root = Path(path)
        if not root.exists():
            raise FileNotFoundError(f"Memories directory not found: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Memories path is not a directory: {root}")

        manifests: dict[str, Manifest] = {}
        for child in sorted(root.iterdir()):
            manifest_path = child / "MEMORY.md"
            if not child.is_dir() or not manifest_path.exists():
                continue

            manifest = load_manifest(manifest_path)
            if manifest.name in manifests:
                first_path = manifests[manifest.name].path
                raise ManifestError(
                    f"Duplicate memory type {manifest.name!r}: {first_path} and {manifest_path}"
                )
            manifests[manifest.name] = manifest

        return cls(manifests=manifests, root=root)

    def list(self) -> list[ManifestSummary]:
        return [manifest.summary() for manifest in self._manifests.values()]

    def get(self, name: str) -> Manifest:
        try:
            return self._manifests[name]
        except KeyError as exc:
            raise KeyError(f"Memory type not found: {name}") from exc

    def schema_model_for(self, name: str) -> type[BaseModel]:
        manifest = self.get(name)
        return schema_model(manifest.name, manifest.schema)

    def __contains__(self, name: str) -> bool:
        return name in self._manifests

    def __iter__(self):
        return iter(self._manifests.values())
