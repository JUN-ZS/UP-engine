from __future__ import annotations

from pathlib import Path

from ..reasoning import ReasoningProposalSet, parse_reasoning_response


OUTPUT_SCHEMA_PROMPT = """You are a visual inspection component inside a constrained image reconstruction engine.
Propose visible objects, visible object parts and directly observable 2D relations.
Do not write a final image prompt. Do not claim hidden 3D facts from one 2D image.
Distinguish visible evidence from plausible assumptions. If a contact, occlusion or attachment is ambiguous, omit that relation and explain the uncertainty.
Return only one valid JSON object. No Markdown fences or prose outside JSON.
Coordinates are normalized 0.0 to 1.0, origin top-left, x right, y down.
Never declare anything human-verified. Every output remains a model proposal.

Return this exact top-level shape:
{
  "nodes": [
    {
      "id": "short_unique_id",
      "label": "concise visible name",
      "semantic_type": "person|face|hand|garment|hammer_head|cylindrical_end_face|shaft_side|hair|background|other",
      "bbox_xyxy_norm": [0.0, 0.0, 1.0, 1.0],
      "visual_evidence": "what is directly visible inside this box",
      "uncertainty": "low|medium|high|unknown"
    }
  ],
  "relations": [
    {
      "id": "short_unique_relation_id",
      "subject_id": "node id",
      "predicate": "part_of|occludes|in_front_of|behind|touches|contacts_at|attached_to|aligned_with|opposes|parallel_to|perpendicular_to|same_object_as",
      "object_id": "node id",
      "confidence": 0.0,
      "evidence_bbox_xyxy_norm": [0.0, 0.0, 1.0, 1.0],
      "visual_evidence": "specific visible features supporting the relation",
      "uncertainty": "low|medium|high|unknown",
      "details": {}
    }
  ],
  "uncertainties": ["unresolved question or ambiguity"]
}

Rules:
- Every node and relation has a normalized box, with x1 < x2 and y1 < y2.
- Relations may only reference node IDs present in nodes.
- For contacts_at, details must contain subject_surface and object_surface. Name actual surface types, e.g. cylindrical_end_face, shaft_side, flat_plate_face, hand_palm. Do not call generic overlap a contact.
- For a T-shaped hammer, distinguish hammer_head, cylindrical_end_face and shaft_side where visible. Do not assert two end faces oppose/contact unless those actual faces visibly meet.
- For occludes/in_front_of/behind, evidence_bbox should cover the visible overlap/boundary, not just an object center.
- Confidence is an uncalibrated self-assessment, not a probability.
- Do not infer unseen back faces, hidden joints, exact 3D angles, physical forces or camera calibration.
- Empty arrays are acceptable. Prefer fewer defensible claims over complete guessed scene graphs.
"""


class QwenSpatialReasoner:
    """Optional local Qwen3.8 (or compatible Qwen vision-language) adapter.

    Install Transformers as an optional dependency and a compatible PyTorch build.
    This class loads weights only when the user explicitly selects this adapter.
    """

    provider_id = "qwen.qwen3.8"
    DEFAULT_MODEL_ID = "Qwen/Qwen3.8-27B"

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        *,
        max_new_tokens: int = 1600,
    ) -> None:
        try:
            from transformers import AutoProcessor, AutoModelForMultimodalLM
            ModelClass = AutoModelForMultimodalLM
        except ImportError as exc:
            raise RuntimeError(
                "Qwen3.8 reasoning requires Transformers >= 5.8.1. Install UP-engine with the vlm extra "
                "and install a compatible PyTorch build separately."
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
            f"Inspection focus: {focus.strip() or 'whole image'}\\n\\n"
            + OUTPUT_SCHEMA_PROMPT
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
