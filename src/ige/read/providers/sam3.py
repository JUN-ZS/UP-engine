from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .base import MaskProposal


class Sam3TextSegmenter:
    """Lazy adapter for Meta SAM 3 / SAM 3.1 text-prompt image segmentation.

    The heavyweight SAM3 package and gated model checkpoint are intentionally not
    dependencies of UP-engine's default installation.
    """

    provider_id = "meta.sam3-text"

    def __init__(self) -> None:
        try:
            from sam3.model_builder import build_sam3_image_model
            from sam3.model.sam3_image_processor import Sam3Processor
        except ImportError as exc:
            raise RuntimeError(
                "SAM3 is not installed in this environment. Install it in a dedicated "
                "Python 3.12+/PyTorch 2.7+/CUDA 12.6+ environment; see docs/READ_ENGINE.md."
            ) from exc
        try:
            self.model = build_sam3_image_model()
            self.processor = Sam3Processor(self.model)
        except Exception as exc:
            raise RuntimeError(
                "SAM3 model initialization failed. Verify CUDA/PyTorch compatibility "
                "and that you have accepted the SAM3 checkpoint access request."
            ) from exc

    @staticmethod
    def _numpy(value: object) -> np.ndarray:
        if hasattr(value, "detach"):
            value = value.detach().cpu().numpy()
        return np.asarray(value)

    def segment_text(
        self, image_path: str | Path, prompts: list[str]
    ) -> list[MaskProposal]:
        if not prompts:
            raise ValueError("SAM3 segmentation requires at least one text prompt")
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
        state = self.processor.set_image(image)
        width, height = image.size
        proposals: list[MaskProposal] = []
        for prompt_index, prompt in enumerate(prompts):
            text = prompt.strip()
            if not text:
                raise ValueError("segmentation prompts must be non-empty")
            output = self.processor.set_text_prompt(state=state, prompt=text)
            if "masks" not in output:
                raise RuntimeError("SAM3 output did not contain masks")
            masks = self._numpy(output["masks"])
            if masks.ndim == 2:
                masks = masks[None, ...]
            elif masks.ndim == 4 and masks.shape[1] == 1:
                masks = masks[:, 0, :, :]
            elif masks.ndim == 4 and masks.shape[-1] == 1:
                masks = masks[:, :, :, 0]
            if masks.ndim != 3:
                raise RuntimeError(f"unsupported SAM3 mask tensor shape: {masks.shape}")
            if masks.shape[1:] != (height, width):
                raise RuntimeError(
                    "SAM3 mask dimensions do not match the source image; refusing to "
                    "silently resize a geometry-bearing mask"
                )
            raw_scores = output.get("scores")
            scores = (
                self._numpy(raw_scores).reshape(-1)
                if raw_scores is not None
                else np.ones((masks.shape[0],), dtype=np.float32)
            )
            for mask_index, raw_mask in enumerate(masks):
                mask = np.asarray(raw_mask > 0.5, dtype=np.uint8) * 255
                if not np.any(mask):
                    continue
                score = float(scores[min(mask_index, len(scores) - 1)])
                proposals.append(
                    MaskProposal(
                        proposal_id=f"sam3-{prompt_index:02d}-{mask_index:03d}",
                        prompt=text,
                        score=max(0.0, min(1.0, score)),
                        mask=mask,
                    )
                )
        return proposals
