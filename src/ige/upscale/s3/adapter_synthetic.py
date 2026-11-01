from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from .adapter_base import ChildRunResult, ChildRunSpec, UpscaleAdapter


class SyntheticNearestAdapter(UpscaleAdapter):
    """Deterministic nearest-neighbor 4x for transport/scheduler/rebuild tests.

    Not a quality model. Not Siax. Used only for S3 dispatch integrity smoke.
    """

    adapter_id = "synthetic.nearest.4x"
    model_id = "synthetic_nearest_4x"
    scale = 4

    def weight_sha256(self) -> str:
        return hashlib.sha256(b"synthetic_nearest_4x_v0").hexdigest()

    def run_child(self, spec: ChildRunSpec) -> ChildRunResult:
        t0 = time.perf_counter()
        with Image.open(spec.base_path) as im:
            base = ImageOps.exif_transpose(im).convert("RGB")
        cx0, cy0, cx1, cy1 = [int(v) for v in spec.core_box_base]
        crop = base.crop((cx0, cy0, cx1, cy1))
        hi = crop.resize((crop.size[0] * self.scale, crop.size[1] * self.scale), Image.Resampling.NEAREST)
        out_uri = Path(spec.extra["out_uri"])
        out_uri.parent.mkdir(parents=True, exist_ok=True)
        hi.save(out_uri, format="PNG", compress_level=1)
        raw = out_uri.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        wall = time.perf_counter() - t0
        # optional sleep to simulate work for lease tests
        sleep_s = float((spec.extra or {}).get("simulate_s") or 0)
        if sleep_s > 0:
            time.sleep(sleep_s)
        receipt = {
            "receipt_version": "1.0",
            "child_id": spec.child_id,
            "job_id": (spec.extra or {}).get("job_id", ""),
            "worker_id": (spec.extra or {}).get("worker_id", ""),
            "adapter_id": self.adapter_id,
            "model_id": self.model_id,
            "model_sha256": self.weight_sha256(),
            "uri": str(out_uri),
            "sha256": sha,
            "core_box_base": [cx0, cy0, cx1, cy1],
            "input_box_base": list(spec.input_box_base),
            "output_box_hires": list(spec.output_box_hires),
            "wall_s": round(wall + sleep_s, 4),
            "peak_rss_mib": None,
            "peak_vram_mib": None,
            "status": "ok",
            "error": None,
        }
        return ChildRunResult(
            child_id=spec.child_id,
            uri=str(out_uri),
            sha256=sha,
            wall_s=wall + sleep_s,
            peak_rss_mib=None,
            status="ok",
            receipt=receipt,
        )
