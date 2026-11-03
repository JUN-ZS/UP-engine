from __future__ import annotations

import itertools
import math
from typing import Any

import numpy as np

from .multiview import MultiViewRegistrationError


def _as_rgb_u8(image: Any) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise MultiViewRegistrationError("feature matcher expects HxWxRGB(A) images")
    array = array[:, :, :3]
    if not np.isfinite(array).all():
        raise MultiViewRegistrationError("feature matcher image contains NaN or infinite values")
    if np.issubdtype(array.dtype, np.floating):
        maximum = float(np.nanmax(array)) if array.size else 0.0
        if maximum <= 1.0:
            array = array * 255.0
    return np.clip(array, 0, 255).astype(np.uint8)


def build_sift_match_graph(
    images: dict[str, Any],
    *,
    max_features: int = 5000,
    ratio_threshold: float = 0.72,
    ransac_reprojection_px: float = 3.0,
    min_inliers: int = 8,
    max_anchors_per_edge: int = 800,
    matcher_backend: str = "flann",
) -> dict[str, Any]:
    """Generate candidate pairwise correspondences using mutual SIFT + RANSAC.

    SIFT/RANSAC only proposes coordinates. The DDXX weighted Umeyama/Huber
    engine performs the subsequent similarity fit and graph optimisation.
    """
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("SIFT matching requires: python -m pip install -e '.[registration]'") from exc
    if not hasattr(cv2, "SIFT_create"):
        raise RuntimeError("the installed OpenCV build does not expose SIFT_create")
    if len(images) < 2:
        raise MultiViewRegistrationError("at least two input images are required")
    if (
        max_features < 100
        or not (0.1 <= ratio_threshold < 1.0)
        or ransac_reprojection_px <= 0
        or min_inliers < 3
        or max_anchors_per_edge < min_inliers
    ):
        raise MultiViewRegistrationError("invalid SIFT/RANSAC settings")
    if matcher_backend not in {"flann", "brute_force"}:
        raise MultiViewRegistrationError("matcher_backend must be 'flann' or 'brute_force'")

    prepared: dict[str, dict[str, Any]] = {}
    for image_id, raw in images.items():
        rgb = _as_rgb_u8(raw)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        keypoints, descriptors = cv2.SIFT_create(nfeatures=int(max_features)).detectAndCompute(gray, None)
        prepared[image_id] = {"rgb": rgb, "keypoints": keypoints or [], "descriptors": descriptors}

    matcher = (
        cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=64))
        if matcher_backend == "flann"
        else cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    )
    edges: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for image_a, image_b in itertools.combinations(images.keys(), 2):
        a, b = prepared[image_a], prepared[image_b]
        da, db = a["descriptors"], b["descriptors"]
        summary = {
            "image_a": image_a, "image_b": image_b,
            "keypoints_a": len(a["keypoints"]), "keypoints_b": len(b["keypoints"]),
        }
        if da is None or db is None or len(da) < 2 or len(db) < 2:
            diagnostics.append(summary | {"status": "rejected_no_descriptors", "mutual_matches": 0, "inliers": 0})
            continue

        forward, reverse = matcher.knnMatch(db, da, k=2), matcher.knnMatch(da, db, k=2)
        best_b_to_a: dict[int, tuple[int, float]] = {}
        best_a_to_b: dict[int, int] = {}
        for pair in forward:
            if len(pair) >= 2 and pair[0].distance < ratio_threshold * pair[1].distance:
                best_b_to_a[pair[0].queryIdx] = (pair[0].trainIdx, float(pair[0].distance))
        for pair in reverse:
            if len(pair) >= 2 and pair[0].distance < ratio_threshold * pair[1].distance:
                best_a_to_b[pair[0].queryIdx] = pair[0].trainIdx
        mutual = [
            (idx_b, idx_a, distance)
            for idx_b, (idx_a, distance) in best_b_to_a.items()
            if best_a_to_b.get(idx_a) == idx_b
        ]
        summary["mutual_matches"] = len(mutual)
        if len(mutual) < min_inliers:
            diagnostics.append(summary | {"status": "rejected_too_few_mutual_matches", "inliers": 0})
            continue

        points_b = np.float32([b["keypoints"][idx_b].pt for idx_b, _, _ in mutual])
        points_a = np.float32([a["keypoints"][idx_a].pt for _, idx_a, _ in mutual])
        _, inlier_mask = cv2.estimateAffinePartial2D(
            points_b, points_a, method=cv2.RANSAC,
            ransacReprojThreshold=float(ransac_reprojection_px),
            maxIters=3000, confidence=0.995, refineIters=20,
        )
        if inlier_mask is None:
            diagnostics.append(summary | {"status": "rejected_ransac_failed", "inliers": 0})
            continue
        inlier_indices = np.flatnonzero(inlier_mask.reshape(-1) > 0)
        summary["ransac_inliers"] = int(len(inlier_indices))
        summary["inlier_ratio"] = float(len(inlier_indices) / max(len(mutual), 1))
        if len(inlier_indices) < min_inliers:
            diagnostics.append(summary | {"status": "rejected_too_few_ransac_inliers"})
            continue

        # Rank descriptors, but stop the strongest points collapsing into one
        # tiny texture patch in either image.
        ranked = sorted(inlier_indices.tolist(), key=lambda i: (mutual[i][2], i))
        rows = cols = 8
        cell_cap = max(2, int(math.ceil(max_anchors_per_edge / (rows * cols))))
        occupancy_a: dict[tuple[int, int], int] = {}
        occupancy_b: dict[tuple[int, int], int] = {}
        selected: list[int] = []
        ha, wa = a["rgb"].shape[:2]
        hb, wb = b["rgb"].shape[:2]
        for match_index in ranked:
            idx_b, idx_a, _ = mutual[match_index]
            xa, ya = a["keypoints"][idx_a].pt
            xb, yb = b["keypoints"][idx_b].pt
            cell_a = (min(rows-1, int(ya/max(ha,1)*rows)), min(cols-1, int(xa/max(wa,1)*cols)))
            cell_b = (min(rows-1, int(yb/max(hb,1)*rows)), min(cols-1, int(xb/max(wb,1)*cols)))
            if occupancy_a.get(cell_a, 0) >= cell_cap or occupancy_b.get(cell_b, 0) >= cell_cap:
                continue
            selected.append(match_index)
            occupancy_a[cell_a] = occupancy_a.get(cell_a, 0) + 1
            occupancy_b[cell_b] = occupancy_b.get(cell_b, 0) + 1
            if len(selected) >= max_anchors_per_edge:
                break
        if len(selected) < min_inliers:
            selected = ranked[:max_anchors_per_edge]

        anchors = []
        for anchor_index, match_index in enumerate(selected):
            idx_b, idx_a, distance = mutual[match_index]
            anchors.append({
                "name": f"sift_{anchor_index:04d}",
                "xy_a": [float(x) for x in a["keypoints"][idx_a].pt],
                "xy_b": [float(x) for x in b["keypoints"][idx_b].pt],
                "weight": 1.0, "confidence": 1.0,
                "descriptor_distance": float(distance),
            })
        edge_id = f"{image_a}__{image_b}"
        edges.append({"edge_id": edge_id, "image_a": image_a, "image_b": image_b, "anchors": anchors})
        summary["status"] = "candidate_edge"
        summary["retained_anchors"] = len(anchors)
        summary["edge_id"] = edge_id
        selected_a = np.asarray([x["xy_a"] for x in anchors], dtype=np.float64)
        selected_b = np.asarray([x["xy_b"] for x in anchors], dtype=np.float64)
        summary["anchor_spread"] = {
            "image_a_bbox_fraction": float(np.prod(np.maximum(np.ptp(selected_a, axis=0), 0.0)) / max(wa*ha, 1)),
            "image_b_bbox_fraction": float(np.prod(np.maximum(np.ptp(selected_b, axis=0), 0.0)) / max(wb*hb, 1)),
            "image_a_span_fraction_xy": [float(v) for v in (np.ptp(selected_a, axis=0)/np.array([wa,ha]))],
            "image_b_span_fraction_xy": [float(v) for v in (np.ptp(selected_b, axis=0)/np.array([wb,hb]))],
        }
        diagnostics.append(summary)

    specs = [
        {"id": image_id, "width": int(prepared[image_id]["rgb"].shape[1]),
         "height": int(prepared[image_id]["rgb"].shape[0])}
        for image_id in images
    ]
    return {
        "schema_version": "siaux-multiview-anchors/1.0",
        "correspondence_provider": "SIFT_MUTUAL_RATIO_RANSAC_CANDIDATE",
        "matcher_backend": matcher_backend, "images": specs, "matches": edges,
        "pair_diagnostics": diagnostics,
        "limitations": [
            "SIFT matches are candidate correspondences, not semantic proof.",
            "Repeated texture, similar objects and parallax can create coherent but incorrect matches.",
            "Pairwise RANSAC inliers are refit by DDXX weighted similarity; they do not prove that similarity is the correct scene model.",
        ],
    }
