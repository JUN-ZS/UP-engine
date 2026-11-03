from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import math
from typing import Any, Iterable

import numpy as np


class MultiViewRegistrationError(ValueError):
    """The multi-image registration graph is invalid or cannot be solved."""


@dataclass(frozen=True)
class SimilarityTransform:
    """Column-vector similarity transform: output = scale * R(theta) @ input + t."""

    scale: float
    rotation_rad: float
    tx: float
    ty: float

    def apply(self, points: np.ndarray) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64)
        c, s = math.cos(self.rotation_rad), math.sin(self.rotation_rad)
        rot = np.array([[c, -s], [s, c]], dtype=np.float64)
        return self.scale * (pts @ rot.T) + np.array([self.tx, self.ty])

    def inverse(self) -> "SimilarityTransform":
        inv_scale = 1.0 / self.scale
        inv_angle = -self.rotation_rad
        c, s = math.cos(inv_angle), math.sin(inv_angle)
        inv_rot = np.array([[c, -s], [s, c]], dtype=np.float64)
        inv_t = -inv_scale * (inv_rot @ np.array([self.tx, self.ty], dtype=np.float64))
        return SimilarityTransform(inv_scale, inv_angle, float(inv_t[0]), float(inv_t[1]))

    def compose(self, inner: "SimilarityTransform") -> "SimilarityTransform":
        """Return self(inner(x)); both transforms use column-vector convention."""
        c, s = math.cos(self.rotation_rad), math.sin(self.rotation_rad)
        rot = np.array([[c, -s], [s, c]], dtype=np.float64)
        translated = self.scale * (rot @ np.array([inner.tx, inner.ty])) + np.array([self.tx, self.ty])
        return SimilarityTransform(
            self.scale * inner.scale,
            self.rotation_rad + inner.rotation_rad,
            float(translated[0]),
            float(translated[1]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "similarity_2d",
            "convention": "column_vector_ccw_degrees",
            "scale": float(self.scale),
            "rotation_degrees": float(math.degrees(self.rotation_rad)),
            "translation_px": [float(self.tx), float(self.ty)],
        }

    @classmethod
    def from_params(cls, values: Iterable[float]) -> "SimilarityTransform":
        tx, ty, log_scale, angle = (float(x) for x in values)
        return cls(math.exp(log_scale), angle, tx, ty)

    def to_params(self) -> np.ndarray:
        return np.array([self.tx, self.ty, math.log(self.scale), self.rotation_rad], dtype=np.float64)


@dataclass(frozen=True)
class SimilarityFit:
    transform: SimilarityTransform
    residuals_px: np.ndarray
    base_weights: np.ndarray
    robust_weights: np.ndarray
    weighted_rmse_px: float
    robust_weighted_rmse_px: float
    median_residual_px: float
    p95_residual_px: float
    max_residual_px: float
    iterations: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "transform": self.transform.to_dict(),
            "weighted_rmse_px": self.weighted_rmse_px,
            "robust_weighted_rmse_px": self.robust_weighted_rmse_px,
            "median_residual_px": self.median_residual_px,
            "p95_residual_px": self.p95_residual_px,
            "max_residual_px": self.max_residual_px,
            "iterations": self.iterations,
            "anchors": [
                {
                    "residual_px": float(r),
                    "base_weight": float(w),
                    "robust_weight": float(rw),
                }
                for r, w, rw in zip(self.residuals_px, self.base_weights, self.robust_weights)
            ],
        }


def _rotation(angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c, -s], [s, c]], dtype=np.float64)


def _find_bridge_edge_indices(image_ids: list[str], edges: list[dict[str, Any]]) -> set[int]:
    """Return pair-edge indices whose relative placement has no independent cycle check."""
    adjacency: dict[str, list[tuple[str, int]]] = {image_id: [] for image_id in image_ids}
    for edge_index, edge in enumerate(edges):
        a, b = edge["image_a"], edge["image_b"]
        adjacency[a].append((b, edge_index))
        adjacency[b].append((a, edge_index))
    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    bridges: set[int] = set()
    clock = 0

    def visit(node: str, parent_edge: int | None) -> None:
        nonlocal clock
        clock += 1
        discovery[node] = low[node] = clock
        for neighbour, edge_index in adjacency[node]:
            if edge_index == parent_edge:
                continue
            if neighbour not in discovery:
                visit(neighbour, edge_index)
                low[node] = min(low[node], low[neighbour])
                if low[neighbour] > discovery[node]:
                    bridges.add(edge_index)
            else:
                low[node] = min(low[node], discovery[neighbour])

    for image_id in image_ids:
        if image_id not in discovery:
            visit(image_id, None)
    return bridges


def _validate_points(source: np.ndarray, target: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if source.ndim != 2 or target.ndim != 2 or source.shape != target.shape or source.shape[1] != 2:
        raise MultiViewRegistrationError("source_points and target_points must have the same Nx2 shape")
    if weights.shape != (len(source),):
        raise MultiViewRegistrationError("weights must contain one value per anchor")
    if len(source) < 3:
        raise MultiViewRegistrationError("at least 3 paired anchors are required for a validated 2D similarity fit")
    if not np.isfinite(source).all() or not np.isfinite(target).all() or not np.isfinite(weights).all():
        raise MultiViewRegistrationError("anchors and weights must be finite")
    if np.any(weights <= 0):
        raise MultiViewRegistrationError("all anchor weights must be positive")
    return source, target, weights


def _fit_umeyama(source: np.ndarray, target: np.ndarray, weights: np.ndarray) -> SimilarityTransform:
    weight_sum = float(np.sum(weights))
    if not math.isfinite(weight_sum) or weight_sum <= 0:
        raise MultiViewRegistrationError("anchor weight sum must be positive")
    wn = weights / weight_sum
    mean_source = np.sum(source * wn[:, None], axis=0)
    mean_target = np.sum(target * wn[:, None], axis=0)
    xs = source - mean_source
    yt = target - mean_target
    source_spread = np.linalg.svd(xs * np.sqrt(wn[:, None]), compute_uv=False)
    target_spread = np.linalg.svd(yt * np.sqrt(wn[:, None]), compute_uv=False)
    if len(source_spread) < 2 or source_spread[0] <= 1e-10 or source_spread[1] <= source_spread[0] * 1e-5:
        raise MultiViewRegistrationError("source anchors are collinear or spatially degenerate")
    if len(target_spread) < 2 or target_spread[0] <= 1e-10 or target_spread[1] <= target_spread[0] * 1e-5:
        raise MultiViewRegistrationError("target anchors are collinear or spatially degenerate")
    covariance = (yt * wn[:, None]).T @ xs
    u, singular, vt = np.linalg.svd(covariance)
    sign = 1.0 if np.linalg.det(u @ vt) >= 0 else -1.0
    correction = np.diag([1.0, sign])
    rot = u @ correction @ vt
    variance = float(np.sum(wn * np.sum(xs * xs, axis=1)))
    if variance <= 1e-12:
        raise MultiViewRegistrationError("source anchor variance is too small")
    scale = float(np.sum(singular * np.diag(correction)) / variance)
    if not math.isfinite(scale) or scale <= 1e-8:
        raise MultiViewRegistrationError("estimated similarity scale is invalid")
    translation = mean_target - scale * (rot @ mean_source)
    angle = math.atan2(float(rot[1, 0]), float(rot[0, 0]))
    return SimilarityTransform(scale, angle, float(translation[0]), float(translation[1]))


def fit_weighted_similarity(
    source_points: np.ndarray,
    target_points: np.ndarray,
    weights: np.ndarray | None = None,
    *,
    huber_px: float = 10.0,
    max_iterations: int = 25,
) -> SimilarityFit:
    """DDXX-derived weighted Umeyama + Huber IRLS for one image pair."""
    source = np.asarray(source_points, dtype=np.float64)
    target = np.asarray(target_points, dtype=np.float64)
    base = np.ones(len(source), dtype=np.float64) if weights is None else np.asarray(weights, dtype=np.float64)
    source, target, base = _validate_points(source, target, base)
    if not math.isfinite(huber_px) or huber_px <= 0:
        raise MultiViewRegistrationError("huber_px must be positive")
    if max_iterations < 1:
        raise MultiViewRegistrationError("max_iterations must be >= 1")
    robust = base.copy()
    transform = _fit_umeyama(source, target, robust)
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        residuals = np.linalg.norm(transform.apply(source) - target, axis=1)
        factors = np.ones_like(residuals)
        outliers = residuals > huber_px
        factors[outliers] = huber_px / np.maximum(residuals[outliers], 1e-12)
        next_robust = base * factors
        updated = _fit_umeyama(source, target, next_robust)
        delta = max(abs(updated.scale - transform.scale), abs(updated.rotation_rad - transform.rotation_rad),
                    abs(updated.tx - transform.tx), abs(updated.ty - transform.ty))
        transform, robust = updated, next_robust
        if delta < 1e-10:
            break
    residuals = np.linalg.norm(transform.apply(source) - target, axis=1)
    weighted_rmse = math.sqrt(float(np.sum(base * residuals**2) / np.sum(base)))
    robust_rmse = math.sqrt(float(np.sum(robust * residuals**2) / np.sum(robust)))
    return SimilarityFit(
        transform, residuals, base, robust, weighted_rmse, robust_rmse,
        float(np.median(residuals)), float(np.percentile(residuals, 95)),
        float(np.max(residuals)), iterations,
    )


def _huber_loss(norm: float, delta: float) -> float:
    return norm * norm if norm <= delta else 2.0 * delta * norm - delta * delta


def _pose_point_jacobian(transform: SimilarityTransform, point: np.ndarray) -> np.ndarray:
    q = transform.scale * (_rotation(transform.rotation_rad) @ point)
    return np.array([[1.0, 0.0, q[0], -q[1]], [0.0, 1.0, q[1], q[0]]], dtype=np.float64)


def register_multiview(
    image_specs: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    *,
    root_image_id: str | None = None,
    huber_px: float = 10.0,
    acceptance_threshold_px: float | None = None,
    max_iterations: int = 60,
    max_canvas_pixels: int = 100_000_000,
    allow_unverified_bridge_edges: bool = False,
) -> dict[str, Any]:
    """Solve a global multi-image similarity pose graph from paired 2D anchors."""
    if not isinstance(image_specs, list) or len(image_specs) < 2:
        raise MultiViewRegistrationError("at least two image_specs are required")
    ids: list[str] = []
    dimensions: dict[str, tuple[int, int]] = {}
    for item in image_specs:
        if not isinstance(item, dict):
            raise MultiViewRegistrationError("each image specification must be an object")
        image_id, width, height = item.get("id"), item.get("width"), item.get("height")
        if not isinstance(image_id, str) or not image_id.strip() or image_id in dimensions:
            raise MultiViewRegistrationError("image IDs must be unique non-empty strings")
        if isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, int) or not isinstance(height, int) or width < 1 or height < 1:
            raise MultiViewRegistrationError(f"invalid dimensions for image {image_id}")
        ids.append(image_id)
        dimensions[image_id] = (width, height)
    root = root_image_id or ids[0]
    if root not in dimensions:
        raise MultiViewRegistrationError(f"root_image_id is not present: {root}")
    if not matches:
        raise MultiViewRegistrationError("at least one pairwise match edge is required")
    if acceptance_threshold_px is not None and (not math.isfinite(acceptance_threshold_px) or acceptance_threshold_px <= 0):
        raise MultiViewRegistrationError("acceptance_threshold_px must be positive or None")
    if not isinstance(max_canvas_pixels, int) or isinstance(max_canvas_pixels, bool) or max_canvas_pixels < 1:
        raise MultiViewRegistrationError("max_canvas_pixels must be a positive integer")
    if max_iterations < 1 or not math.isfinite(huber_px) or huber_px <= 0:
        raise MultiViewRegistrationError("optimizer settings are invalid")

    edges: list[dict[str, Any]] = []
    adjacency: dict[str, list[tuple[str, SimilarityTransform]]] = {image_id: [] for image_id in ids}
    for edge_index, edge in enumerate(matches):
        a, b = edge.get("image_a"), edge.get("image_b")
        if a not in dimensions or b not in dimensions or a == b:
            raise MultiViewRegistrationError(f"edge {edge_index} has invalid image endpoints")
        anchors = edge.get("anchors")
        if not isinstance(anchors, list) or len(anchors) < 3:
            raise MultiViewRegistrationError(f"edge {edge_index} needs at least 3 paired anchors")
        pa, pb, weights, names = [], [], [], []
        for anchor_index, anchor in enumerate(anchors):
            if not isinstance(anchor, dict):
                raise MultiViewRegistrationError(f"edge {edge_index} anchor {anchor_index} is invalid")
            try:
                xa = np.asarray(anchor["xy_a"], dtype=np.float64)
                xb = np.asarray(anchor["xy_b"], dtype=np.float64)
                weight = float(anchor.get("weight", 1.0)) * float(anchor.get("confidence", 1.0))
            except (KeyError, TypeError, ValueError) as exc:
                raise MultiViewRegistrationError(f"edge {edge_index} anchor {anchor_index} lacks valid coordinates") from exc
            if xa.shape != (2,) or xb.shape != (2,) or not np.isfinite(xa).all() or not np.isfinite(xb).all():
                raise MultiViewRegistrationError(f"edge {edge_index} anchor {anchor_index} coordinates must be finite 2-vectors")
            if weight <= 0 or not math.isfinite(weight):
                raise MultiViewRegistrationError(f"edge {edge_index} anchor {anchor_index} weight must be positive")
            wa, ha = dimensions[a]
            wb, hb = dimensions[b]
            if not (0 <= xa[0] < wa and 0 <= xa[1] < ha and 0 <= xb[0] < wb and 0 <= xb[1] < hb):
                raise MultiViewRegistrationError(f"edge {edge_index} anchor {anchor_index} lies outside its image bounds")
            pa.append(xa); pb.append(xb); weights.append(weight); names.append(str(anchor.get("name", f"anchor_{anchor_index}")))
        fit = fit_weighted_similarity(np.asarray(pb), np.asarray(pa), np.asarray(weights), huber_px=huber_px)
        adjacency[a].append((b, fit.transform))
        adjacency[b].append((a, fit.transform.inverse()))
        edges.append({
            "edge_id": str(edge.get("edge_id", f"edge_{edge_index}")), "image_a": a, "image_b": b,
            "xy_a": np.asarray(pa), "xy_b": np.asarray(pb), "weights": np.asarray(weights),
            "names": names, "b_to_a": fit.transform, "pairwise_fit": fit,
        })

    poses: dict[str, SimilarityTransform] = {root: SimilarityTransform(1.0, 0.0, 0.0, 0.0)}
    queue: deque[str] = deque([root])
    while queue:
        current = queue.popleft()
        for neighbour, neighbour_to_current in adjacency[current]:
            if neighbour not in poses:
                poses[neighbour] = poses[current].compose(neighbour_to_current)
                queue.append(neighbour)
    disconnected = sorted(set(ids) - set(poses))
    if disconnected:
        raise MultiViewRegistrationError(f"pairwise match graph is disconnected: {disconnected}")

    bridge_indices = _find_bridge_edge_indices(ids, edges)
    variable_ids = [image_id for image_id in ids if image_id != root]
    variable_index = {image_id: 4 * index for index, image_id in enumerate(variable_ids)}
    params = np.concatenate([poses[x].to_params() for x in variable_ids])

    def unpack(vector: np.ndarray) -> dict[str, SimilarityTransform]:
        result = {root: SimilarityTransform(1.0, 0.0, 0.0, 0.0)}
        for image_id in variable_ids:
            offset = variable_index[image_id]
            result[image_id] = SimilarityTransform.from_params(vector[offset:offset + 4])
        return result

    def residual_jacobian(vector: np.ndarray, jacobian_needed: bool = True):
        current = unpack(vector)
        residuals, jacobians, weights = [], [], []
        for edge in edges:
            a, b = edge["image_a"], edge["image_b"]
            for pa, pb, weight in zip(edge["xy_a"], edge["xy_b"], edge["weights"]):
                qa, qb = current[a].apply(pa[None, :])[0], current[b].apply(pb[None, :])[0]
                residuals.append(qa - qb); weights.append(float(weight))
                if jacobian_needed:
                    row = np.zeros((2, len(vector)), dtype=np.float64)
                    if a != root:
                        off = variable_index[a]; row[:, off:off + 4] += _pose_point_jacobian(current[a], pa)
                    if b != root:
                        off = variable_index[b]; row[:, off:off + 4] -= _pose_point_jacobian(current[b], pb)
                    jacobians.append(row)
        return np.asarray(residuals), np.asarray(weights), (np.vstack(jacobians) if jacobian_needed else None)

    def objective(vector: np.ndarray) -> float:
        residual, weights, _ = residual_jacobian(vector, False)
        norms = np.linalg.norm(residual, axis=1)
        return float(np.sum(weights * np.where(norms <= huber_px, norms**2, 2*huber_px*norms-huber_px**2)))

    damping, loss, iterations = 1e-3, objective(params), 0
    for iterations in range(1, max_iterations + 1):
        residual, weights, jac = residual_jacobian(params)
        norms = np.linalg.norm(residual, axis=1)
        factors = np.ones_like(norms); outliers = norms > huber_px
        factors[outliers] = huber_px / np.maximum(norms[outliers], 1e-12)
        row_weights = np.repeat(weights * factors, 2)
        hessian = jac.T @ (row_weights[:, None] * jac)
        gradient = jac.T @ (row_weights * residual.reshape(-1))
        diagonal = np.maximum(np.diag(hessian), 1.0)
        try:
            delta = np.linalg.solve(hessian + damping*np.diag(diagonal), -gradient)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(hessian + damping*np.diag(diagonal), -gradient, rcond=None)[0]
        if not np.isfinite(delta).all():
            raise MultiViewRegistrationError("pose graph optimizer produced a non-finite update")
        proposal = params + delta
        if any(not (1e-4 < pose.scale < 1e4) for pose in unpack(proposal).values()):
            damping *= 10.0; continue
        new_loss = objective(proposal)
        if new_loss < loss:
            improvement = loss - new_loss
            params, loss = proposal, new_loss
            if improvement < 1e-10 or np.linalg.norm(delta) < 1e-7:
                break
            damping = max(damping*0.5, 1e-9)
        else:
            damping = min(damping*10.0, 1e9)
            if damping >= 1e8:
                break

    poses = unpack(params)
    residual, base_weights, _ = residual_jacobian(params, False)
    norms = np.linalg.norm(residual, axis=1)
    factors = np.ones_like(norms); outliers = norms > huber_px
    factors[outliers] = huber_px / np.maximum(norms[outliers], 1e-12)
    robust_weights = base_weights * factors
    global_stats = {
        "anchor_count": int(len(norms)),
        "weighted_rmse_px": math.sqrt(float(np.sum(base_weights*norms**2)/np.sum(base_weights))),
        "robust_weighted_rmse_px": math.sqrt(float(np.sum(robust_weights*norms**2)/np.sum(robust_weights))),
        "median_residual_px": float(np.median(norms)),
        "p95_residual_px": float(np.percentile(norms, 95)),
        "max_residual_px": float(np.max(norms)),
        "huber_px": float(huber_px),
        "downweighted_anchor_count": int(np.count_nonzero(factors < 0.999999)),
        "optimizer_iterations": int(iterations),
    }

    edge_reports, cycle_closures = [], []
    for i, edge in enumerate(edges):
        a, b = edge["image_a"], edge["image_b"]
        expected = poses[a].inverse().compose(poses[b])
        closure = np.linalg.norm(edge["b_to_a"].apply(edge["xy_b"]) - expected.apply(edge["xy_b"]), axis=1)
        closure_p95 = float(np.percentile(closure, 95))
        if i not in bridge_indices:
            cycle_closures.append(closure_p95)
        edge_reports.append({
            "edge_id": edge["edge_id"], "image_a": a, "image_b": b,
            "direction": "image_b_to_image_a", "independent_cycle_check": i not in bridge_indices,
            "pairwise_fit": edge["pairwise_fit"].to_dict(),
            "global_closure": {"p95_residual_px": closure_p95, "max_residual_px": float(np.max(closure))},
        })
    worst_edge = max((x["global_closure"]["p95_residual_px"] for x in edge_reports), default=0.0)
    worst_cycle_edge = max(cycle_closures, default=0.0)
    global_stats["worst_edge_closure_p95_px"] = worst_edge
    global_stats["worst_cycle_checked_edge_closure_p95_px"] = worst_cycle_edge
    bridge_ids = [edges[i]["edge_id"] for i in sorted(bridge_indices)]
    cycle_rank = max(0, len(edges) - len(ids) + 1)

    if acceptance_threshold_px is None:
        gate = "pending_threshold_not_declared"
    elif global_stats["p95_residual_px"] > acceptance_threshold_px:
        gate = "fail_global_residual_threshold"
    elif worst_cycle_edge > acceptance_threshold_px:
        gate = "fail_edge_closure_threshold"
    elif len(ids) > 2 and bridge_indices and not allow_unverified_bridge_edges:
        gate = "pending_unverified_bridge_edges"
    else:
        gate = "pass"

    corners = []
    for image_id in ids:
        width, height = dimensions[image_id]
        points = np.array([[0,0],[width-1,0],[width-1,height-1],[0,height-1]], dtype=np.float64)
        corners.append(poses[image_id].apply(points))
    all_corners = np.vstack(corners)
    min_xy, max_xy = np.floor(all_corners.min(axis=0)), np.ceil(all_corners.max(axis=0))
    canvas_width, canvas_height = int(max_xy[0]-min_xy[0]+1), int(max_xy[1]-min_xy[1]+1)
    canvas_pixels = canvas_width * canvas_height
    if canvas_width < 1 or canvas_height < 1 or canvas_pixels > max_canvas_pixels:
        raise MultiViewRegistrationError(f"canvas {canvas_width}x{canvas_height} exceeds or violates the declared pixel cap")

    image_records = {}
    for image_id in ids:
        pose = poses[image_id]
        canvas_t = np.array([pose.tx, pose.ty]) - min_xy
        canvas_pose = SimilarityTransform(pose.scale, pose.rotation_rad, float(canvas_t[0]), float(canvas_t[1]))
        image_records[image_id] = {
            "width": dimensions[image_id][0], "height": dimensions[image_id][1],
            "world_transform": pose.to_dict(), "canvas_transform": canvas_pose.to_dict(),
        }
    return {
        "schema_version": "siaux-multiview-transform/0.1",
        "algorithm_id": "DDXX_MV_GLOBAL_SIMILARITY_V1",
        "coordinate_convention": "column_vector_ccw_degrees",
        "root_image_id": root, "images": image_records,
        "canvas": {"width": canvas_width, "height": canvas_height,
                   "world_min_xy": min_xy.tolist(), "world_max_xy": max_xy.tolist(),
                   "pixel_count": int(canvas_pixels), "max_canvas_pixels": int(max_canvas_pixels)},
        "graph": {"image_count": len(ids), "edge_count": len(edges), "cycle_rank": cycle_rank,
                  "connectivity": "connected", "cycle_closure_status": "checked_with_redundant_edges" if cycle_rank else "not_testable_tree_only",
                  "bridge_edge_ids": bridge_ids, "unverified_bridge_edge_count": len(bridge_indices),
                  "bridge_edge_override": bool(allow_unverified_bridge_edges)},
        "global_residual": global_stats, "edge_reports": edge_reports,
        "geometry_gate": gate, "acceptance_threshold_px": acceptance_threshold_px,
        "allow_unverified_bridge_edges": bool(allow_unverified_bridge_edges),
        "limitations": [
            "One 2D similarity transform per image; no homography, parallax, rolling shutter, lens distortion or local deformation.",
            "Graph bridge edges have no independent cycle closure; 3+ image graphs remain pending unless explicitly waived.",
            "Feature/semantic matches are evidence candidates, not proof of correspondence identity.",
            "Geometry registration does not create missing scene content or certify seam quality.",
        ],
    }


def warp_image_to_canvas(image: Any, transform_json: str | dict[str, Any], image_id: str, *, resample: str = "bicubic"):
    """Warp one RGB PIL image into the shared canvas; requires a passed geometry gate."""
    from PIL import Image
    payload = json.loads(transform_json) if isinstance(transform_json, str) else transform_json
    if payload.get("schema_version") not in ("siaux-multiview-transform/0.1", "siaux-multiview-transform/0.2") or payload.get("geometry_gate") != "pass":
        raise MultiViewRegistrationError("supported transform schema and geometry_gate=pass are required")
    if image_id not in payload.get("images", {}):
        raise MultiViewRegistrationError(f"image_id is not registered: {image_id}")
    canvas = payload.get("canvas", {})
    width, height = int(canvas.get("width", 0)), int(canvas.get("height", 0))
    pixels, cap = width*height, int(canvas.get("max_canvas_pixels", 100_000_000))
    if width < 1 or height < 1 or pixels != int(canvas.get("pixel_count", pixels)) or pixels > cap:
        raise MultiViewRegistrationError("transform JSON canvas dimensions/pixel cap are invalid")
    record = payload["images"][image_id]
    source = image.convert("RGB")
    if source.size != (int(record["width"]), int(record["height"])):
        raise MultiViewRegistrationError("source image dimensions differ from the registered input")
    filters = {"nearest": Image.Resampling.NEAREST, "bilinear": Image.Resampling.BILINEAR,
               "bicubic": Image.Resampling.BICUBIC, "lanczos": Image.Resampling.LANCZOS}
    if resample not in filters:
        raise MultiViewRegistrationError("resample must be nearest, bilinear, bicubic or lanczos")

    # Prefer canvas_transform (0.2) when present
    tdict = record.get("canvas_transform") or record["world_transform"]
    model = tdict.get("model", "similarity_2d")
    min_xy = np.asarray(canvas["world_min_xy"], dtype=np.float64)

    if model == "homography_2d":
        H = np.asarray(tdict["matrix_3x3"], dtype=np.float64)
        try:
            Hinv = np.linalg.inv(H)
        except np.linalg.LinAlgError as exc:
            raise MultiViewRegistrationError("canvas homography is singular") from exc
        Hinv = Hinv / Hinv[2, 2]
        # PIL PERSPECTIVE: maps output->input
        coeffs = (
            float(Hinv[0, 0]), float(Hinv[0, 1]), float(Hinv[0, 2]),
            float(Hinv[1, 0]), float(Hinv[1, 1]), float(Hinv[1, 2]),
            float(Hinv[2, 0]), float(Hinv[2, 1]),
        )
        rgb = source.transform((width, height), Image.Transform.PERSPECTIVE, coeffs,
                               resample=filters[resample], fillcolor=(0, 0, 0))
        mask = Image.new("L", source.size, 255).transform(
            (width, height), Image.Transform.PERSPECTIVE, coeffs,
            resample=Image.Resampling.BILINEAR, fillcolor=0,
        )
        return rgb, mask

    # similarity (and local_mesh backbone)
    if "canvas_transform" in record and tdict is record["canvas_transform"]:
        scale = float(tdict["scale"])
        angle = math.radians(float(tdict["rotation_degrees"]))
        translation = np.asarray(tdict["translation_px"], dtype=np.float64)
        inv_linear = _rotation(angle).T / scale
        offset = inv_linear @ (-translation)
    else:
        scale = float(tdict["scale"])
        angle = math.radians(float(tdict["rotation_degrees"]))
        translation = np.asarray(tdict["translation_px"], dtype=np.float64)
        inv_linear = _rotation(angle).T / scale
        offset = inv_linear @ (min_xy - translation)
    matrix = (float(inv_linear[0, 0]), float(inv_linear[0, 1]), float(offset[0]),
              float(inv_linear[1, 0]), float(inv_linear[1, 1]), float(offset[1]))
    rgb = source.transform((width, height), Image.Transform.AFFINE, matrix, resample=filters[resample], fillcolor=(0, 0, 0))
    mask = Image.new("L", source.size, 255).transform(
        (width, height), Image.Transform.AFFINE, matrix, resample=Image.Resampling.BILINEAR, fillcolor=0
    )
    return rgb, mask


# =============================================================================
# Multi-model API (v0.2) — wraps similarity core; adds homography + local_mesh + holdout
# =============================================================================

def register_multiview_v2(
    image_specs,
    matches,
    *,
    root_image_id=None,
    huber_px=10.0,
    acceptance_threshold_px=None,
    max_iterations=60,
    max_canvas_pixels=100_000_000,
    allow_unverified_bridge_edges=False,
    geometry_model="similarity",
    holdout_fraction=None,
    holdout_seed=0,
    local_mesh_grid=(2, 2),
):
    """Explicit geometry-model multiview registration (schema 0.2)."""
    from collections import deque
    import math
    import numpy as np

    model = str(geometry_model or "similarity").strip().lower()
    if model not in ("similarity", "homography", "local_mesh"):
        raise MultiViewRegistrationError("geometry_model must be similarity|homography|local_mesh")

    work_matches = matches
    holdout_matches = None
    if holdout_fraction is not None:
        from .geometry_models import split_edge_anchors_holdout, evaluate_holdout_residuals
        work_matches, holdout_matches = split_edge_anchors_holdout(
            matches,
            holdout_fraction=float(holdout_fraction),
            seed=int(holdout_seed),
            min_train=4 if model == "homography" else 3,
        )

    if model == "similarity":
        result = register_multiview(
            image_specs, work_matches,
            root_image_id=root_image_id, huber_px=huber_px,
            acceptance_threshold_px=acceptance_threshold_px,
            max_iterations=max_iterations, max_canvas_pixels=max_canvas_pixels,
            allow_unverified_bridge_edges=allow_unverified_bridge_edges,
        )
        result = dict(result)
        result["schema_version"] = "siaux-multiview-transform/0.2"
        result["geometry_model"] = "similarity"
        if holdout_matches is not None:
            from .geometry_models import evaluate_holdout_residuals
            result["holdout"] = evaluate_holdout_residuals(result, holdout_matches, "similarity")
            result["holdout_fraction"] = float(holdout_fraction)
            result["holdout_seed"] = int(holdout_seed)
        return result

    if model == "local_mesh":
        from .geometry_models import fit_local_mesh_pair, evaluate_holdout_residuals
        # validate specs
        ids = []
        dimensions = {}
        for item in image_specs:
            iid = item["id"]
            ids.append(iid)
            dimensions[iid] = (int(item["width"]), int(item["height"]))
        local_edge_reports = []
        for edge_index, edge in enumerate(work_matches):
            a, b = edge["image_a"], edge["image_b"]
            anchors = edge.get("anchors") or []
            pa = np.asarray([x["xy_a"] for x in anchors], dtype=np.float64)
            pb = np.asarray([x["xy_b"] for x in anchors], dtype=np.float64)
            weights = np.asarray([
                float(x.get("weight", 1.0)) * float(x.get("confidence", 1.0)) for x in anchors
            ], dtype=np.float64)
            pair = fit_local_mesh_pair(pb, pa, weights, grid=local_mesh_grid, huber_px=huber_px)
            local_edge_reports.append({
                "edge_id": str(edge.get("edge_id", f"edge_{edge_index}")),
                "image_a": a, "image_b": b,
                "local_mesh": pair.to_dict(),
                "local_apply_p95_px": float(np.percentile(
                    np.linalg.norm(pair.apply_local(pb) - pa, axis=1), 95
                )) if len(pa) else None,
                "backbone_p95_px": pair.backbone.p95_residual_px,
            })
        result = register_multiview(
            image_specs, work_matches,
            root_image_id=root_image_id, huber_px=huber_px,
            acceptance_threshold_px=acceptance_threshold_px,
            max_iterations=max_iterations, max_canvas_pixels=max_canvas_pixels,
            allow_unverified_bridge_edges=allow_unverified_bridge_edges,
        )
        result = dict(result)
        result["schema_version"] = "siaux-multiview-transform/0.2"
        result["geometry_model"] = "local_mesh"
        result["algorithm_id"] = "DDXX_MV_LOCAL_MESH_SIMTILE_V0_2"
        result["local_mesh"] = {
            "grid": list(local_mesh_grid),
            "edge_reports": local_edge_reports,
            "note": "Tiles improve pair residual; canvas poses remain global similarity backbone.",
        }
        result["limitations"] = [
            "local_mesh v0.2 = per-edge spatial similarity tiles + global similarity canvas backbone.",
            "Not a true multi-plane / deformable mesh.",
            "Use holdout_fraction when comparing models.",
        ] + list(result.get("limitations") or [])
        if holdout_matches is not None:
            result["holdout"] = evaluate_holdout_residuals(result, holdout_matches, "local_mesh")
            result["holdout_fraction"] = float(holdout_fraction)
            result["holdout_seed"] = int(holdout_seed)
        return result

    # ---- homography ----
    from .geometry_models import HomographyTransform, fit_weighted_homography, evaluate_holdout_residuals

    if not isinstance(image_specs, list) or len(image_specs) < 2:
        raise MultiViewRegistrationError("at least two image_specs are required")
    ids = []
    dimensions = {}
    for item in image_specs:
        image_id, width, height = item.get("id"), item.get("width"), item.get("height")
        if not isinstance(image_id, str) or not image_id or image_id in dimensions:
            raise MultiViewRegistrationError("image IDs must be unique non-empty strings")
        if not isinstance(width, int) or not isinstance(height, int) or width < 1 or height < 1:
            raise MultiViewRegistrationError(f"invalid dimensions for image {image_id}")
        ids.append(image_id)
        dimensions[image_id] = (width, height)
    root = root_image_id or ids[0]
    if root not in dimensions:
        raise MultiViewRegistrationError(f"root_image_id is not present: {root}")
    if not work_matches:
        raise MultiViewRegistrationError("at least one pairwise match edge is required")
    if acceptance_threshold_px is not None and (not math.isfinite(acceptance_threshold_px) or acceptance_threshold_px <= 0):
        raise MultiViewRegistrationError("acceptance_threshold_px must be positive or None")

    edges = []
    adjacency = {image_id: [] for image_id in ids}
    for edge_index, edge in enumerate(work_matches):
        a, b = edge.get("image_a"), edge.get("image_b")
        if a not in dimensions or b not in dimensions or a == b:
            raise MultiViewRegistrationError(f"edge {edge_index} has invalid image endpoints")
        anchors = edge.get("anchors")
        if not isinstance(anchors, list) or len(anchors) < 4:
            raise MultiViewRegistrationError(f"edge {edge_index} needs at least 4 paired anchors for homography")
        pa, pb, weights, names = [], [], [], []
        for anchor_index, anchor in enumerate(anchors):
            xa = np.asarray(anchor["xy_a"], dtype=np.float64)
            xb = np.asarray(anchor["xy_b"], dtype=np.float64)
            weight = float(anchor.get("weight", 1.0)) * float(anchor.get("confidence", 1.0))
            wa, ha = dimensions[a]
            wb, hb = dimensions[b]
            if not (0 <= xa[0] < wa and 0 <= xa[1] < ha and 0 <= xb[0] < wb and 0 <= xb[1] < hb):
                raise MultiViewRegistrationError(f"edge {edge_index} anchor {anchor_index} outside bounds")
            if weight <= 0 or not math.isfinite(weight):
                raise MultiViewRegistrationError(f"edge {edge_index} anchor weight invalid")
            pa.append(xa); pb.append(xb); weights.append(weight); names.append(str(anchor.get("name", f"a{anchor_index}")))
        fit = fit_weighted_homography(np.asarray(pb), np.asarray(pa), np.asarray(weights), huber_px=huber_px)
        adjacency[a].append((b, fit.transform))
        adjacency[b].append((a, fit.transform.inverse()))
        edges.append({
            "edge_id": str(edge.get("edge_id", f"edge_{edge_index}")), "image_a": a, "image_b": b,
            "xy_a": np.asarray(pa), "xy_b": np.asarray(pb), "weights": np.asarray(weights),
            "names": names, "b_to_a": fit.transform, "pairwise_fit": fit,
        })

    poses = {root: HomographyTransform.identity()}
    queue = deque([root])
    while queue:
        current = queue.popleft()
        for neighbour, neighbour_to_current in adjacency[current]:
            if neighbour not in poses:
                poses[neighbour] = poses[current].compose(neighbour_to_current)
                queue.append(neighbour)
    disconnected = sorted(set(ids) - set(poses))
    if disconnected:
        raise MultiViewRegistrationError(f"pairwise match graph is disconnected: {disconnected}")

    bridge_indices = _find_bridge_edge_indices(ids, edges)
    residuals, base_weights = [], []
    for edge in edges:
        a, b = edge["image_a"], edge["image_b"]
        for pa, pb, w in zip(edge["xy_a"], edge["xy_b"], edge["weights"]):
            qa = poses[a].apply(pa[None, :])[0]
            qb = poses[b].apply(pb[None, :])[0]
            residuals.append(float(np.linalg.norm(qa - qb)))
            base_weights.append(float(w))
    norms = np.asarray(residuals, dtype=np.float64)
    base_weights = np.asarray(base_weights, dtype=np.float64)
    factors = np.ones_like(norms)
    outliers = norms > huber_px
    factors[outliers] = huber_px / np.maximum(norms[outliers], 1e-12)
    robust_weights = base_weights * factors
    global_stats = {
        "anchor_count": int(len(norms)),
        "weighted_rmse_px": math.sqrt(float(np.sum(base_weights * norms ** 2) / np.sum(base_weights))),
        "robust_weighted_rmse_px": math.sqrt(float(np.sum(robust_weights * norms ** 2) / np.sum(robust_weights))),
        "median_residual_px": float(np.median(norms)),
        "p95_residual_px": float(np.percentile(norms, 95)),
        "max_residual_px": float(np.max(norms)),
        "huber_px": float(huber_px),
        "downweighted_anchor_count": int(np.count_nonzero(factors < 0.999999)),
        "optimizer_iterations": 0,
        "note": "homography v0.2: pairwise DLT/Huber + graph composition (no joint projective LM)",
    }

    edge_reports, cycle_closures = [], []
    for i, edge in enumerate(edges):
        a, b = edge["image_a"], edge["image_b"]
        expected = poses[a].inverse().compose(poses[b])
        closure = np.linalg.norm(edge["b_to_a"].apply(edge["xy_b"]) - expected.apply(edge["xy_b"]), axis=1)
        closure_p95 = float(np.percentile(closure, 95))
        if i not in bridge_indices:
            cycle_closures.append(closure_p95)
        edge_reports.append({
            "edge_id": edge["edge_id"], "image_a": a, "image_b": b,
            "direction": "image_b_to_image_a", "independent_cycle_check": i not in bridge_indices,
            "pairwise_fit": edge["pairwise_fit"].to_dict(),
            "global_closure": {"p95_residual_px": closure_p95, "max_residual_px": float(np.max(closure))},
        })
    worst_edge = max((x["global_closure"]["p95_residual_px"] for x in edge_reports), default=0.0)
    worst_cycle_edge = max(cycle_closures, default=0.0)
    global_stats["worst_edge_closure_p95_px"] = worst_edge
    global_stats["worst_cycle_checked_edge_closure_p95_px"] = worst_cycle_edge
    bridge_ids = [edges[i]["edge_id"] for i in sorted(bridge_indices)]
    cycle_rank = max(0, len(edges) - len(ids) + 1)

    if acceptance_threshold_px is None:
        gate = "pending_threshold_not_declared"
    elif global_stats["p95_residual_px"] > acceptance_threshold_px:
        gate = "fail_global_residual_threshold"
    elif worst_cycle_edge > acceptance_threshold_px:
        gate = "fail_edge_closure_threshold"
    elif len(ids) > 2 and bridge_indices and not allow_unverified_bridge_edges:
        gate = "pending_unverified_bridge_edges"
    else:
        gate = "pass"

    corners = []
    for image_id in ids:
        width, height = dimensions[image_id]
        points = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float64)
        corners.append(poses[image_id].apply(points))
    all_corners = np.vstack(corners)
    min_xy = np.floor(all_corners.min(axis=0))
    max_xy = np.ceil(all_corners.max(axis=0))
    canvas_width = int(max_xy[0] - min_xy[0] + 1)
    canvas_height = int(max_xy[1] - min_xy[1] + 1)
    canvas_pixels = canvas_width * canvas_height
    if canvas_width < 1 or canvas_height < 1 or canvas_pixels > max_canvas_pixels:
        raise MultiViewRegistrationError(f"canvas {canvas_width}x{canvas_height} exceeds pixel cap")

    T = np.array([[1.0, 0.0, -float(min_xy[0])], [0.0, 1.0, -float(min_xy[1])], [0.0, 0.0, 1.0]], dtype=np.float64)
    image_records = {}
    for image_id in ids:
        pose = poses[image_id]
        canvas_pose = HomographyTransform(T @ pose.matrix)
        image_records[image_id] = {
            "width": dimensions[image_id][0],
            "height": dimensions[image_id][1],
            "world_transform": pose.to_dict(),
            "canvas_transform": canvas_pose.to_dict(),
        }
    result = {
        "schema_version": "siaux-multiview-transform/0.2",
        "geometry_model": "homography",
        "algorithm_id": "DDXX_MV_GLOBAL_HOMOGRAPHY_V0_2",
        "coordinate_convention": "column_vector_homogeneous_H_x",
        "root_image_id": root,
        "images": image_records,
        "canvas": {
            "width": canvas_width, "height": canvas_height,
            "world_min_xy": min_xy.tolist(), "world_max_xy": max_xy.tolist(),
            "pixel_count": int(canvas_pixels), "max_canvas_pixels": int(max_canvas_pixels),
        },
        "graph": {
            "image_count": len(ids), "edge_count": len(edges), "cycle_rank": cycle_rank,
            "connectivity": "connected",
            "cycle_closure_status": "checked_with_redundant_edges" if cycle_rank else "not_testable_tree_only",
            "bridge_edge_ids": bridge_ids,
            "unverified_bridge_edge_count": len(bridge_indices),
            "bridge_edge_override": bool(allow_unverified_bridge_edges),
        },
        "global_residual": global_stats,
        "edge_reports": edge_reports,
        "geometry_gate": gate,
        "acceptance_threshold_px": acceptance_threshold_px,
        "allow_unverified_bridge_edges": bool(allow_unverified_bridge_edges),
        "limitations": [
            "One global 2D homography per image; fails under multi-depth parallax.",
            "v0.2: pairwise DLT/Huber + graph composition; joint projective LM not yet included.",
            "High-DOF risk: always compare holdout residual, not train residual alone.",
            "Bridge edges still lack independent cycle checks unless waived.",
            "Geometry registration does not certify seam quality or synthesize missing content.",
        ],
    }
    if holdout_matches is not None:
        result["holdout"] = evaluate_holdout_residuals(result, holdout_matches, "homography")
        result["holdout_fraction"] = float(holdout_fraction)
        result["holdout_seed"] = int(holdout_seed)
    return result


# Backward-compatible alias: register_multiview remains similarity-only.
# Prefer register_multiview_v2 for model switching.
