from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageOps


class GeometryTileError(ValueError):
    """The object geometry contract or two-tile experiment is invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise GeometryTileError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise GeometryTileError(f"{label} must be finite")
    return result


def _rect(value: Any, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise GeometryTileError(f"{label} must be [x0, y0, x1, y1]")
    result = [_finite_number(x, label) for x in value]
    if result[2] <= result[0] or result[3] <= result[1]:
        raise GeometryTileError(f"{label} must have positive width and height")
    return result


def _clip_bbox(box: list[float], rect: list[float]) -> list[float] | None:
    result = [
        max(box[0], rect[0]),
        max(box[1], rect[1]),
        min(box[2], rect[2]),
        min(box[3], rect[3]),
    ]
    if result[2] <= result[0] or result[3] <= result[1]:
        return None
    return result


def _clip_polygon(points: list[list[float]], rect: list[float]) -> list[list[float]]:
    """Sutherland-Hodgman clip against an axis-aligned rectangle."""
    output = [[float(p[0]), float(p[1])] for p in points]
    boundaries = (
        (0, rect[0], True),
        (0, rect[2], False),
        (1, rect[1], True),
        (1, rect[3], False),
    )
    for axis, bound, keep_greater in boundaries:
        if not output:
            break
        incoming = output
        output = []

        def inside(point: list[float]) -> bool:
            return point[axis] >= bound if keep_greater else point[axis] <= bound

        previous = incoming[-1]
        previous_inside = inside(previous)
        for current in incoming:
            current_inside = inside(current)
            if current_inside != previous_inside:
                delta = current[axis] - previous[axis]
                if abs(delta) > 1e-12:
                    ratio = (bound - previous[axis]) / delta
                    other = 1 - axis
                    cross = [0.0, 0.0]
                    cross[axis] = bound
                    cross[other] = previous[other] + ratio * (current[other] - previous[other])
                    output.append(cross)
            if current_inside:
                output.append(current)
            previous, previous_inside = current, current_inside
    return output


def _polygon_area(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point[0] * nxt[1] - nxt[0] * point[1]
    return abs(total) * 0.5


def _bbox_from_points(points: list[list[float]]) -> list[float]:
    return [
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    ]


def _validate_contract(
    raw: Any,
    *,
    width: int,
    height: int,
    source_sha256: str,
) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("schema_version") != "ige-object-geometry/1.0":
        raise GeometryTileError("schema_version must be ige-object-geometry/1.0")
    if raw.get("geometry_status") != "human_verified":
        raise GeometryTileError("object geometry must be human_verified; model proposals cannot create locks")
    source = raw.get("source")
    if not isinstance(source, dict):
        raise GeometryTileError("source metadata is required")
    if source.get("sha256") != source_sha256:
        raise GeometryTileError("source SHA-256 does not match the supplied image")
    if (source.get("width"), source.get("height")) != (width, height):
        raise GeometryTileError("source dimensions do not match the EXIF-corrected image")

    obj = raw.get("object")
    if not isinstance(obj, dict) or not isinstance(obj.get("id"), str) or not obj["id"].strip():
        raise GeometryTileError("object.id is required")
    bbox = _rect(obj.get("bbox_xyxy"), "object.bbox_xyxy")
    if bbox[0] < 0 or bbox[1] < 0 or bbox[2] > width or bbox[3] > height:
        raise GeometryTileError("object bbox must lie inside the source canvas")

    polygon_raw = obj.get("polygon_xy")
    if not isinstance(polygon_raw, list) or len(polygon_raw) < 3:
        raise GeometryTileError("object.polygon_xy must contain at least three points")
    polygon = []
    for index, point in enumerate(polygon_raw):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise GeometryTileError(f"object.polygon_xy[{index}] must be an [x, y] pair")
        x = _finite_number(point[0], "polygon x")
        y = _finite_number(point[1], "polygon y")
        if x < 0 or y < 0 or x > width or y > height:
            raise GeometryTileError("object polygon must lie inside the source canvas")
        polygon.append([x, y])
    if _polygon_area(polygon) <= 1e-6:
        raise GeometryTileError("object polygon is degenerate")
    poly_box = _bbox_from_points(polygon)
    if any(poly_box[i] < bbox[i] - 1e-4 or poly_box[i] > bbox[i] + 1e-4 for i in (0, 1, 2, 3)):
        raise GeometryTileError("object bbox must tightly enclose the declared polygon")

    landmarks_raw = obj.get("landmarks", {})
    if not isinstance(landmarks_raw, dict):
        raise GeometryTileError("object.landmarks must be an object keyed by landmark name")
    landmarks: dict[str, list[float]] = {}
    for name, point in landmarks_raw.items():
        if not isinstance(name, str) or not name:
            raise GeometryTileError("landmark names must be non-empty strings")
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise GeometryTileError(f"landmark {name} must be an [x, y] pair")
        x = _finite_number(point[0], f"landmark {name} x")
        y = _finite_number(point[1], f"landmark {name} y")
        if x < bbox[0] or x > bbox[2] or y < bbox[1] or y > bbox[3]:
            raise GeometryTileError(f"landmark {name} lies outside the object bbox")
        landmarks[name] = [x, y]

    tolerance_raw = raw.get("tolerances")
    if not isinstance(tolerance_raw, dict):
        raise GeometryTileError("explicit experiment tolerances are required")
    tolerances = {
        "bbox_iou_min": _finite_number(tolerance_raw.get("bbox_iou_min"), "bbox_iou_min"),
        "silhouette_iou_min": _finite_number(tolerance_raw.get("silhouette_iou_min"), "silhouette_iou_min"),
        "landmark_max_px": _finite_number(tolerance_raw.get("landmark_max_px"), "landmark_max_px"),
        "overlap_silhouette_iou_min": _finite_number(
            tolerance_raw.get("overlap_silhouette_iou_min"), "overlap_silhouette_iou_min"
        ),
        "overlap_landmark_max_px": _finite_number(
            tolerance_raw.get("overlap_landmark_max_px"), "overlap_landmark_max_px"
        ),
    }
    for key in ("bbox_iou_min", "silhouette_iou_min", "overlap_silhouette_iou_min"):
        if not 0.0 <= tolerances[key] <= 1.0:
            raise GeometryTileError(f"{key} must be between 0 and 1")
    for key in ("landmark_max_px", "overlap_landmark_max_px"):
        if tolerances[key] < 0:
            raise GeometryTileError(f"{key} must be non-negative")

    return {
        "schema_version": raw["schema_version"],
        "geometry_status": "human_verified",
        "source": {"sha256": source_sha256, "width": width, "height": height},
        "object": {
            "id": obj["id"],
            "bbox_xyxy": bbox,
            "polygon_xy": polygon,
            "landmarks": landmarks,
        },
        "tolerances": tolerances,
        "provenance": raw.get("provenance", {}),
    }


def _translate_polygon(points: list[list[float]], origin_x: float, origin_y: float) -> list[list[float]]:
    return [[p[0] - origin_x, p[1] - origin_y] for p in points]


def _local_object_geometry(contract: dict[str, Any], crop: list[int]) -> dict[str, Any]:
    obj = contract["object"]
    visible_bbox = _clip_bbox(obj["bbox_xyxy"], [float(v) for v in crop])
    if visible_bbox is None:
        raise GeometryTileError("object does not intersect a planned tile crop")
    visible_polygon = _clip_polygon(obj["polygon_xy"], [float(v) for v in crop])
    if len(visible_polygon) < 3 or _polygon_area(visible_polygon) <= 1e-6:
        raise GeometryTileError("object polygon does not have visible area in a planned tile")
    x0, y0, _, _ = crop
    local_landmarks = {
        name: [point[0] - x0, point[1] - y0]
        for name, point in obj["landmarks"].items()
        if x0 <= point[0] <= crop[2] and y0 <= point[1] <= crop[3]
    }
    return {
        "object_id": obj["id"],
        "bbox_xyxy": [visible_bbox[0] - x0, visible_bbox[1] - y0,
                      visible_bbox[2] - x0, visible_bbox[3] - y0],
        "polygon_xy": _translate_polygon(visible_polygon, x0, y0),
        "landmarks": local_landmarks,
        "coordinate_frame": "tile_crop_local_px",
        "derived_from_global_contract": True,
    }


def _iou(box_a: list[float], box_b: list[float]) -> float:
    intersection = _clip_bbox(box_a, box_b)
    if intersection is None:
        return 0.0
    area_i = (intersection[2] - intersection[0]) * (intersection[3] - intersection[1])
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    return float(area_i / max(area_a + area_b - area_i, 1e-12))


def _polygon_iou(
    polygon_a: list[list[float]],
    polygon_b: list[list[float]],
    width: int,
    height: int,
) -> float:
    if width <= 0 or height <= 0:
        return 0.0
    mask_a = Image.new("1", (width, height), 0)
    mask_b = Image.new("1", (width, height), 0)
    ImageDraw.Draw(mask_a).polygon([tuple(p) for p in polygon_a], fill=1)
    ImageDraw.Draw(mask_b).polygon([tuple(p) for p in polygon_b], fill=1)
    a = np.asarray(mask_a, dtype=bool)
    b = np.asarray(mask_b, dtype=bool)
    intersection = int(np.count_nonzero(a & b))
    union = int(np.count_nonzero(a | b))
    return float(intersection / union) if union else 1.0


def plan_two_tile_generation(
    source_image_path: str | Path,
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    split_x: int,
    overlap_px: int,
) -> dict[str, Any]:
    """Create two overlapping generation crops with disjoint reconstruction cores.

    Global object geometry is immutable input. Tile-local geometry is derived by
    coordinate translation and polygon clipping; Tile dimensions never rescale
    the object contract.
    """
    source_path = Path(source_image_path)
    contract_file = Path(contract_path)
    out = Path(output_dir)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if not contract_file.is_file():
        raise FileNotFoundError(contract_file)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"output directory is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    source_sha = _sha256(source_path)
    with Image.open(source_path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    width, height = image.size
    contract_raw = json.loads(contract_file.read_text(encoding="utf-8"))
    contract = _validate_contract(
        contract_raw, width=width, height=height, source_sha256=source_sha
    )
    if not isinstance(split_x, int) or not 1 <= split_x < width:
        raise GeometryTileError("split_x must be an integer inside the canvas")
    if not isinstance(overlap_px, int) or overlap_px < 1:
        raise GeometryTileError("overlap_px must be a positive integer")

    obj_bbox = contract["object"]["bbox_xyxy"]
    if not (obj_bbox[0] < split_x < obj_bbox[2]):
        raise GeometryTileError(
            "the experiment requires the split line to cross the object's global bbox"
        )
    overlap_left = max(0, split_x - overlap_px)
    overlap_right = min(width, split_x + overlap_px)
    if overlap_right <= overlap_left:
        raise GeometryTileError("the two tile crops have no shared overlap")
    shared_rect = [overlap_left, 0, overlap_right, height]
    if _clip_bbox(obj_bbox, [float(v) for v in shared_rect]) is None:
        raise GeometryTileError("the shared tile overlap does not intersect the object")
    shared_object_polygon = _clip_polygon(contract["object"]["polygon_xy"], [float(v) for v in shared_rect])
    if len(shared_object_polygon) < 3 or _polygon_area(shared_object_polygon) <= 1e-6:
        raise GeometryTileError("the declared object silhouette does not cross the shared tile overlap")

    definitions = [
        {
            "tile_id": "tile_left",
            "side": "left",
            "crop_xyxy": [0, 0, overlap_right, height],
            "core_xyxy_global": [0, 0, split_x, height],
        },
        {
            "tile_id": "tile_right",
            "side": "right",
            "crop_xyxy": [overlap_left, 0, width, height],
            "core_xyxy_global": [split_x, 0, width, height],
        },
    ]

    tile_records = []
    for item in definitions:
        crop = item["crop_xyxy"]
        x0, y0, x1, y1 = crop
        core = item["core_xyxy_global"]
        crop_image = image.crop((x0, y0, x1, y1))
        filename = item["tile_id"] + ".png"
        crop_path = out / filename
        crop_image.save(crop_path, format="PNG")
        local_core = [core[0] - x0, core[1] - y0, core[2] - x0, core[3] - y0]
        local_geometry = _local_object_geometry(contract, crop)
        prompt = (
            "High-resolution tile refinement. Treat the supplied crop as the source of truth. "
            "Preserve the visible part of object '" + contract["object"]["id"] + "' at its "
            "declared tile-local silhouette and landmark coordinates. Add surface detail only; "
            "do not move, resize, rotate, reshape, duplicate, or reinterpret the object. "
            "Do not invent geometry outside the visible crop. This text is a conditioning hint, "
            "not a hard geometric constraint; the separate geometry audit decides pass or fail."
        )
        task = {
            "schema_version": "ige-comfyui-geometry-tile-task/0.1",
            "status": "planned_not_generated",
            "backend": "comfyui",
            "input_image": filename,
            "input_image_sha256": _sha256(crop_path),
            "prompt": prompt,
            "global_canvas": {"width": width, "height": height},
            "tile": {
                **item,
                "size": {"width": x1 - x0, "height": y1 - y0},
                "origin_xy": [x0, y0],
                "core_xyxy_local": local_core,
                "object_geometry_local": local_geometry,
                "coordinate_map": {
                    "global_to_local": "x_local=x_global-crop_x0; y_local=y_global-crop_y0",
                    "local_to_global": "x_global=x_local+crop_x0; y_global=y_local+crop_y0",
                },
            },
            "generation_constraints": {
                "global_geometry_is_authoritative": True,
                "tile_size_may_not_rescale_object": True,
                "write_only_core_region": True,
                "overlap_is_context_and_reconciliation_region": True,
                "hard_constraint_enforced_by_diffusion": False,
            },
        }
        task_path = out / (item["tile_id"] + ".task.json")
        task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tile_records.append({
            "tile_id": item["tile_id"],
            "crop_xyxy": crop,
            "core_xyxy_global": core,
            "core_xyxy_local": local_core,
            "origin_xy": [x0, y0],
            "size": {"width": x1 - x0, "height": y1 - y0},
            "image_path": filename,
            "image_sha256": task["input_image_sha256"],
            "task_path": task_path.name,
            "object_geometry_local": local_geometry,
        })

    plan = {
        "schema_version": "ige-geometry-tile-plan/0.1",
        "status": "planned_not_generated",
        "source": {
            "path": str(source_path.resolve()),
            "sha256": source_sha,
            "width": width,
            "height": height,
        },
        "geometry_contract": contract,
        "tiling": {
            "strategy": "two_vertical_tiles_with_overlap_and_disjoint_cores",
            "split_x": split_x,
            "requested_overlap_px": overlap_px,
            "actual_overlap_xyxy": shared_rect,
            "core_coverage": "exact_non_overlapping_full_canvas",
        },
        "generator": {
            "backend": "comfyui",
            "state": "handoff_packets_only",
            "workflow_api_json": "not_bound",
            "note": "Open each task image in the existing high-resolution img2img workflow; the task prompt is a hint, not a geometry guarantee.",
        },
        "tiles": tile_records,
        "acceptance": {
            "status": "not_run",
            "requires_generated_tile_observations": True,
            "tolerances": contract["tolerances"],
        },
    }
    plan_path = out / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan




def stitch_two_tile_cores(
    plan_path: str | Path,
    left_generated_path: str | Path,
    right_generated_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Reconstruct a candidate from the two disjoint generated write cores.

    The two generated images must retain their exact planned crop dimensions.
    No resizing, registration, feathering or hidden overlap averaging occurs.
    """
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    if plan.get("schema_version") != "ige-geometry-tile-plan/0.1":
        raise GeometryTileError("unsupported geometry tile plan schema")
    tiles = plan.get("tiles")
    if not isinstance(tiles, list) or len(tiles) != 2:
        raise GeometryTileError("two-tile stitch requires exactly two planned tiles")
    output = Path(output_path)
    report_path = Path(str(output) + ".audit.json")
    if output.exists() or report_path.exists():
        raise FileExistsError("stitch output or its audit sidecar already exists")
    output.parent.mkdir(parents=True, exist_ok=True)

    generated_paths = [Path(left_generated_path), Path(right_generated_path)]
    opened_images = []
    try:
        for tile, generated_path in zip(tiles, generated_paths):
            if not generated_path.is_file():
                raise FileNotFoundError(generated_path)
            with Image.open(generated_path) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
            expected_size = (tile["size"]["width"], tile["size"]["height"])
            if image.size != expected_size:
                raise GeometryTileError(
                    f'{tile["tile_id"]} generated dimensions {image.size} '
                    f"do not match planned crop {expected_size}; no implicit resize is allowed"
                )
            opened_images.append(image)

        canvas_width = int(plan["source"]["width"])
        canvas_height = int(plan["source"]["height"])
        canvas = Image.new("RGB", (canvas_width, canvas_height))
        occupied_area = 0
        cores = []
        for tile, generated in zip(tiles, opened_images):
            gx0, gy0, gx1, gy1 = tile["core_xyxy_global"]
            lx0, ly0, lx1, ly1 = tile["core_xyxy_local"]
            if not (0 <= gx0 < gx1 <= canvas_width and 0 <= gy0 < gy1 <= canvas_height):
                raise GeometryTileError("global write core lies outside the planned canvas")
            if not (0 <= lx0 < lx1 <= generated.width and 0 <= ly0 < ly1 <= generated.height):
                raise GeometryTileError("local write core lies outside its generated tile")
            if (gx1 - gx0, gy1 - gy0) != (lx1 - lx0, ly1 - ly0):
                raise GeometryTileError("global and local write-core dimensions do not match")
            cores.append([gx0, gy0, gx1, gy1])
            occupied_area += (gx1 - gx0) * (gy1 - gy0)
            canvas.paste(generated.crop((lx0, ly0, lx1, ly1)), (gx0, gy0))

        a, b = cores
        overlap_w = min(a[2], b[2]) - max(a[0], b[0])
        overlap_h = min(a[3], b[3]) - max(a[1], b[1])
        if overlap_w > 0 and overlap_h > 0:
            raise GeometryTileError("write cores overlap; output ownership is ambiguous")
        if occupied_area != canvas_width * canvas_height:
            raise GeometryTileError("write cores do not cover the full canvas exactly")

        canvas.save(output, format="PNG")
        report = {
            "schema_version": "ige-geometry-tile-stitch/0.1",
            "status": "COMPOSITE_CANDIDATE_NOT_GEOMETRY_ACCEPTED",
            "output_path": str(output.resolve()),
            "output_sha256": _sha256(output),
            "source_sha256": plan["source"]["sha256"],
            "generated_tile_sha256": {
                tiles[0]["tile_id"]: _sha256(generated_paths[0]),
                tiles[1]["tile_id"]: _sha256(generated_paths[1]),
            },
            "write_cores_global": cores,
            "ownership": "disjoint_core_copy_no_blend_no_resize_no_warp",
            "geometry_audit": "not_run",
            "final_acceptance": False,
            "limitations": [
                "Only disjoint tile cores were copied; the shared context overlap was not averaged.",
                "This is a composite candidate, not proof of geometry, identity, perceptual quality or seam acceptance.",
                "Generated-image dimensions must exactly match planned crop dimensions.",
            ],
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    finally:
        opened_images.clear()


def audit_tile_observations(
    plan_path: str | Path,
    observations_path: str | Path,
) -> dict[str, Any]:
    """Compare externally measured generated geometry with each tile's locked geometry.

    Observations are pixel measurements (e.g. manually marked or segmentation
    proposals reviewed by a human), not values inferred from prompt compliance.
    """
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    observations_doc = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    if plan.get("schema_version") != "ige-geometry-tile-plan/0.1":
        raise GeometryTileError("unsupported geometry tile plan schema")
    observations = observations_doc.get("observations") if isinstance(observations_doc, dict) else None
    if not isinstance(observations, list):
        raise GeometryTileError("observations.json must contain an observations array")
    by_id = {}
    for item in observations:
        if not isinstance(item, dict) or not isinstance(item.get("tile_id"), str):
            raise GeometryTileError("each observation requires tile_id")
        if item["tile_id"] in by_id:
            raise GeometryTileError("duplicate tile observation: " + item["tile_id"])
        by_id[item["tile_id"]] = item

    tolerance = plan["acceptance"]["tolerances"]
    tile_reports = []
    measured_global_polygons: dict[str, list[list[float]]] = {}
    measured_global_landmarks: dict[str, dict[str, list[float]]] = {}
    expected_landmarks_global = plan["geometry_contract"]["object"]["landmarks"]

    for tile in plan["tiles"]:
        tile_id = tile["tile_id"]
        obs = by_id.get(tile_id)
        if obs is None:
            tile_reports.append({"tile_id": tile_id, "status": "incomplete", "reason": "missing_observation"})
            continue
        expected = tile["object_geometry_local"]
        width = tile["size"]["width"]
        height = tile["size"]["height"]
        observed_bbox = _rect(obs.get("bbox_xyxy"), tile_id + ".bbox_xyxy")
        observed_polygon_raw = obs.get("polygon_xy")
        if not isinstance(observed_polygon_raw, list) or len(observed_polygon_raw) < 3:
            raise GeometryTileError(tile_id + ".polygon_xy requires at least three points")
        observed_polygon = [
            [_finite_number(p[0], "observed polygon x"), _finite_number(p[1], "observed polygon y")]
            for p in observed_polygon_raw
            if isinstance(p, (list, tuple)) and len(p) == 2
        ]
        if len(observed_polygon) < 3:
            raise GeometryTileError(tile_id + ".polygon_xy is invalid")
        expected_bbox = expected["bbox_xyxy"]
        if observed_bbox[0] < 0 or observed_bbox[1] < 0 or observed_bbox[2] > width or observed_bbox[3] > height:
            raise GeometryTileError(tile_id + ".bbox_xyxy must lie inside the tile crop")
        if any(p[0] < 0 or p[1] < 0 or p[0] > width or p[1] > height for p in observed_polygon):
            raise GeometryTileError(tile_id + ".polygon_xy must lie inside the tile crop")
        bbox_iou = _iou(expected_bbox, observed_bbox)
        silhouette_iou = _polygon_iou(expected["polygon_xy"], observed_polygon, width, height)

        obs_landmarks = obs.get("landmarks", {})
        if not isinstance(obs_landmarks, dict):
            raise GeometryTileError(tile_id + ".landmarks must be an object")
        origin_x, origin_y = tile["origin_xy"]
        global_polygon = [[p[0] + origin_x, p[1] + origin_y] for p in observed_polygon]
        measured_global_polygons[tile_id] = global_polygon
        global_landmarks = {
            name: [float(point[0]) + origin_x, float(point[1]) + origin_y]
            for name, point in obs_landmarks.items()
            if isinstance(point, (list, tuple)) and len(point) == 2
        }
        measured_global_landmarks[tile_id] = global_landmarks

        expected_local_landmarks = expected["landmarks"]
        missing_landmarks = sorted(set(expected_local_landmarks) - set(obs_landmarks))
        landmark_errors = {
            name: math.dist(expected_local_landmarks[name], obs_landmarks[name])
            for name in expected_local_landmarks
            if name in obs_landmarks
        }
        landmark_max = max(landmark_errors.values()) if landmark_errors else 0.0
        within = (
            bbox_iou >= tolerance["bbox_iou_min"]
            and silhouette_iou >= tolerance["silhouette_iou_min"]
            and not missing_landmarks
            and landmark_max <= tolerance["landmark_max_px"]
        )
        tile_reports.append({
            "tile_id": tile_id,
            "status": "within_declared_tolerance" if within else "outside_declared_tolerance",
            "bbox_iou": bbox_iou,
            "silhouette_iou": silhouette_iou,
            "landmark_max_error_px": landmark_max if landmark_errors else None,
            "landmark_errors_px": landmark_errors,
            "missing_landmarks": missing_landmarks,
        })

    if len(tile_reports) != len(plan["tiles"]) or any(x["status"] != "within_declared_tolerance" for x in tile_reports):
        return {
            "schema_version": "ige-geometry-tile-audit/0.1",
            "status": "FAIL_OR_INCOMPLETE",
            "tile_reports": tile_reports,
            "overlap_report": {"status": "not_evaluated"},
            "limitations": [
                "This audit compares annotated geometry; it does not prove perceptual quality or model fidelity.",
                "Declared tolerances are experiment parameters and are not globally validated thresholds.",
            ],
        }

    left, right = plan["tiles"]
    left_crop, right_crop = left["crop_xyxy"], right["crop_xyxy"]
    overlap = [
        max(left_crop[0], right_crop[0]),
        max(left_crop[1], right_crop[1]),
        min(left_crop[2], right_crop[2]),
        min(left_crop[3], right_crop[3]),
    ]
    overlap_w, overlap_h = overlap[2] - overlap[0], overlap[3] - overlap[1]
    left_overlap_poly = _clip_polygon(
        [[p[0], p[1]] for p in measured_global_polygons[left["tile_id"]]],
        [float(v) for v in overlap],
    )
    right_overlap_poly = _clip_polygon(
        [[p[0], p[1]] for p in measured_global_polygons[right["tile_id"]]],
        [float(v) for v in overlap],
    )
    left_local = _translate_polygon(left_overlap_poly, overlap[0], overlap[1])
    right_local = _translate_polygon(right_overlap_poly, overlap[0], overlap[1])
    overlap_iou = _polygon_iou(left_local, right_local, overlap_w, overlap_h)

    shared_errors = {}
    left_lm = measured_global_landmarks[left["tile_id"]]
    right_lm = measured_global_landmarks[right["tile_id"]]
    for name in sorted(set(left_lm) & set(right_lm) & set(expected_landmarks_global)):
        point = expected_landmarks_global[name]
        if overlap[0] <= point[0] <= overlap[2] and overlap[1] <= point[1] <= overlap[3]:
            shared_errors[name] = math.dist(left_lm[name], right_lm[name])
    shared_max = max(shared_errors.values()) if shared_errors else 0.0
    overlap_ok = (
        overlap_iou >= tolerance["overlap_silhouette_iou_min"]
        and shared_max <= tolerance["overlap_landmark_max_px"]
    )
    return {
        "schema_version": "ige-geometry-tile-audit/0.1",
        "status": "PASS_WITHIN_DECLARED_TOLERANCES" if overlap_ok else "FAIL_OVERLAP_INCONSISTENCY",
        "tile_reports": tile_reports,
        "overlap_report": {
            "overlap_xyxy_global": overlap,
            "silhouette_iou": overlap_iou,
            "shared_landmark_errors_px": shared_errors,
            "shared_landmark_max_error_px": shared_max if shared_errors else None,
            "status": "within_declared_tolerance" if overlap_ok else "outside_declared_tolerance",
        },
        "limitations": [
            "This audit compares annotated geometry; it does not prove perceptual quality or model fidelity.",
            "Declared tolerances are experiment parameters and are not globally validated thresholds.",
            "A pass requires geometry measurements from both generated tiles; prompt adherence alone is never accepted.",
        ],
    }
