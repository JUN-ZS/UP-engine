from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .adapter_base import ChildRunResult, ChildRunSpec, UpscaleAdapter


class SiaxAdapter(UpscaleAdapter):
    """Siax adapter shell — wires identity; full forward may call existing siax path.

    v0 exposes descriptor + SHA check so scheduler/transport can be tested without
    claiming a new quality cell.
    """

    adapter_id = "siax.esgan.4x"
    model_id = "4x_NMKD-Siax_200k"
    scale = 4

    def __init__(self, checkpoint: str | Path, *, device: str = "cpu"):
        self.checkpoint = Path(checkpoint)
        self.device = device
        self._sha: str | None = None

    def weight_sha256(self) -> str:
        if self._sha is None:
            from ige.upscale.siax import MODEL_SHA256, file_sha256

            actual = file_sha256(self.checkpoint)
            if actual != MODEL_SHA256:
                raise ValueError(f"checkpoint hash mismatch: {actual}")
            self._sha = actual
        return self._sha

    def run_child(self, spec: ChildRunSpec) -> ChildRunResult:
        """Placeholder: not used for quality claims in S3.0.

        Real inference should reuse nested_compute / distributed worker paths.
        """
        raise NotImplementedError(
            "S3.0 ships adapter identity only; wire nested/distributed forward in S3.3"
        )

    def descriptor(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "model_family": "esrgan_siax",
            "scale": self.scale,
            "run_unit": "compute_child",
            "model_id": self.model_id,
            "weight_sha256": self.weight_sha256() if self.checkpoint.is_file() else None,
            "device": self.device,
            "notes": [
                "Siax is one adapter among future model workers",
                "Does not rewrite S2.1 quality decision",
            ],
        }
