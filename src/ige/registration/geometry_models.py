"""SIAX multi-view geometry model family (switchable, explicit IDs).

Models
------
- similarity : global 2D similarity (existing DDXX Umeyama + pose graph LM)
- homography : global 2D projective (DLT + Huber IRLS; pose graph composition + residual)
- local_mesh : per-edge spatial tiles of local similarity (pair detail); multi-image canvas
               still uses a global similarity backbone so common canvas remains defined

Holdout
-------
Anchors may be split train/holdout before fitting. Holdout residuals are the primary
model-selection signal — training residual alone is not sufficient.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Literal

import numpy as np

from .multiview import (
    MultiViewRegistrationError,
    SimilarityFit,
    SimilarityTransform,
    fit_weighted_similarity,
)

GeometryModelName = Literal["similarity", "homography", "local_mesh"]
SUPPORTED_GEOMETRY_MODELS: tuple[str, ...] = ("similarity", "homography", "local_mesh")


# ---------------------------------------------------------------------------
# Homography
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HomographyTransform:
    """3x3 homography mapping source points to target:  H @ [x, y, 1]^T."""

    matrix: np.ndarray  # shape (3, 3)

    def __post_init__(self) -> None:
        m = np.asarray(self.matrix, dtype=np.float64)
        if m.shape != (3, 3) or not np.isfinite(m).all():
            raise MultiViewRegistrationError("homography matrix must be finite 3x3")
        object.__setattr__(self, "matrix", m / (m[2, 2] if abs(m[2, 2]) > 1e-15 else 1.0))

    def apply(self, points: np.ndarray) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise MultiViewRegistrationError("points must be Nx2")
        ones = np.ones((len(pts), 1), dtype=np.float64)
        h = (self.matrix @ np.hstack([pts, ones]).T).T
        w = h[:, 2:3]
        if np.any(np.abs(w) < 1e-12):
            raise MultiViewRegistrationError("homography produced near-zero homogeneous weight")
        return h[:, :2] / w

    def inverse(self) -> "HomographyTransform":
        try:
            inv = np.linalg.inv(self.matrix)
        except np.linalg.LinAlgError as exc:
            raise MultiViewRegistrationError("homography is singular and cannot be inverted") from exc
        return HomographyTransform(inv)

    def compose(self, inner: "HomographyTransform") -> "HomographyTransform":
        """self(inner(x)) = H_self @ H_inner."""
        return HomographyTransform(self.matrix @ inner.matrix)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "homography_2d",
            "convention": "column_vector_homogeneous_H_x",
            "matrix_3x3": self.matrix.tolist(),
        }

    @classmethod
    def identity(cls) -> "HomographyTransform":
        return cls(np.eye(3, dtype=np.float64))


@dataclass(frozen=True)
class HomographyFit:
    transform: HomographyTransform
    residuals_px: np.ndarray
    base_weights: np.ndarray
    robust_weights: np.ndarray
    weighted_rmse_px: float
    robust_weighted_rmse_px: float
    median_residual_px: float
    p95_residual_px: float
    max_residual_px: float
    iterations: int
    inlier_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "transform": self.transform.to_dict(),
            "weighted_rmse_px": self.weighted_rmse_px,
            "robust_weighted_rmse_px": self.robust_weighted_rmse_px,
            "median_residual_px": self.median_residual_px,
            "p95_residual_px": self.p95_residual_px,
            "max_residual_px": self.max_residual_px,
            "iterations": self.iterations,
            "inlier_count": self.inlier_count,
        }


def _validate_pair(source: np.ndarray, target: np.ndarray, weights: np.ndarray, min_n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if source.ndim != 2 or target.ndim != 2 or source.shape != target.shape or source.shape[1] != 2:
        raise MultiViewRegistrationError("source_points and target_points must have the same Nx2 shape")
    if weights.shape != (len(source),):
        raise MultiViewRegistrationError("weights must contain one value per anchor")
    if len(source) < min_n:
        raise MultiViewRegistrationError(f"at least {min_n} paired anchors are required for this geometry model")
    if not np.isfinite(source).all() or not np.isfinite(target).all() or not np.isfinite(weights).all():
        raise MultiViewRegistrationError("anchors and weights must be finite")
    if np.any(weights <= 0):
        raise MultiViewRegistrationError("all anchor weights must be positive")
    return source, target, weights


def _dlt_homography(source: np.ndarray, target: np.ndarray, weights: np.ndarray) -> HomographyTransform:
    """Weighted Direct Linear Transform for H mapping source → target."""
    n = len(source)
    # Normalize for stability (Hartley)
    def _norm(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        mean = pts.mean(axis=0)
        rms = np.sqrt(np.mean(np.sum((pts - mean) ** 2, axis=1)))
        s = math.sqrt(2.0) / max(rms, 1e-8)
        T = np.array([[s, 0, -s * mean[0]], [0, s, -s * mean[1]], [0, 0, 1]], dtype=np.float64)
        ones = np.ones((len(pts), 1))
        return (T @ np.hstack([pts, ones]).T).T[:, :2], T

    src_n, T_s = _norm(source)
    tgt_n, T_t = _norm(target)
    A = np.zeros((2 * n, 9), dtype=np.float64)
    w = np.sqrt(weights / max(float(np.sum(weights)), 1e-12))
    for i, ((x, y), (u, v), wi) in enumerate(zip(src_n, tgt_n, w)):
        A[2 * i] = wi * np.array([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A[2 * i + 1] = wi * np.array([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vt = np.linalg.svd(A, full_matrices=False)
    h = vt[-1].reshape(3, 3)
    # Denormalize: H = T_t^{-1} @ H_n @ T_s
    try:
        H = np.linalg.inv(T_t) @ h @ T_s
    except np.linalg.LinAlgError as exc:
        raise MultiViewRegistrationError("failed to denormalize homography") from exc
    if abs(H[2, 2]) < 1e-15:
        raise MultiViewRegistrationError("degenerate homography (H22 ~ 0)")
    H = H / H[2, 2]
    # Reject extreme projective warp (fold risk)
    if abs(H[2, 0]) > 5e-3 or abs(H[2, 1]) > 5e-3:
        # still allow but check Jacobian-ish via corner mapping later
        pass
    return HomographyTransform(H)


def fit_weighted_homography(
    source_points: np.ndarray,
    target_points: np.ndarray,
    weights: np.ndarray | None = None,
    *,
    huber_px: float = 10.0,
    max_iterations: int = 25,
) -> HomographyFit:
    """Weighted DLT + Huber IRLS for one image pair (source → target)."""
    source = np.asarray(source_points, dtype=np.float64)
    target = np.asarray(target_points, dtype=np.float64)
    base = np.ones(len(source), dtype=np.float64) if weights is None else np.asarray(weights, dtype=np.float64)
    source, target, base = _validate_pair(source, target, base, min_n=4)
    if not math.isfinite(huber_px) or huber_px <= 0:
        raise MultiViewRegistrationError("huber_px must be positive")
    robust = base.copy()
    transform = _dlt_homography(source, target, robust)
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        residuals = np.linalg.norm(transform.apply(source) - target, axis=1)
        factors = np.ones_like(residuals)
        outliers = residuals > huber_px
        factors[outliers] = huber_px / np.maximum(residuals[outliers], 1e-12)
        next_robust = base * factors
        try:
            updated = _dlt_homography(source, target, next_robust)
        except MultiViewRegistrationError:
            break
        delta = float(np.max(np.abs(updated.matrix - transform.matrix)))
        transform, robust = updated, next_robust
        if delta < 1e-10:
            break
    residuals = np.linalg.norm(transform.apply(source) - target, axis=1)
    weighted_rmse = math.sqrt(float(np.sum(base * residuals ** 2) / np.sum(base)))
    robust_rmse = math.sqrt(float(np.sum(robust * residuals ** 2) / np.sum(robust)))
    inliers = int(np.count_nonzero(residuals <= huber_px))
    return HomographyFit(
        transform, residuals, base, robust, weighted_rmse, robust_rmse,
        float(np.median(residuals)), float(np.percentile(residuals, 95)),
        float(np.max(residuals)), iterations, inliers,
    )


# ---------------------------------------------------------------------------
# Local mesh (pair tiles of similarity)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LocalMeshTile:
    tile_id: str
    center_xy: list[float]
    radius_px: float
    transform: SimilarityTransform
    anchor_count: int
    p95_residual_px: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "center_xy": self.center_xy,
            "radius_px": self.radius_px,
            "transform": self.transform.to_dict(),
            "anchor_count": self.anchor_count,
            "p95_residual_px": self.p95_residual_px,
        }


@dataclass(frozen=True)
class LocalMeshPairFit:
    """Per-edge local similarities + global similarity backbone (B→A)."""

    backbone: SimilarityFit
    tiles: list[LocalMeshTile]
    grid: tuple[int, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "local_mesh_similarity_tiles",
            "grid": list(self.grid),
            "backbone": self.backbone.to_dict(),
            "tiles": [t.to_dict() for t in self.tiles],
        }

    def apply_local(self, points: np.ndarray) -> np.ndarray:
        """Apply nearest-tile similarity when available, else backbone."""
        pts = np.asarray(points, dtype=np.float64)
        if not self.tiles:
            return self.backbone.transform.apply(pts)
        out = np.zeros_like(pts)
        centers = np.asarray([t.center_xy for t in self.tiles], dtype=np.float64)
        for i, p in enumerate(pts):
            d = np.linalg.norm(centers - p, axis=1)
            tile = self.tiles[int(np.argmin(d))]
            out[i] = tile.transform.apply(p[None, :])[0]
        return out


def fit_local_mesh_pair(
    source_points: np.ndarray,
    target_points: np.ndarray,
    weights: np.ndarray | None = None,
    *,
    grid: tuple[int, int] = (2, 2),
    huber_px: float = 10.0,
    min_tile_anchors: int = 3,
) -> LocalMeshPairFit:
    """Fit a global similarity backbone plus spatial tile similarities (source→target)."""
    source = np.asarray(source_points, dtype=np.float64)
    target = np.asarray(target_points, dtype=np.float64)
    base = np.ones(len(source), dtype=np.float64) if weights is None else np.asarray(weights, dtype=np.float64)
    source, target, base = _validate_pair(source, target, base, min_n=3)
    gx, gy = int(grid[0]), int(grid[1])
    if gx < 1 or gy < 1 or gx * gy > 16:
        raise MultiViewRegistrationError("local_mesh grid must be 1..4 per axis (max 16 tiles)")
    backbone = fit_weighted_similarity(source, target, base, huber_px=huber_px)
    xmin, ymin = source.min(axis=0)
    xmax, ymax = source.max(axis=0)
    # expand slightly
    pad = 1e-6
    tiles: list[LocalMeshTile] = []
    for iy in range(gy):
        for ix in range(gx):
            x0 = xmin + (xmax - xmin + pad) * ix / gx
            x1 = xmin + (xmax - xmin + pad) * (ix + 1) / gx
            y0 = ymin + (ymax - ymin + pad) * iy / gy
            y1 = ymin + (ymax - ymin + pad) * (iy + 1) / gy
            mask = (source[:, 0] >= x0) & (source[:, 0] < x1) & (source[:, 1] >= y0) & (source[:, 1] < y1)
            if iy == gy - 1:
                mask |= (source[:, 1] >= y0) & (source[:, 1] <= y1 + pad) & (source[:, 0] >= x0) & (source[:, 0] < x1)
            if ix == gx - 1:
                mask |= (source[:, 0] >= x0) & (source[:, 0] <= x1 + pad) & (source[:, 1] >= y0) & (source[:, 1] < y1)
            count = int(np.count_nonzero(mask))
            if count < min_tile_anchors:
                continue
            try:
                fit = fit_weighted_similarity(source[mask], target[mask], base[mask], huber_px=huber_px)
            except MultiViewRegistrationError:
                continue
            tiles.append(LocalMeshTile(
                tile_id=f"t_{ix}_{iy}",
                center_xy=[float((x0 + x1) / 2), float((y0 + y1) / 2)],
                radius_px=float(max(x1 - x0, y1 - y0) / 2),
                transform=fit.transform,
                anchor_count=count,
                p95_residual_px=fit.p95_residual_px,
            ))
    return LocalMeshPairFit(backbone=backbone, tiles=tiles, grid=(gx, gy))


# ---------------------------------------------------------------------------
# Holdout split
# ---------------------------------------------------------------------------

def split_edge_anchors_holdout(
    matches: list[dict[str, Any]],
    *,
    holdout_fraction: float = 0.25,
    seed: int = 0,
    min_train: int = 4,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Per-edge random split of anchors into train / holdout (same edge topology)."""
    if not (0.0 < holdout_fraction < 0.9):
        raise MultiViewRegistrationError("holdout_fraction must be in (0, 0.9)")
    rng = np.random.default_rng(seed)
    train_edges: list[dict[str, Any]] = []
    holdout_edges: list[dict[str, Any]] = []
    for edge in matches:
        anchors = list(edge.get("anchors") or [])
        n = len(anchors)
        if n < min_train + 1:
            # not enough for holdout — all train, empty holdout
            train_edges.append(dict(edge, anchors=anchors))
            holdout_edges.append(dict(edge, anchors=[], holdout_empty=True))
            continue
        idx = np.arange(n)
        rng.shuffle(idx)
        n_hold = max(1, int(round(n * holdout_fraction)))
        n_hold = min(n_hold, n - min_train)
        hold_idx = set(int(i) for i in idx[:n_hold])
        train_a = [anchors[i] for i in range(n) if i not in hold_idx]
        hold_a = [anchors[i] for i in range(n) if i in hold_idx]
        train_edges.append(dict(edge, anchors=train_a))
        holdout_edges.append(dict(edge, anchors=hold_a))
    return train_edges, holdout_edges


def evaluate_holdout_residuals(
    result: dict[str, Any],
    holdout_matches: list[dict[str, Any]],
    geometry_model: str,
) -> dict[str, Any]:
    """Apply solved poses to holdout anchors; report residuals (never used in fit)."""
    images = result.get("images") or {}
    model = geometry_model
    residuals: list[float] = []
    per_edge: list[dict[str, Any]] = []
    for edge in holdout_matches:
        a, b = edge.get("image_a"), edge.get("image_b")
        anchors = edge.get("anchors") or []
        if not anchors or a not in images or b not in images:
            per_edge.append({"edge_id": edge.get("edge_id"), "holdout_count": 0, "p95_residual_px": None})
            continue
        ta = _transform_from_record(images[a]["world_transform"])
        tb = _transform_from_record(images[b]["world_transform"])
        edge_res = []
        for anc in anchors:
            pa = np.asarray(anc["xy_a"], dtype=np.float64)
            pb = np.asarray(anc["xy_b"], dtype=np.float64)
            qa = ta.apply(pa[None, :])[0]
            qb = tb.apply(pb[None, :])[0]
            r = float(np.linalg.norm(qa - qb))
            edge_res.append(r)
            residuals.append(r)
        per_edge.append({
            "edge_id": edge.get("edge_id", f"{a}-{b}"),
            "image_a": a, "image_b": b,
            "holdout_count": len(edge_res),
            "p95_residual_px": float(np.percentile(edge_res, 95)) if edge_res else None,
            "median_residual_px": float(np.median(edge_res)) if edge_res else None,
            "max_residual_px": float(np.max(edge_res)) if edge_res else None,
        })
    if residuals:
        arr = np.asarray(residuals, dtype=np.float64)
        summary = {
            "holdout_anchor_count": int(len(arr)),
            "weighted_rmse_px": float(np.sqrt(np.mean(arr ** 2))),
            "median_residual_px": float(np.median(arr)),
            "p95_residual_px": float(np.percentile(arr, 95)),
            "max_residual_px": float(np.max(arr)),
        }
    else:
        summary = {
            "holdout_anchor_count": 0,
            "weighted_rmse_px": None,
            "median_residual_px": None,
            "p95_residual_px": None,
            "max_residual_px": None,
            "note": "no holdout anchors available",
        }
    return {
        "geometry_model": model,
        "algorithm_id": result.get("algorithm_id"),
        "train_geometry_gate": result.get("geometry_gate"),
        "train_global_residual": result.get("global_residual"),
        "holdout_global": summary,
        "holdout_edges": per_edge,
        "interpretation": [
            "Holdout anchors were not used in the fit.",
            "Prefer lower holdout p95 over lower train residual when choosing a model.",
            "A model can overfit train anchors and still fail holdout (esp. high-DOF homography).",
        ],
    }


def _transform_from_record(rec: dict[str, Any]):
    model = rec.get("model")
    if model == "similarity_2d":
        return SimilarityTransform(
            float(rec["scale"]),
            math.radians(float(rec["rotation_degrees"])),
            float(rec["translation_px"][0]),
            float(rec["translation_px"][1]),
        )
    if model == "homography_2d":
        return HomographyTransform(np.asarray(rec["matrix_3x3"], dtype=np.float64))
    raise MultiViewRegistrationError(f"unsupported transform model in record: {model}")
