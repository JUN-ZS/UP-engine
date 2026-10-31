from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class Transform:
    kind: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class PEEPManifest:
    manifest_version: str
    task_id: str
    parent_asset_id: str
    generation_mask: str
    protected_mask: str
    context_ring: str | None
    transform: Transform
    adapter_id: str
    seed: int | None
    output_uri: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PEEPManifest":
        required = ["manifest_version", "task_id", "parent_asset_id", "generation_mask",
                    "protected_mask", "transform", "adapter_id", "output_uri"]
        missing = [key for key in required if key not in raw]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        transform = raw["transform"]
        if not isinstance(transform, dict) or not transform.get("kind"):
            raise ValueError("transform.kind is required")
        manifest = cls(
            manifest_version=str(raw["manifest_version"]),
            task_id=str(raw["task_id"]),
            parent_asset_id=str(raw["parent_asset_id"]),
            generation_mask=str(raw["generation_mask"]),
            protected_mask=str(raw["protected_mask"]),
            context_ring=raw.get("context_ring"),
            transform=Transform(str(transform["kind"]), dict(transform.get("parameters", {}))),
            adapter_id=str(raw["adapter_id"]),
            seed=raw.get("seed"),
            output_uri=str(raw["output_uri"]),
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        for name in ("manifest_version", "task_id", "parent_asset_id", "generation_mask",
                     "protected_mask", "adapter_id", "output_uri"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.generation_mask == self.protected_mask:
            raise ValueError("generation_mask and protected_mask must be distinct")
        if self.seed is not None and (not isinstance(self.seed, int) or self.seed < 0):
            raise ValueError("seed must be a non-negative integer or null")


def load_manifest(path: str | Path) -> PEEPManifest:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("manifest root must be a JSON object")
    return PEEPManifest.from_dict(raw)
