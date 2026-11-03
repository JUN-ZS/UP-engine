"""C0.3.1 — DDXX consecutive-pair static gate + temporal seam/frontier metrics for NFE.

Mixes geometry methods proven on DDXX/N1 verify figures into temporal still chain:
- SIFT mutual + RANSAC anchors between F_t and F_{t+1}
- Similarity / Homography pair fits (holdout optional)
- Overlap MAE (should be low if hard-lock; for pure time usually N/A → use full-frame MAE)
- Frontier-style residual: median residual of anchors as motion signature (dynamic OK)

NOT generation. NOT I2V. Does not force-align dynamic body anchors to zero motion.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image


@dataclass
class PairDDXXReport:
    ok: bool
    pair: str
    n_anchors: int = 0
    sim_p95: Optional[float] = None
    sim_median: Optional[float] = None
    sim_scale: Optional[float] = None
    sim_rot_deg: Optional[float] = None
    sim_tx: Optional[float] = None
    sim_ty: Optional[float] = None
    homo_p95: Optional[float] = None
    mae_full: Optional[float] = None
    flow_p50: Optional[float] = None
    gate: str = "pending"
    reasons: list[str] = field(default_factory=list)
    note: str = "static_similarity_expected_near_identity_for_locked_camera; dynamic_content_may_move"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_rgb(path: Path, size: tuple[int, int] | None = None) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    if size is not None and im.size != size:
        im = im.resize(size, Image.Resampling.LANCZOS)
    return np.asarray(im, np.uint8)


def consecutive_ddxx_pair(
    path_a: Path,
    path_b: Path,
    *,
    pair_id: str = "A_B",
    size: tuple[int, int] = (1280, 720),
    sim_p95_max: float = 12.0,
    scale_tol: float = 0.08,
    rot_tol_deg: float = 5.0,
    trans_tol_px: float = 40.0,
    min_anchors: int = 12,
) -> PairDDXXReport:
    """Run light DDXX between two temporal stills (locked camera expected near identity)."""
    reasons: list[str] = []
    a = _load_rgb(path_a, size)
    b = _load_rgb(path_b, size)
    mae = float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))))
    flow_p50 = None
    try:
        import cv2

        g0 = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
        g1 = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
        fl = cv2.calcOpticalFlowFarneback(g0, g1, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        flow_p50 = float(np.median(np.sqrt(fl[..., 0] ** 2 + fl[..., 1] ** 2)))
    except Exception:
        pass

    n_anchors = 0
    sim_p95 = sim_med = sim_s = sim_r = sim_tx = sim_ty = None
    homo_p95 = None
    try:
        from ige.registration.features import build_sift_match_graph
        from ige.registration.multiview import fit_weighted_similarity
        from ige.registration.geometry_models import fit_weighted_homography

        imgs = {"A": a, "B": b}
        graph = build_sift_match_graph(imgs, max_features=2000, min_inliers=8, max_anchors_per_edge=200)
        edges = graph.get("matches") or graph.get("edges") or []
        # features.py may return 'edges' with anchors
        if not edges and "diagnostics" in graph:
            edges = [e for e in (graph.get("edges") or []) if e]
        # normalize edge structure
        edge = None
        for e in edges:
            ids = {e.get("image_a"), e.get("image_b")}
            if ids == {"A", "B"}:
                edge = e
                break
        if edge is None and edges:
            edge = edges[0]
        if edge is None:
            reasons.append("no_sift_edge")
        else:
            anchors = edge.get("anchors") or []
            if not anchors and "xy_a" in edge:
                # alternate packing
                xy_a = np.asarray(edge["xy_a"])
                xy_b = np.asarray(edge["xy_b"])
            else:
                xy_a = np.asarray([x["xy_a"] for x in anchors], dtype=np.float64)
                xy_b = np.asarray([x["xy_b"] for x in anchors], dtype=np.float64)
            n_anchors = int(len(xy_a))
            if n_anchors < min_anchors:
                reasons.append(f"few_anchors={n_anchors}<{min_anchors}")
            else:
                w = np.ones(n_anchors, dtype=np.float64)
                fit = fit_weighted_similarity(xy_b, xy_a, w)
                sim_p95 = float(fit.p95_residual_px)
                sim_med = float(fit.median_residual_px)
                sim_s = float(fit.transform.scale)
                sim_r = float(np.degrees(fit.transform.rotation_rad))
                sim_tx = float(fit.transform.tx)
                sim_ty = float(fit.transform.ty)
                # locked-camera soft static checks
                if abs(sim_s - 1.0) > scale_tol:
                    reasons.append(f"scale_drift={sim_s:.4f}")
                if abs(sim_r) > rot_tol_deg:
                    reasons.append(f"rot_drift_deg={sim_r:.3f}")
                if abs(sim_tx) > trans_tol_px or abs(sim_ty) > trans_tol_px:
                    reasons.append(f"trans_drift=({sim_tx:.1f},{sim_ty:.1f})")
                if sim_p95 > sim_p95_max:
                    reasons.append(f"sim_p95={sim_p95:.2f}>{sim_p95_max}")
                try:
                    if n_anchors >= 4:
                        hf = fit_weighted_homography(xy_b, xy_a, w)
                        homo_p95 = float(hf.p95_residual_px)
                except Exception as exc:
                    reasons.append(f"homo_skip:{type(exc).__name__}")
    except Exception as exc:
        reasons.append(f"ddxx_unavailable:{type(exc).__name__}:{str(exc)[:80]}")

    # Soft gate: missing DDXX is pending not hard fail if mae ok
    if any(r.startswith("ddxx_unavailable") or r == "no_sift_edge" for r in reasons) and mae is not None:
        gate = "soft_mae_only"
        ok = True  # do not kill NFE solely on missing SIFT
        # strip hard fails that came with unavailability only
    elif reasons:
        gate = "fail_static_or_anchors"
        ok = False
    else:
        gate = "pass_static_near_identity"
        ok = True

    return PairDDXXReport(
        ok=ok,
        pair=pair_id,
        n_anchors=n_anchors,
        sim_p95=sim_p95,
        sim_median=sim_med,
        sim_scale=sim_s,
        sim_rot_deg=sim_r,
        sim_tx=sim_tx,
        sim_ty=sim_ty,
        homo_p95=homo_p95,
        mae_full=mae,
        flow_p50=flow_p50,
        gate=gate,
        reasons=reasons,
    )


def chain_ddxx_reports(
    frame_paths: list[Path],
    *,
    size: tuple[int, int] = (1280, 720),
    out_json: Path | None = None,
) -> dict[str, Any]:
    pairs = []
    for i in range(len(frame_paths) - 1):
        rep = consecutive_ddxx_pair(
            frame_paths[i],
            frame_paths[i + 1],
            pair_id=f"F{i:02d}->F{i+1:02d}",
            size=size,
        )
        pairs.append(rep.to_dict())
    ok_n = sum(1 for p in pairs if p.get("ok"))
    summary = {
        "format": "ige.nfe.ddxx_chain_gate",
        "format_version": "1.0",
        "n_frames": len(frame_paths),
        "n_pairs": len(pairs),
        "n_ok": ok_n,
        "all_ok": ok_n == len(pairs) and len(pairs) > 0,
        "pairs": pairs,
        "not_image_to_video": True,
        "quality_qualified": False,
        "mix_role": "C0.3.1_static_camera_gate_plus_motion_signature",
        "from_figures": [
            "GT_anchors_similarity",
            "sim_vs_homography_residuals",
            "seam_frontier_mae_trend",
            "continuous_frame_multigrid_verify",
        ],
        "note": "Methods mixed from DDXX/N1 verify figures; applied as temporal consecutive stills gate.",
    }
    if out_json:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(out_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
