from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ChildRunSpec:
    child_id: str
    base_path: str
    core_box_base: list[int]
    input_box_base: list[int]
    output_box_hires: list[int]
    extra: dict[str, Any] | None = None


@dataclass
class ChildRunResult:
    child_id: str
    uri: str
    sha256: str
    wall_s: float
    peak_rss_mib: float | None
    status: str
    receipt: dict[str, Any]


class UpscaleAdapter(ABC):
    adapter_id: str
    model_id: str
    scale: int

    @abstractmethod
    def weight_sha256(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def run_child(self, spec: ChildRunSpec) -> ChildRunResult:
        raise NotImplementedError
