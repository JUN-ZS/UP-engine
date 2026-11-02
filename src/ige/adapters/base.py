from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any


@dataclass(frozen=True)
class GenerationRequest:
    task_id: str
    prompt: str
    input_assets: tuple[str, ...]
    generation_mask_uri: str | None
    seed: int | None
    parameters: dict[str, Any]


@dataclass(frozen=True)
class GenerationResult:
    adapter_id: str
    output_uri: str
    model_version: str
    seed: int | None
    raw_metadata_uri: str | None = None


class ImageModelAdapter(Protocol):
    """Provider boundary. Implementations must not silently composite into BASE."""

    adapter_id: str

    def generate(self, request: GenerationRequest) -> GenerationResult:
        ...
