from __future__ import annotations

import warnings
from pathlib import Path

from ..reasoner_prompt import REASONER_OUTPUT_SCHEMA_PROMPT
from ..reasoning import ReasoningProposalSet, parse_reasoning_response


OUTPUT_SCHEMA_PROMPT = REASONER_OUTPUT_SCHEMA_PROMPT  # backward-compatible alias


class QwenSpatialReasoner:
    """DEPRECATED local Qwen vision-language adapter.

    Retained only for historical comparison. Grok Vision is the active READ
    reasoner. This adapter is not on the default CLI path and must never be
    used as a silent fallback when Grok fails.
    """

    provider_id = "qwen.qwen3.8"
    DEFAULT_MODEL_ID = "Qwen/Qwen3.8-27B"
    DEPRECATED = True

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        *,
        max_new_tokens: int = 1600,
    ) -> None:
        warnings.warn(
            "QwenSpatialReasoner is deprecated. Prefer --reasoner grok (xAI Grok Vision). "
            "Qwen remains available only for explicit comparison and is not a fallback.",
            DeprecationWarning,
            stacklevel=2,
        )
        try:
            from transformers import AutoProcessor, AutoModelForImageTextToText
            ModelClass = AutoModelForImageTextToText
        except ImportError as exc:
            raise RuntimeError(
                "Qwen3.8 reasoning requires Transformers >= 5.8.1. Install UP-engine with the vlm extra "
                "and install a compatible PyTorch build separately. "
                "Note: Qwen is deprecated; the default READ path is Grok Vision."
            ) from exc
        self.model_id = model_id
        self.max_new_tokens = max_new_tokens
        try:
            self.processor = AutoProcessor.from_pretrained(model_id)
            self.model = ModelClass.from_pretrained(
                model_id,
                dtype="auto",
                device_map="auto",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Could not load {model_id}. Check model access, disk space, RAM/VRAM, "
                "Transformers/PyTorch versions and checkpoint compatibility."
            ) from exc

    def propose(
        self,
        image_path: str | Path,
        *,
        focus: str = "Inspect the whole image, including object parts, boundaries, contact and occlusion.",
    ) -> ReasoningProposalSet:
        source = Path(image_path)
        if not source.is_file():
            raise FileNotFoundError(source)
        prompt = (
            f"Inspection focus: {focus.strip() or 'whole image'}\n\n"
            + REASONER_OUTPUT_SCHEMA_PROMPT
        )
        from PIL import Image
        with Image.open(source) as opened:
            image = opened.convert("RGB").copy()
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }]
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
            enable_thinking=False,
        ).to(self.model.device)
        generated = self.model.generate(
            **inputs,
            max_new_tokens=self.max_new_tokens,
            do_sample=False,
        )
        trimmed = [
            output[len(input_ids):]
            for input_ids, output in zip(inputs["input_ids"], generated)
        ]
        response = self.processor.batch_decode(
            trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]
        return parse_reasoning_response(
            response,
            provider_id=self.provider_id,
            model_id=self.model_id,
        )


# Backward-compatible name retained for existing callers.
Qwen3VLReasoner = QwenSpatialReasoner
