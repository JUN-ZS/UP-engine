from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class MaskProposal:
    """A model-proposed object mask. It is never writable until reviewed by a human."""

    proposal_id: str
    prompt: str
    score: float
    mask: np.ndarray


class SegmentationProvider(Protocol):
    provider_id: str

    def segment_text(
        self, image_path: str | Path, prompts: list[str]
    ) -> list[MaskProposal]:
        """Return candidate masks for text concepts; do not assign edit permissions."""
        ...
