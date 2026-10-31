from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from PIL import Image, ImageDraw, ImageOps
import numpy as np

from .annotations import RegionAnnotation, RegionRole, load_regions, rasterize_region
from .providers.base import MaskProposal, SegmentationProvider


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raster_metrics(image: Image.Image) -> dict[str, Any]:
    """Compute low-cost pixel statistics; these are not semantic image understanding."""
    sample = image.copy()
    sample.thumbnail((512, 512), Image.Resampling.LANCZOS)
    rgb = np.asarray(sample.convert("RGB"), dtype=np.float32) / 255.0
    gray = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:] = np.abs(gray[:, 1:] - gray[:, :-1])
    gy[1:, :] = np.abs(gray[1:, :] - gray[:-1, :])
    gradient = np.hypot(gx, gy)
    edge_threshold = 0.15
    return {
        "sample_size": {"width": int(sample.width), "height": int(sample.height)},
        "mean_rgb_0_1": [round(float(v), 5) for v in rgb.mean(axis=(0, 1))],
        "std_rgb_0_1": [round(float(v), 5) for v in rgb.std(axis=(0, 1))],
        "mean_luminance_0_1": round(float(gray.mean()), 5),
        "luminance_std_0_1": round(float(gray.std()), 5),
        "edge_density_at_threshold_0_15": round(float((gradient >= edge_threshold).mean()), 5),
        "edge_metric_note": "A simple raster statistic, not an object boundary or quality score.",
    }


def _bbox(mask: np.ndarray) -> list[int] | None:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def _save_mask(mask: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(mask, dtype=np.uint8), mode="L").save(path)


def _save_preview(
    image: Image.Image,
    path: Path,
    editable: np.ndarray,
    explicit_protected: np.ndarray,
    context: np.ndarray,
    proposals: list[MaskProposal],
) -> None:
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layers = [
        (editable, (20, 220, 90, 90)),
        (explicit_protected, (235, 45, 45, 100)),
        (context, (45, 135, 245, 70)),
    ]
    for mask, color in layers:
        tint = Image.new("RGBA", base.size, color)
        alpha = Image.fromarray(np.asarray(mask, dtype=np.uint8), mode="L")
        overlay.alpha_composite(Image.composite(tint, Image.new("RGBA", base.size), alpha))
    # Model proposals are outlined separately; they do not alter accepted masks.
    draw = ImageDraw.Draw(overlay)
    for proposal in proposals:
        box = _bbox(proposal.mask)
        if box:
            draw.rectangle(box, outline=(255, 190, 30, 230), width=max(1, round(min(base.size) / 500)))
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(base, overlay).convert("RGB").save(path, quality=92)


def _serialize_region(region: RegionAnnotation, mask: np.ndarray) -> dict[str, Any]:
    height, width = mask.shape
    pixels = int(np.count_nonzero(mask))
    return {
        "id": region.region_id,
        "label": region.label,
        "role": region.role.value,
        "source": "human_annotation",
        "bbox_xyxy_pixels": _bbox(mask),
        "area_pixels": pixels,
        "area_fraction": round(pixels / float(width * height), 8),
        "polygon_normalized_0_1": [list(point) for point in region.polygon],
    }


def run_read(
    image_path: str | Path,
    output_dir: str | Path,
    *,
    regions_path: str | Path | None = None,
    provider: SegmentationProvider | None = None,
    prompts: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Read one still image and export auditable metrics, overlays, and masks.

    Only human-annotated regions with role='editable' become writable. All pixels
    outside that mask are included in the effective protected mask by default.
    Provider masks are always proposals and never confer edit permission.
    """
    source = Path(image_path)
    destination = Path(output_dir)
    if not source.is_file():
        raise FileNotFoundError(f"input image not found: {source}")
    if destination.exists() and not destination.is_dir():
        raise NotADirectoryError(f"output path is not a directory: {destination}")
    if destination.exists() and any(destination.iterdir()) and not overwrite:
        raise FileExistsError(f"output directory is not empty: {destination} (use --overwrite)")
    destination.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        original_format = opened.format
        original_mode = opened.mode
        has_alpha = "A" in opened.getbands()
        image = ImageOps.exif_transpose(opened).convert("RGB")
    width, height = image.size
    if width < 1 or height < 1:
        raise ValueError("source image has invalid dimensions")

    annotations = load_regions(regions_path)
    editable = np.zeros((height, width), dtype=np.uint8)
    explicit_protected = np.zeros((height, width), dtype=np.uint8)
    context = np.zeros((height, width), dtype=np.uint8)
    object_regions = np.zeros((height, width), dtype=np.uint8)
    region_rows: list[dict[str, Any]] = []
    per_region: list[tuple[RegionAnnotation, np.ndarray]] = []
    for region in annotations:
        mask = rasterize_region(region, width, height)
        per_region.append((region, mask))
        region_rows.append(_serialize_region(region, mask))
        if region.role == RegionRole.EDITABLE:
            editable = np.maximum(editable, mask)
        elif region.role == RegionRole.PROTECTED:
            explicit_protected = np.maximum(explicit_protected, mask)
        elif region.role == RegionRole.CONTEXT:
            context = np.maximum(context, mask)
        elif region.role == RegionRole.OBJECT:
            object_regions = np.maximum(object_regions, mask)

    overlap = (editable > 0) & (explicit_protected > 0)
    if np.any(overlap):
        raise ValueError(
            f"editable and protected annotations overlap in {int(overlap.sum())} pixels; "
            "resolve the conflict before generating"
        )
    effective_protected = np.where(editable > 0, 0, 255).astype(np.uint8)
    annotated_union = np.maximum.reduce([editable, explicit_protected, context, object_regions])
    unlabelled = np.where(annotated_union > 0, 0, 255).astype(np.uint8)

    provider_prompts = [p.strip() for p in (prompts or []) if p and p.strip()]
    proposals: list[MaskProposal] = []
    provider_id = None
    if provider is not None:
        if not provider_prompts:
            raise ValueError("at least one --prompt is required when a segmentation provider is used")
        provider_id = provider.provider_id
        proposals = provider.segment_text(source, provider_prompts)
        for proposal in proposals:
            if proposal.mask.shape != (height, width):
                raise ValueError(
                    f"provider proposal {proposal.proposal_id!r} has shape {proposal.mask.shape}, "
                    f"expected {(height, width)}; refusing implicit resize"
                )
            if not 0.0 <= proposal.score <= 1.0:
                raise ValueError(f"proposal score out of range: {proposal.score}")

    masks_dir = destination / "masks"
    _save_mask(editable, masks_dir / "editable.png")
    _save_mask(explicit_protected, masks_dir / "explicit_protected.png")
    _save_mask(effective_protected, masks_dir / "protected_effective.png")
    _save_mask(context, masks_dir / "context.png")
    _save_mask(unlabelled, masks_dir / "unlabelled.png")

    region_mask_rows = []
    for region, mask in per_region:
        region_file = f"region-{region.region_id}.png"
        _save_mask(mask, masks_dir / "regions" / region_file)
        region_mask_rows.append({"id": region.region_id, "mask": f"masks/regions/{region_file}"})

    proposal_rows = []
    for index, proposal in enumerate(proposals):
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", proposal.proposal_id).strip("-.") or f"proposal-{index}"
        proposal_file = f"{index:03d}-{safe_id}.png"
        _save_mask(proposal.mask, destination / "proposals" / proposal_file)
        pixels = int(np.count_nonzero(proposal.mask))
        proposal_rows.append({
            "id": proposal.proposal_id,
            "prompt": proposal.prompt,
            "score": round(proposal.score, 6),
            "status": "unreviewed_proposal",
            "mask": f"proposals/{proposal_file}",
            "bbox_xyxy_pixels": _bbox(proposal.mask),
            "area_pixels": pixels,
            "area_fraction": round(pixels / float(width * height), 8),
            "edit_permission": False,
        })

    _save_preview(image, destination / "preview.png", editable, explicit_protected, context, proposals)
    total_pixels = width * height
    editable_pixels = int(np.count_nonzero(editable))
    explicit_protected_pixels = int(np.count_nonzero(explicit_protected))
    report: dict[str, Any] = {
        "read_version": "0.1.0",
        "source": {
            "path": str(source.resolve()),
            "sha256": _sha256(source),
            "width": width,
            "height": height,
            "format": original_format,
            "original_mode": original_mode,
            "has_alpha": has_alpha,
            "orientation": "EXIF-transposed-to-display-orientation",
        },
        "raster_metrics": _raster_metrics(image),
        "semantic_segmentation": {
            "provider": provider_id,
            "prompts": provider_prompts,
            "proposal_count": len(proposal_rows),
            "status": "unreviewed_proposals" if provider is not None else "not_run",
            "note": "Segmentation proposals are not verified scene understanding and never authorize editing.",
        },
        "regions": region_rows,
        "region_masks": region_mask_rows,
        "proposals": proposal_rows,
        "mask_policy": {
            "editable_pixels": editable_pixels,
            "explicit_protected_pixels": explicit_protected_pixels,
            "effective_protected_pixels": total_pixels - editable_pixels,
            "unlabelled_pixels": int(np.count_nonzero(unlabelled)),
            "editable_fraction": round(editable_pixels / float(total_pixels), 8),
            "default": "Only human-annotated editable pixels are writable; every other pixel is effectively protected.",
            "semantic_proposals_grant_permission": False,
        },
        "interpretation": {
            "status": "partial_read",
            "semantic_scene_graph": "not_claimed",
            "physical_geometry_and_occlusion": "not_claimed",
            "human_review_required": True,
        },
        "limitations": [
            "Raster statistics describe pixel distributions only; they do not identify objects or materials.",
            "Semantic model masks are proposals. They must be visually checked and explicitly accepted as annotations.",
            "Object contact, part connectivity, camera geometry, and occlusion order are not inferred by this stage.",
            "Unannotated pixels are not authorized for modification.",
        ],
    }
    (destination / "analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_text = [
        "# READ report",
        "",
        f"- Source SHA-256: {report['source']['sha256']}",
        f"- Dimensions: {width} x {height}",
        f"- Semantic proposals: {len(proposal_rows)} ({report['semantic_segmentation']['status']})",
        f"- Human editable coverage: {editable_pixels}/{total_pixels} pixels ({report['mask_policy']['editable_fraction']:.2%})",
        f"- Effective protected coverage: {total_pixels - editable_pixels}/{total_pixels} pixels",
        "",
        "## Mask files",
        "",
        "- preview.png: editable tint, explicit protected tint, context tint, and proposal bounding boxes.",
        "- masks/editable.png: only explicitly human-annotated editable pixels.",
        "- masks/protected_effective.png: complement of the editable mask; safe default for preservation.",
        "- masks/explicit_protected.png: explicit human-protected regions.",
        "- masks/context.png: human-annotated context areas.",
        "- masks/unlabelled.png: pixels not covered by any human region annotation.",
        "- proposals/: model proposal masks, always unreviewed.",
        "",
        "## Safety interpretation",
        "",
        "No semantic model proposal is automatically accepted as editable. Review the preview and masks, then create or revise the human region annotation file. Unlabelled pixels remain protected by default.",
        "",
        "This report is a partial image read, not a claim that physical geometry, part topology, identity, or occlusion has been understood.",
    ]
    (destination / "READ_REPORT.md").write_text("\n".join(report_text) + "\n", encoding="utf-8")
    return report
