from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps


class ReconstructionError(ValueError):
    """The candidate cannot be safely composited against this generation packet."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _packet_artifact(packet_dir: Path, relative_name: str) -> Path:
    path = (packet_dir / relative_name).resolve()
    if not path.is_relative_to(packet_dir.resolve()):
        raise ReconstructionError(f"packet artifact path escapes the packet directory: {relative_name}")
    if not path.is_file():
        raise ReconstructionError(f"packet artifact is missing: {relative_name}")
    return path


def composite_candidate(
    packet_path: str | Path,
    base_image_path: str | Path,
    candidate_image_path: str | Path,
    output_image_path: str | Path,
    *,
    candidate_model_id: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Composite only authorized pixels from a registered candidate into immutable BASE.

    The candidate must already be registered to the exact BASE pixel dimensions.
    This stage never resizes, warps or guesses alignment. It is a pixel-preservation
    compositor, not an image generator or a geometry/identity acceptance model.
    """
    packet_file = Path(packet_path)
    base_path = Path(base_image_path)
    candidate_path = Path(candidate_image_path)
    output_path = Path(output_image_path)
    if not packet_file.is_file():
        raise FileNotFoundError(packet_file)
    if not base_path.is_file():
        raise FileNotFoundError(base_path)
    if not candidate_path.is_file():
        raise FileNotFoundError(candidate_path)
    if output_path.suffix.lower() != ".png":
        raise ReconstructionError("strict pixel-preserving composite output must use lossless .png")
    audit_path = output_path.with_name(output_path.name + ".audit.json")
    if not overwrite and (output_path.exists() or audit_path.exists()):
        raise FileExistsError(output_path if output_path.exists() else audit_path)
    protected_input_paths = {
        packet_file.resolve(),
        base_path.resolve(),
        candidate_path.resolve(),
    }
    if output_path.resolve() in protected_input_paths or audit_path.resolve() in protected_input_paths:
        raise ReconstructionError(
            "output and audit paths must not overwrite the packet, immutable BASE, or candidate input"
        )

    packet = json.loads(packet_file.read_text(encoding="utf-8"))
    if packet.get("packet_version") != "0.1.0":
        raise ReconstructionError("unsupported generation packet version")
    packet_dir = packet_file.parent.resolve()
    base_spec = packet.get("base", {})
    width, height = base_spec.get("width"), base_spec.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ReconstructionError("generation packet has invalid BASE dimensions")
    expected_base_sha = base_spec.get("sha256")
    actual_base_sha = _sha256(base_path)
    if actual_base_sha != expected_base_sha:
        raise ReconstructionError("BASE SHA-256 does not match generation packet")

    authorization = packet.get("pixel_authorization", {})
    generation_mask_path = _packet_artifact(packet_dir, authorization.get("generation_mask", ""))
    protected_mask_path = _packet_artifact(packet_dir, authorization.get("protected_mask", ""))
    if output_path.resolve() in {generation_mask_path.resolve(), protected_mask_path.resolve()} or audit_path.resolve() in {generation_mask_path.resolve(), protected_mask_path.resolve()}:
        raise ReconstructionError("output paths must not overwrite packet mask inputs")
    if _sha256(generation_mask_path) != authorization.get("generation_mask_sha256"):
        raise ReconstructionError("generation mask SHA-256 does not match packet")
    if _sha256(protected_mask_path) != authorization.get("protected_mask_sha256"):
        raise ReconstructionError("protected mask SHA-256 does not match packet")

    with Image.open(base_path) as opened:
        base_has_alpha = "A" in opened.getbands() or "transparency" in opened.info
        icc_profile = opened.info.get("icc_profile")
        dpi = opened.info.get("dpi")
        base_image = ImageOps.exif_transpose(opened).convert("RGBA" if base_has_alpha else "RGB")
    with Image.open(candidate_path) as opened:
        candidate_image = ImageOps.exif_transpose(opened).convert("RGBA" if base_has_alpha else "RGB")
    if base_image.size != (width, height):
        raise ReconstructionError(
            f"BASE display dimensions {base_image.size} do not match packet {(width, height)}"
        )
    if candidate_image.size != (width, height):
        raise ReconstructionError(
            f"candidate dimensions {candidate_image.size} do not match BASE {(width, height)}; "
            "register it explicitly first; automatic resize is forbidden"
        )

    with Image.open(generation_mask_path) as opened:
        generation_mask_image = opened.convert("L")
    with Image.open(protected_mask_path) as opened:
        protected_mask_image = opened.convert("L")
    if generation_mask_image.size != (width, height) or protected_mask_image.size != (width, height):
        raise ReconstructionError("packet mask dimensions do not match BASE")
    generation_mask = np.asarray(generation_mask_image, dtype=np.uint8)
    protected_mask = np.asarray(protected_mask_image, dtype=np.uint8)
    if not set(np.unique(generation_mask)).issubset({0, 255}):
        raise ReconstructionError("generation mask must be binary (0 or 255)")
    if not set(np.unique(protected_mask)).issubset({0, 255}):
        raise ReconstructionError("protected mask must be binary (0 or 255)")
    if not np.array_equal(protected_mask, 255 - generation_mask):
        raise ReconstructionError("protected mask is not the exact complement of generation mask")
    authorized_pixels = int(np.count_nonzero(generation_mask))
    if authorized_pixels != authorization.get("generation_pixels"):
        raise ReconstructionError("generation pixel count does not match packet")

    base_array = np.asarray(base_image, dtype=np.uint8)
    candidate_array = np.asarray(candidate_image, dtype=np.uint8)
    write_region = generation_mask > 0
    composed_array = base_array.copy()
    composed_array[write_region] = candidate_array[write_region]

    changed = np.any(composed_array != base_array, axis=2)
    changed_outside = int(np.count_nonzero(changed & ~write_region))
    changed_inside = int(np.count_nonzero(changed & write_region))
    if changed_outside != 0:
        raise ReconstructionError(
            f"pixel preservation failure: {changed_outside} pixels changed outside the generation mask"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed = Image.fromarray(composed_array, mode="RGBA" if base_has_alpha else "RGB")
    save_kwargs: dict[str, Any] = {}
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile
    if dpi:
        save_kwargs["dpi"] = dpi
    composed.save(output_path, format="PNG", **save_kwargs)

    # Verify the encoded file, not only the pre-save array. PNG is lossless, but the
    # post-write check guards future changes to this compositor's save path.
    with Image.open(output_path) as saved_image:
        saved_array = np.asarray(saved_image.convert("RGBA" if base_has_alpha else "RGB"), dtype=np.uint8)
    saved_changed = np.any(saved_array != base_array, axis=2)
    saved_changed_outside = int(np.count_nonzero(saved_changed & ~write_region))
    if saved_changed_outside != 0:
        output_path.unlink(missing_ok=True)
        raise ReconstructionError(
            f"encoded image changed {saved_changed_outside} pixels outside the generation mask"
        )
    changed_inside = int(np.count_nonzero(saved_changed & write_region))
    audit: dict[str, Any] = {
        "audit_version": "0.1.0",
        "status": "composited_candidate_not_accepted",
        "task_id": packet.get("task_id"),
        "base": {
            "path": str(base_path.resolve()),
            "sha256": actual_base_sha,
            "width": width,
            "height": height,
        },
        "candidate": {
            "path": str(candidate_path.resolve()),
            "sha256": _sha256(candidate_path),
            "model_id": candidate_model_id,
            "registered_dimensions_match_base": True,
            "registration_quality": "not_measured_by_this_compositor",
        },
        "authorization": {
            "generation_mask_sha256": authorization["generation_mask_sha256"],
            "protected_mask_sha256": authorization["protected_mask_sha256"],
            "authorized_pixels": authorized_pixels,
        },
        "output": {
            "path": str(output_path.resolve()),
            "sha256": _sha256(output_path),
            "format": "PNG",
        },
        "pixel_diff": {
            "changed_pixels_inside_authorized_region": changed_inside,
            "changed_pixels_outside_authorized_region": saved_changed_outside,
            "outside_mask_preservation": "pass",
            "full_frame_changed_fraction": round(
                float(np.count_nonzero(changed)) / float(width * height), 8
            ),
        },
        "hard_gates": {
            "parent_source_identity": "pass",
            "mask_integrity": "pass",
            "protected_region_pixel_preservation": "pass",
            "mask_leakage": "pass",
            "registration_quality": "pending",
            "identity": "pending",
            "pose": "pending",
            "topology": "pending",
            "geometry_lock_preservation": "pending",
            "native_resolution": "pass",
        },
        "final_acceptance": False,
        "limitations": [
            "This stage composites an already registered candidate; it does not generate or align images.",
            "Matching image dimensions do not prove correct geometric registration.",
            "Identity, pose, topology and human-verified relation preservation require separate validators.",
            "The result remains a candidate and must not replace immutable BASE until all required gates pass.",
        ],
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit
