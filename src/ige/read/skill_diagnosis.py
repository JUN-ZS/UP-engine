from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .providers.xai_grok import GrokSpatialReasoner


SKILL_DIAGNOSIS_OBSERVATIONS = (
    "identity_drift",
    "topology_error",
    "garment_pattern_error",
    "face_detail_low",
    "skin_noise",
    "metal_detail_low",
    "stone_detail_low",
    "text_detail_low",
    "fire_detail_low",
    "background_detail_low",
    "defocus_blur",
    "motion_blur",
    "compression_artifacts",
    "jpeg_blocks",
    "oversharpening_ringing",
    "color_noise",
    "low_resolution_undersampling",
)


class SkillDiagnosisError(ValueError):
    """Grok produced a malformed or unsupported skill diagnosis."""


SKILL_DIAGNOSIS_PROMPT = """You are performing a conservative visual defect diagnosis for an image reconstruction pipeline.

Image order:
- Image 1 is the BASE image to diagnose.
- Image 2, when supplied, is the canonical identity reference (a8b or another explicitly provided reference).
- Do not assume a reference image exists if only one image is supplied.

Return JSON only, with this exact top-level shape:
{
  "observations": {
    "<observation_name>": {
      "state": "present | absent | unknown",
      "evidence": "short, directly visible explanation",
      "bbox_xyxy_norm": [x1, y1, x2, y2],
      "confidence": 0.0,
      "uncertainty": "low | medium | high"
    }
  }
}

You MUST include every observation name listed below:
identity_drift, topology_error, garment_pattern_error, face_detail_low,
skin_noise, metal_detail_low, stone_detail_low, text_detail_low,
fire_detail_low, background_detail_low, defocus_blur, motion_blur,
compression_artifacts, jpeg_blocks, oversharpening_ringing, color_noise,
low_resolution_undersampling.

Rules:
1. Use state=present only when the defect is directly visible and explain the visual evidence.
2. Use state=absent only when the relevant region is visible enough to assess and the defect is not seen.
3. Use state=unknown when the region is absent, too small, occluded, ambiguous, or cannot be judged.
4. If no canonical identity reference was supplied, identity_drift MUST be unknown. Never infer identity drift from appearance alone.
5. topology_error concerns object part count, connectivity, shape and physical construction, not merely an unusual pose.
6. garment_pattern_error concerns broken, discontinuous or structurally inconsistent garment patterns, not an aesthetic preference.
7. face_detail_low is about insufficient recoverable face detail, not whether the face is attractive.
8. skin_noise is visible artificial texture, ringing, oversharpening or noisy skin, not normal pores.
9. metal_detail_low / stone_detail_low / text_detail_low / fire_detail_low / background_detail_low refer only to visible detail insufficiency in those material regions.
10. A bounding box is optional. When supplied, it must tightly cover the affected region using normalized coordinates from 0 to 1.
11. Confidence is uncalibrated and must not be used as an acceptance score.
12. Do not prescribe sharpening or upscale before structural/topology diagnosis.
13. Do not claim pixel-perfect, geometric, identity or final acceptance.
14. Every finding is a model candidate for human review, not verified truth.
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_facts(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened)
        width, height = image.size
        image_format = opened.format
        mode = opened.mode
    return {
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "width": width,
        "height": height,
        "format": image_format,
        "mode": mode,
    }


def _validate_bbox(value: Any, name: str) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4:
        raise SkillDiagnosisError(f"{name}.bbox_xyxy_norm must be four numbers")
    try:
        coords = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise SkillDiagnosisError(f"{name}.bbox_xyxy_norm contains a non-number") from exc
    x1, y1, x2, y2 = coords
    if any(item < 0 or item > 1 for item in coords) or x2 <= x1 or y2 <= y1:
        raise SkillDiagnosisError(f"{name}.bbox_xyxy_norm is outside the normalized image or has no area")
    return coords


class GrokSkillDiagnoser:
    """Grok Vision image diagnosis adapter that emits candidate-only router input."""

    def __init__(
        self,
        *,
        model_id: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        detail: str = "high",
        timeout_seconds: float = 180.0,
        transport: Any | None = None,
    ) -> None:
        self.reasoner = GrokSpatialReasoner(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            detail=detail,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    def diagnose(
        self,
        image_path: str | Path,
        *,
        identity_reference: str | Path | None = None,
        identity_reference_id: str | None = None,
        focus: str = "Assess structural integrity first, then identity, material detail and image-quality defects.",
    ) -> dict[str, Any]:
        base = Path(image_path)
        base_facts = _image_facts(base)
        image_paths = [base]
        reference_facts = None
        if identity_reference is not None:
            reference = Path(identity_reference)
            reference_facts = _image_facts(reference)
            image_paths.append(reference)

        prompt = (
            f"Inspection focus: {focus.strip() or 'whole image'}\n"
            f"Canonical identity reference supplied: {'yes' if reference_facts else 'no'}\n"
            f"Identity reference ID: {identity_reference_id or 'not supplied'}\n\n"
            + SKILL_DIAGNOSIS_PROMPT
        )
        response_text, request_meta = self.reasoner.request_text(image_paths, prompt)
        try:
            raw = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise SkillDiagnosisError("Grok skill diagnosis must be strict JSON; no repair is attempted") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("observations"), dict):
            raise SkillDiagnosisError("Grok diagnosis requires an observations object")

        unknown = set(raw["observations"]) - set(SKILL_DIAGNOSIS_OBSERVATIONS)
        if unknown:
            raise SkillDiagnosisError(f"unsupported observation names: {sorted(unknown)}")

        observations: dict[str, dict[str, Any]] = {}
        for name in SKILL_DIAGNOSIS_OBSERVATIONS:
            item = raw["observations"].get(name)
            if item is None:
                observations[name] = {
                    "state": "unknown",
                    "evidence": "The model did not return this observation.",
                    "source": "grok_vision",
                    "verification": "candidate",
                    "uncertainty": "high",
                }
                continue
            if not isinstance(item, dict):
                raise SkillDiagnosisError(f"observation {name} must be an object")
            state = item.get("state")
            if state not in {"present", "absent", "unknown"}:
                raise SkillDiagnosisError(f"observation {name}.state is invalid")
            evidence = str(item.get("evidence", "")).strip()
            if state == "present" and not evidence:
                raise SkillDiagnosisError(f"present observation {name} requires visible evidence")
            normalized: dict[str, Any] = {
                "state": state,
                "evidence": evidence,
                "source": "grok_vision",
                "verification": "candidate",
                "uncertainty": str(item.get("uncertainty", "high")),
            }
            bbox = _validate_bbox(item.get("bbox_xyxy_norm"), name)
            if bbox is not None:
                normalized["bbox_xyxy_norm"] = bbox
            if item.get("confidence") is not None:
                try:
                    confidence = float(item["confidence"])
                except (TypeError, ValueError) as exc:
                    raise SkillDiagnosisError(f"observation {name}.confidence is invalid") from exc
                if confidence < 0 or confidence > 1:
                    raise SkillDiagnosisError(f"observation {name}.confidence must be in [0, 1]")
                normalized["confidence_uncalibrated"] = confidence
            observations[name] = normalized

        if reference_facts is None:
            observations["identity_drift"] = {
                "state": "unknown",
                "evidence": "No identity reference image was supplied; identity drift cannot be assessed.",
                "source": "grok_vision",
                "verification": "candidate",
                "uncertainty": "high",
            }

        return {
            "diagnosis_version": "1.0",
            "image": base_facts,
            "observations": observations,
            "references": (
                [{
                    "role": "identity_reference",
                    "asset_id": identity_reference_id,
                    **reference_facts,
                }]
                if reference_facts else []
            ),
            "diagnosis_meta": {
                **request_meta,
                "task": "skill_defect_diagnosis",
                "observation_count": len(observations),
                "verification": "candidate_only",
                "confidence_note": "All confidence values are uncalibrated and are not acceptance scores.",
            },
            "next_action": "ige skill-plan BASE --diagnosis diagnosis.json; review all model findings before promoting any observation to human_verified.",
            "final_acceptance": False,
        }
