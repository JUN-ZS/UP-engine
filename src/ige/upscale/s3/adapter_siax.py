from __future__ import annotations

import gc
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from .adapter_base import ChildRunResult, ChildRunSpec, UpscaleAdapter


class SiaxAdapter(UpscaleAdapter):
    """Siax compute-child adapter: one forward per child, native PNG + receipt.

    Does not claim quality PASS / E3 / original 256/32 equivalence.
    """

    adapter_id = "siax.esgan.4x"
    model_id = "4x_NMKD-Siax_200k"
    scale = 4

    def __init__(
        self,
        checkpoint: str | Path,
        *,
        device: str = "cpu",
        confirm_model_license_review: bool = False,
    ):
        if not confirm_model_license_review:
            raise PermissionError("confirm_model_license_review required for SiaxAdapter")
        self.checkpoint = Path(checkpoint)
        self.device = device
        self._sha: str | None = None
        self._desc = None
        self._torch = None

    def weight_sha256(self) -> str:
        if self._sha is None:
            from ige.upscale.siax import MODEL_SHA256, file_sha256

            actual = file_sha256(self.checkpoint)
            if actual != MODEL_SHA256:
                raise ValueError(f"checkpoint hash mismatch: {actual}")
            self._sha = actual
        return self._sha

    def _ensure_model(self) -> None:
        if self._desc is not None:
            return
        import os

        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")
        os.environ.setdefault("TORCH_NUM_THREADS", "1")
        import torch
        from spandrel import ImageModelDescriptor, ModelLoader

        torch.set_num_threads(1)
        self._torch = torch
        device = self.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("cuda requested but unavailable")
        self.device = device
        desc = ModelLoader(device=device).load_from_file(str(self.checkpoint))
        if not isinstance(desc, ImageModelDescriptor) or int(desc.scale) != 4:
            raise ValueError("bad Siax model descriptor")
        desc.eval()
        self._desc = desc
        self.weight_sha256()

    def run_child(self, spec: ChildRunSpec) -> ChildRunResult:
        self._ensure_model()
        from ige.upscale.siax import file_sha256

        torch = self._torch
        t0 = time.perf_counter()
        with Image.open(spec.base_path) as im:
            base = np.asarray(ImageOps.exif_transpose(im).convert("RGB"), dtype=np.uint8)
        ex0, ey0, ex1, ey1 = [int(v) for v in spec.input_box_base]
        cx0, cy0, cx1, cy1 = [int(v) for v in spec.core_box_base]
        crop = base[ey0:ey1, ex0:ex1].astype(np.float32) / 255.0
        tensor = torch.from_numpy(crop).permute(2, 0, 1).unsqueeze(0)
        if self.device == "cuda":
            tensor = tensor.to("cuda")
        with torch.inference_mode():
            out = self._desc(tensor).float().cpu()
        pred = out[0].permute(1, 2, 0).numpy()
        pred_u8 = np.clip(pred * 255.0 + 0.5, 0, 255).astype(np.uint8)
        left = (cx0 - ex0) * self.scale
        top = (cy0 - ey0) * self.scale
        right = left + (cx1 - cx0) * self.scale
        bottom = top + (cy1 - cy0) * self.scale
        core = pred_u8[top:bottom, left:right]
        out_uri = Path(spec.extra["out_uri"]) if spec.extra and spec.extra.get("out_uri") else None
        if out_uri is None:
            raise ValueError("spec.extra.out_uri required")
        out_uri.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(core, "RGB").save(out_uri, format="PNG", compress_level=1)
        sha = file_sha256(out_uri)
        wall = time.perf_counter() - t0
        peak = None
        try:
            import resource

            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        except Exception:
            pass
        del tensor, out, pred, pred_u8, core, crop
        gc.collect()
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
            "input_box_base": [ex0, ey0, ex1, ey1],
            "output_box_hires": list(spec.output_box_hires),
            "wall_s": round(wall, 4),
            "peak_rss_mib": peak,
            "peak_vram_mib": None,
            "status": "ok",
            "error": None,
        }
        return ChildRunResult(
            child_id=spec.child_id,
            uri=str(out_uri),
            sha256=sha,
            wall_s=wall,
            peak_rss_mib=peak,
            status="ok",
            receipt=receipt,
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
                "Not E3 speed claim",
            ],
        }
