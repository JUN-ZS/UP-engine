"""Candidate-to-BASE registration gate.

UP-engine compositor never auto-resizes or warps. This adapter only measures
whether a candidate is already pixel-aligned with BASE dimensions and records
registration quality. It never invents a geometric transform that the
compositor would silently apply.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


class RegistrationError(ValueError):
    """Candidate cannot enter the compositor without explicit registration work."""


@dataclass(frozen=True)
class RegistrationReport:
    registration_quality: str
    base_width: int
    base_height: int
    candidate_width: int
    candidate_height: int
    dimensions_match: bool
    transformation: dict[str, Any]
    registration_residual: dict[str, Any]
    base_sha256: str
    candidate_sha256: str
    allowed_for_compositor: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "registration_quality": self.registration_quality,
            "base": {
                "width": self.base_width,
                "height": self.base_height,
                "sha256": self.base_sha256,
            },
            "candidate": {
                "width": self.candidate_width,
                "height": self.candidate_height,
                "sha256": self.candidate_sha256,
            },
            "dimensions_match": self.dimensions_match,
            "transformation": self.transformation,
            "registration_residual": self.registration_residual,
            "allowed_for_compositor": self.allowed_for_compositor,
            "notes": list(self.notes),
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assess_registration(
    base_image_path: str | Path,
    candidate_image_path: str | Path,
    *,
    expected_base_sha256: str | None = None,
) -> RegistrationReport:
    """Assess whether a candidate is already registered to BASE pixel space.

    Current policy (honest v0.1):
    - Exact EXIF-corrected display dimensions must match.
    - No automatic affine/homography estimation is performed.
    - If dimensions differ, registration_quality = failed and compositor is blocked.
    - If dimensions match, registration_quality = pending_dimension_match_only —
      size match is necessary but not sufficient for geometric correctness.
    """
    base_path = Path(base_image_path)
    candidate_path = Path(candidate_image_path)
    if not base_path.is_file():
        raise FileNotFoundError(base_path)
    if not candidate_path.is_file():
        raise FileNotFoundError(candidate_path)

    base_sha = _sha256(base_path)
    if expected_base_sha256 is not None and base_sha != expected_base_sha256:
        raise RegistrationError("BASE SHA-256 does not match the generation packet")

    with Image.open(base_path) as opened:
        base = ImageOps.exif_transpose(opened)
        base_w, base_h = base.size
    with Image.open(candidate_path) as opened:
        candidate = ImageOps.exif_transpose(opened)
        cand_w, cand_h = candidate.size

    dimensions_match = (base_w, base_h) == (cand_w, cand_h)
    if dimensions_match:
        quality = "pending_dimension_match_only"
        allowed = True
        notes = (
            "Candidate display dimensions match BASE.",
            "Dimension match is not geometric registration proof.",
            "Identity, pose, topology and lock preservation remain separate gates.",
            "No transform was applied; transformation is identity.",
        )
        transformation = {
            "type": "identity",
            "scale_x": 1.0,
            "scale_y": 1.0,
            "translation_x": 0.0,
            "translation_y": 0.0,
            "rotation_deg": 0.0,
            "applied": False,
        }
        residual = {
            "status": "not_measured",
            "pixel_rmse": None,
            "note": "No dense residual computed in v0.1 registration adapter.",
        }
    else:
        quality = "failed"
        allowed = False
        notes = (
            "Candidate dimensions differ from BASE.",
            "Automatic resize/warp is forbidden.",
            "Do not send this candidate to the compositor.",
            "Mark E2E registration as BLOCKED until an explicit registered candidate exists.",
        )
        scale_x = cand_w / float(base_w) if base_w else None
        scale_y = cand_h / float(base_h) if base_h else None
        transformation = {
            "type": "unresolved_scale_mismatch",
            "scale_x": scale_x,
            "scale_y": scale_y,
            "translation_x": None,
            "translation_y": None,
            "rotation_deg": None,
            "applied": False,
        }
        residual = {
            "status": "failed",
            "pixel_rmse": None,
            "width_delta": cand_w - base_w,
            "height_delta": cand_h - base_h,
        }

    return RegistrationReport(
        registration_quality=quality,
        base_width=base_w,
        base_height=base_h,
        candidate_width=cand_w,
        candidate_height=cand_h,
        dimensions_match=dimensions_match,
        transformation=transformation,
        registration_residual=residual,
        base_sha256=base_sha,
        candidate_sha256=_sha256(candidate_path),
        allowed_for_compositor=allowed,
        notes=notes,
    )


def require_registration_for_composite(
    base_image_path: str | Path,
    candidate_image_path: str | Path,
    *,
    expected_base_sha256: str | None = None,
) -> RegistrationReport:
    report = assess_registration(
        base_image_path,
        candidate_image_path,
        expected_base_sha256=expected_base_sha256,
    )
    if not report.allowed_for_compositor:
        raise RegistrationError(
            f"registration_quality={report.registration_quality}; "
            f"candidate {report.candidate_width}x{report.candidate_height} "
            f"vs BASE {report.base_width}x{report.base_height}"
        )
    return report
