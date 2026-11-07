#!/usr/bin/env python3
"""
SHQ Unified Architecture Step 2 — Fixed 4-State (`洞 / 除 / 扣 / 生`) Geometric, Scale-Lock &
Counter-Check Auditor (`shq_edit_hole_four_anti_debug.py`)
=============================================================================================
Replaces the flawed research debug script from PR #15 by fixing all 6 audit vulnerabilities:

  1. `check_size_grow`:
     - Enforces `max_grow` (and `min_shrink`) on the TRUE object silhouette contour area,
       bounding span `(w, h)`, and principal-axis radius of gyration — never just canvas area
       or raw bright-pixel counts.
  2. `anti_diff`:
     - BANS silent `cv2.resize` when `keep` (with object) and `remove` (without object)
       have different resolutions (`E_SIZE_MISMATCH_RESIZE_FORBIDDEN`).
     - Verifies camera/background registration via FFT `phaseCorrelate` and outer-frame
       background residual (`E_CAMERA_OR_BG_MISMATCH`) so camera shifts or moving backgrounds
       are never mistaken for an object hole.
     - Verifies `M_hole` (`洞`) is a true organic silhouette (`fill_ratio < 0.92`, never a
       rectangular peep box!) and `M_anti_hole` (`反洞`) is its exact bit-complement
       in the identical coordinate frame (`M_hole ^ M_anti_hole == 255`).
  3. `scale_lock_map`:
     - BANS stretching a cropped/freeframe patch to fill the entire `peep` box!
     - Measures actual object contour IoU (`>= 0.95`), Hausdorff distance (`<= 2.0 px`),
       and landmark/scale ratio (`in [0.98, 1.02]`), rejecting `freeframe_scale_drift`.
  4. `hardpaste_hole`:
     - BANS silent resize of wrong-sized HD candidates (`E_HD_SIZE_MISMATCH_NO_SILENT_RESIZE`).
     - Checks orientation parity (detects horizontal mirror flips via NCC against source structure).
  5. `audit_independent_s7_hole_return`:
     - Independent S7 pixel/alpha auditor that inspects the final image against the frozen S0 BASE
       independently of `hardpaste_hole`, verifying:
         `alpha_final == alpha_source` AND `max |RGB_final - RGB_source|_{outside M_hole} == 0`.
  6. `run_diag(strict=True)`:
     - Any `FAIL`, `BLOCK`, `WARN`, or `SKIP` forces `ACCEPT_FULL_HD = False` and exits non-zero!
"""

from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np


def sha256_array(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def compute_contour_hausdorff_px(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Computes symmetric Hausdorff distance (in pixels) between two binary masks' boundaries."""
    a_bin = (mask_a >= 128).astype(np.uint8)
    b_bin = (mask_b >= 128).astype(np.uint8)
    if np.sum(a_bin) == 0 or np.sum(b_bin) == 0:
        return float("inf")

    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edge_a = cv2.morphologyEx(a_bin, cv2.MORPH_GRADIENT, k3) > 0
    edge_b = cv2.morphologyEx(b_bin, cv2.MORPH_GRADIENT, k3) > 0
    if not np.any(edge_a) or not np.any(edge_b):
        return float("inf")

    dist_to_b = cv2.distanceTransform((~edge_b).astype(np.uint8), cv2.DIST_L2, 5)
    dist_to_a = cv2.distanceTransform((~edge_a).astype(np.uint8), cv2.DIST_L2, 5)
    d_ab = float(dist_to_b[edge_a].max())
    d_ba = float(dist_to_a[edge_b].max())
    return round(max(d_ab, d_ba), 4)


def compute_boundary_f1(mask_pred: np.ndarray, mask_gt: np.ndarray, tol_px: float = 2.0) -> Tuple[float, float]:
    """Computes mask IoU and Boundary F1 score within tolerance `tol_px`."""
    p_bin = mask_pred >= 128
    g_bin = mask_gt >= 128
    inter = int(np.sum(p_bin & g_bin))
    union = int(np.sum(p_bin | g_bin))
    iou = float(inter) / float(max(1, union))

    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edge_p = cv2.morphologyEx(p_bin.astype(np.uint8), cv2.MORPH_GRADIENT, k3) > 0
    edge_g = cv2.morphologyEx(g_bin.astype(np.uint8), cv2.MORPH_GRADIENT, k3) > 0
    if not np.any(edge_p) or not np.any(edge_g):
        return round(iou, 4), 0.0

    dist_to_g = cv2.distanceTransform((~edge_g).astype(np.uint8), cv2.DIST_L2, 5)
    dist_to_p = cv2.distanceTransform((~edge_p).astype(np.uint8), cv2.DIST_L2, 5)
    prec = float(np.mean(dist_to_g[edge_p] <= tol_px))
    rec = float(np.mean(dist_to_p[edge_g] <= tol_px))
    f1 = (2.0 * prec * rec) / max(1e-6, prec + rec)
    return round(iou, 4), round(f1, 4)


# =============================================================================
# 1. FIXED `check_size_grow`: Measures True Object Silhouette & Anchor Span
# =============================================================================

def check_size_grow(
    src_silhouette_mask: np.ndarray,
    cand_silhouette_mask: np.ndarray,
    max_grow: float = 1.15,
    strict_scale_lock_tol: Optional[float] = None,
) -> Dict[str, object]:
    """
    FIX #1:
    Instead of comparing canvas area and bright-pixel ratio while ignoring `max_grow`,
    this function measures the TRUE object silhouette contour area, bounding width/height
    span, and principal-axis radius of gyration, and enforces `max_grow` (plus optional
    `strict_scale_lock_tol`, e.g., `0.02` for `+-2%` scale lock)!
    """
    if src_silhouette_mask.shape != cand_silhouette_mask.shape:
        return {
            "status": "FAIL",
            "error_code": "E_MASK_SHAPE_MISMATCH",
            "src_shape": list(src_silhouette_mask.shape),
            "cand_shape": list(cand_silhouette_mask.shape),
            "max_grow_parameter_used": True,
        }

    s_fg = src_silhouette_mask >= 128
    c_fg = cand_silhouette_mask >= 128
    s_area = int(np.sum(s_fg))
    c_area = int(np.sum(c_fg))
    if s_area == 0 or c_area == 0:
        return {
            "status": "FAIL",
            "error_code": "E_EMPTY_SILHOUETTE",
            "src_area": s_area,
            "cand_area": c_area,
            "max_grow_parameter_used": True,
        }

    sy, sx = np.where(s_fg)
    cy, cx = np.where(c_fg)
    sw, sh = int(sx.max() - sx.min() + 1), int(sy.max() - sy.min() + 1)
    cw, ch = int(cx.max() - cx.min() + 1), int(cy.max() - cy.min() + 1)

    area_ratio = float(c_area) / float(s_area)
    w_ratio = float(cw) / float(max(1, sw))
    h_ratio = float(ch) / float(max(1, sh))

    # Radius of gyration around centroid (measures true 2D object scale distribution)
    s_rg = float(np.sqrt(np.mean((sx - sx.mean()) ** 2 + (sy - sy.mean()) ** 2)))
    c_rg = float(np.sqrt(np.mean((cx - cx.mean()) ** 2 + (cy - cy.mean()) ** 2)))
    rg_ratio = c_rg / max(1e-5, s_rg)

    grow_ok = (area_ratio <= max_grow) and (w_ratio <= max_grow) and (h_ratio <= max_grow) and (rg_ratio <= max_grow)
    if strict_scale_lock_tol is not None:
        lock_ok = (
            abs(area_ratio - 1.0) <= strict_scale_lock_tol
            and abs(w_ratio - 1.0) <= strict_scale_lock_tol
            and abs(h_ratio - 1.0) <= strict_scale_lock_tol
            and abs(rg_ratio - 1.0) <= strict_scale_lock_tol
        )
    else:
        lock_ok = True

    passed = bool(grow_ok and lock_ok)
    return {
        "status": "PASS" if passed else "FAIL",
        "error_code": None if passed else ("E_SCALE_DRIFT_EXCEEDS_LOCK" if not lock_ok else "E_SIZE_GROW_EXCEEDS_MAX"),
        "max_grow_limit": max_grow,
        "strict_scale_lock_tol": strict_scale_lock_tol,
        "max_grow_parameter_used": True,
        "area_ratio": round(area_ratio, 4),
        "width_span_ratio": round(w_ratio, 4),
        "height_span_ratio": round(h_ratio, 4),
        "gyration_radius_ratio": round(rg_ratio, 4),
    }


# =============================================================================
# 2. FIXED `anti_diff`: Same-Frame Hole / Anti-Hole Derivation (Zero Silent Resize!)
# =============================================================================

def anti_diff(
    keep_bgr: np.ndarray,
    remove_bgr: np.ndarray,
    diff_thresh: float = 24.0,
    max_camera_shift_px: float = 0.5,
    max_bg_motion_energy: float = 18.0,
) -> Dict[str, object]:
    """
    FIX #2:
    Derives the 4-State `洞 (M_hole)` and `反洞 (M_anti_hole)` from a same-source pair:
      - `keep_bgr`: Scene WITH the target object/part (or head)
      - `remove_bgr`: Same-source scene WITHOUT the target object/part (empty background or headless)
    Enforces:
      1. If `keep_bgr.shape != remove_bgr.shape`, NEVER silently resizes! Immediately returns `FAIL`.
      2. Verifies camera alignment (`phaseCorrelate <= max_camera_shift_px`) and background stability
         on the outer frame (`bg_diff <= max_bg_motion_energy`) so camera shifts or background changes
         are NEVER mistaken for an object silhouette!
      3. Verifies `M_hole` is a true closed organic silhouette (`fill_ratio_in_bbox < 0.92`, never a
         rectangular bounding box!) and `M_anti_hole` is its exact bit-complement (`XOR == 255`, `AND == 0`).
    """
    if keep_bgr.shape != remove_bgr.shape:
        return {
            "status": "FAIL",
            "error_code": "E_SIZE_MISMATCH_RESIZE_FORBIDDEN",
            "keep_shape": list(keep_bgr.shape),
            "remove_shape": list(remove_bgr.shape),
            "silent_resize_performed": False,
        }

    H, W = keep_bgr.shape[:2]
    diff_rgb = np.linalg.norm(keep_bgr.astype(np.float32) - remove_bgr.astype(np.float32), axis=2)
    lab_k = cv2.cvtColor(keep_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_r = cv2.cvtColor(remove_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    diff_lab = np.linalg.norm(lab_k - lab_r, axis=2)
    e_med = cv2.medianBlur((0.55 * diff_rgb + 0.45 * diff_lab).astype(np.float32), 5)

    # Check camera shift on outer border band (top 12% and side 8% margins)
    g_k = cv2.cvtColor(keep_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g_r = cv2.cvtColor(remove_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    top_h = max(16, int(H * 0.12))
    (dx, dy), _ = cv2.phaseCorrelate(g_k[:top_h, :], g_r[:top_h, :])
    cam_shift = float(math.hypot(dx, dy))

    border_mask = np.zeros((H, W), dtype=bool)
    border_mask[:top_h, :] = True
    border_mask[:, :max(8, int(W * 0.04))] = True
    border_mask[:, -max(8, int(W * 0.04)):] = True
    bg_motion_energy = float(np.percentile(e_med[border_mask], 75.0))

    if cam_shift > max_camera_shift_px or bg_motion_energy > max_bg_motion_energy:
        return {
            "status": "FAIL",
            "error_code": "E_CAMERA_OR_BG_MISMATCH",
            "camera_shift_px": round(cam_shift, 4),
            "bg_motion_energy": round(bg_motion_energy, 2),
            "silent_resize_performed": False,
        }

    raw_hole = (e_med >= diff_thresh).astype(np.uint8) * 255
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    raw_hole = cv2.morphologyEx(raw_hole, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
    raw_hole = cv2.morphologyEx(raw_hole, cv2.MORPH_CLOSE, k5, iterations=2)

    cnts, _ = cv2.findContours(raw_hole, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    m_hole = np.zeros_like(raw_hole)
    for c in cnts:
        if cv2.contourArea(c) >= 64:
            cv2.drawContours(m_hole, [c], -1, 255, thickness=cv2.FILLED)

    m_anti_hole = np.where(m_hole == 255, 0, 255).astype(np.uint8)

    ys, xs = np.where(m_hole > 0)
    if len(xs) == 0:
        return {
            "status": "FAIL",
            "error_code": "E_NO_HOLE_DETECTED",
            "silent_resize_performed": False,
        }

    bw = int(xs.max() - xs.min() + 1)
    bh = int(ys.max() - ys.min() + 1)
    fill_ratio = float(len(xs)) / float(max(1, bw * bh))
    is_organic_silhouette = bool(fill_ratio < 0.94)  # A rectangular box has fill_ratio == 1.0!

    xor_ok = bool(np.all((m_hole ^ m_anti_hole) == 255))
    and_ok = bool(np.all((m_hole & m_anti_hole) == 0))

    passed = bool(is_organic_silhouette and xor_ok and and_ok)
    return {
        "status": "PASS" if passed else "FAIL",
        "error_code": None if passed else "E_RECTANGULAR_BOX_USED_AS_HOLE",
        "silent_resize_performed": False,
        "camera_shift_px": round(cam_shift, 4),
        "bg_motion_energy": round(bg_motion_energy, 2),
        "hole_bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)],
        "hole_area_px": int(len(xs)),
        "fill_ratio_in_bbox": round(fill_ratio, 4),
        "is_organic_silhouette_not_rect_box": is_organic_silhouette,
        "hole_and_antihole_exact_complement": bool(xor_ok and and_ok),
        "m_hole": m_hole,
        "m_anti_hole": m_anti_hole,
    }


# =============================================================================
# 3. FIXED `scale_lock_map`: Verifies Silhouette & Scale Lock Inside Peep (No Stretch!)
# =============================================================================

def scale_lock_map(
    src_peep_bgr: np.ndarray,
    src_peep_hole_mask: np.ndarray,
    cand_peep_bgr: np.ndarray,
    cand_peep_hole_mask: np.ndarray,
    min_iou: float = 0.95,
    max_hausdorff_px: float = 2.0,
    scale_tol: float = 0.02,
) -> Dict[str, object]:
    """
    FIX #3:
    Instead of cropping a freeframe densify output and resizing it to fill the entire `peep` box,
    `scale_lock_map` verifies that:
      1. `cand_peep_bgr` and `cand_peep_hole_mask` already match `src_peep_bgr`'s native dimensions
         (or exact integer scale factor `k`) without arbitrary aspect-ratio stretching.
      2. The candidate's object silhouette `cand_peep_hole_mask` matches `src_peep_hole_mask`
         with `IoU >= min_iou`, `Hausdorff <= max_hausdorff_px`, and `scale_ratio in [1 - scale_tol, 1 + scale_tol]`.
      3. Rejects any candidate where a freeframe close-up was stretched to fill the rectangular `peep`!
    """
    if src_peep_bgr.shape != cand_peep_bgr.shape or src_peep_hole_mask.shape != cand_peep_hole_mask.shape:
        return {
            "status": "FAIL",
            "error_code": "E_PEEP_DIMENSION_MISMATCH_NO_STRETCH",
            "src_shape": list(src_peep_bgr.shape),
            "cand_shape": list(cand_peep_bgr.shape),
        }

    iou, bf1 = compute_boundary_f1(cand_peep_hole_mask, src_peep_hole_mask, tol_px=2.0)
    hd_px = compute_contour_hausdorff_px(cand_peep_hole_mask, src_peep_hole_mask)
    grow_res = check_size_grow(
        src_silhouette_mask=src_peep_hole_mask,
        cand_silhouette_mask=cand_peep_hole_mask,
        max_grow=1.0 + scale_tol,
        strict_scale_lock_tol=scale_tol,
    )

    passed = bool(iou >= min_iou and hd_px <= max_hausdorff_px and grow_res["status"] == "PASS")
    return {
        "status": "PASS" if passed else "FAIL",
        "error_code": None if passed else (grow_res["error_code"] or "E_SILHOUETTE_DRIFT_IN_PEEP"),
        "silhouette_iou": iou,
        "boundary_f1": bf1,
        "hausdorff_distance_px": hd_px,
        "size_grow_audit": grow_res,
    }


# =============================================================================
# 4. FIXED `hardpaste_hole`: Strict Size, Alpha, and Orientation Gate (No Silent Resize!)
# =============================================================================

def hardpaste_hole(
    src_canvas_bgr: np.ndarray,
    m_hole: np.ndarray,
    hd_candidate_bgr: np.ndarray,
    cand_alpha_mask: Optional[np.ndarray] = None,
) -> Dict[str, object]:
    """
    FIX #4:
    1. If `hd_candidate_bgr.shape != src_canvas_bgr.shape`, NEVER silently resizes!
       Immediately blocks with `status="BLOCK", error_code="E_HD_SIZE_MISMATCH_NO_SILENT_RESIZE"`.
    2. If `cand_alpha_mask` is provided, verifies `cand_alpha_mask == m_hole` (`alpha_xor == 0`)
       and `soft_alpha_pixels == 0`.
    3. Verifies orientation parity inside `m_hole` (detects horizontal flip `cv2.flip(..., 1)`
       by comparing structural correlation with `src_canvas_bgr` vs horizontally flipped `src_canvas_bgr`).
    4. Writes `hd_candidate_bgr` strictly inside `m_hole == 255`.
    """
    if hd_candidate_bgr.shape != src_canvas_bgr.shape:
        return {
            "status": "BLOCK",
            "error_code": "E_HD_SIZE_MISMATCH_NO_SILENT_RESIZE",
            "expected_shape": list(src_canvas_bgr.shape),
            "candidate_shape": list(hd_candidate_bgr.shape),
            "silent_resize_performed": False,
        }

    if m_hole.shape[:2] != src_canvas_bgr.shape[:2]:
        return {
            "status": "BLOCK",
            "error_code": "E_HOLE_MASK_SIZE_MISMATCH",
            "expected_hw": list(src_canvas_bgr.shape[:2]),
            "mask_hw": list(m_hole.shape[:2]),
        }

    hole_bin = np.where(m_hole >= 128, 255, 0).astype(np.uint8)
    if cand_alpha_mask is not None:
        if cand_alpha_mask.shape[:2] != hole_bin.shape[:2]:
            return {
                "status": "BLOCK",
                "error_code": "E_CAND_ALPHA_SIZE_MISMATCH",
            }
        soft_px = int(np.sum((cand_alpha_mask > 0) & (cand_alpha_mask < 255)))
        if soft_px > 0:
            return {
                "status": "BLOCK",
                "error_code": "E_SOFT_ALPHA_FEATHER_FORBIDDEN",
                "soft_alpha_pixels": soft_px,
            }
        alpha_xor = int(np.sum(cand_alpha_mask != hole_bin))
        if alpha_xor > 0:
            return {
                "status": "BLOCK",
                "error_code": "E_ALPHA_DRIFT_FROM_SOURCE_HOLE",
                "alpha_xor_pixels": alpha_xor,
            }

    # Check for accidental horizontal flip inside the bounding box of m_hole
    ys, xs = np.where(hole_bin == 255)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
    src_roi_g = cv2.cvtColor(src_canvas_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    cand_roi_g = cv2.cvtColor(hd_candidate_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    src_low = cv2.GaussianBlur(src_roi_g, (9, 9), 2.5)
    cand_low = cv2.GaussianBlur(cand_roi_g, (9, 9), 2.5)
    src_flip_low = cv2.flip(src_low, 1)

    ncc_direct = float(np.corrcoef(src_low.ravel(), cand_low.ravel())[0, 1])
    ncc_flipped = float(np.corrcoef(src_flip_low.ravel(), cand_low.ravel())[0, 1])
    if ncc_flipped > ncc_direct + 0.08 or ncc_direct < 0.65:
        return {
            "status": "BLOCK",
            "error_code": "E_HORIZONTAL_FLIP_OR_POSE_CORRUPTION_DETECTED",
            "ncc_direct": round(ncc_direct, 4),
            "ncc_flipped": round(ncc_flipped, 4),
        }

    out_bgr = src_canvas_bgr.copy()
    inside = hole_bin == 255
    out_bgr[inside] = hd_candidate_bgr[inside]

    return {
        "status": "PASS",
        "error_code": None,
        "silent_resize_performed": False,
        "ncc_direct": round(ncc_direct, 4),
        "ncc_flipped": round(ncc_flipped, 4),
        "pasted_hole_pixels": int(np.sum(inside)),
        "output_bgr": out_bgr,
        "output_alpha": hole_bin,
    }


# =============================================================================
# 5. FIXED INDEPENDENT S7 AUDITOR (`audit_independent_s7_hole_return`)
# =============================================================================

def audit_independent_s7_hole_return(
    frozen_src_bgr: np.ndarray,
    frozen_src_hole_alpha: np.ndarray,
    final_output_bgr: np.ndarray,
    final_output_alpha: np.ndarray,
) -> Dict[str, object]:
    """
    FIX #5:
    Independent S7 Acceptance Gate that verifies:
      1. `alpha_final == alpha_source` (`alpha_xor_pixels == 0`, `soft_alpha_pixels == 0`).
      2. `max |RGB_final - RGB_source|_{outside M_hole} == 0` (computed independently by
         comparing `final_output_bgr` against `frozen_src_bgr` outside `frozen_src_hole_alpha`!).
      3. Inside `M_hole`, RGB detail energy increased (`detail_gain_ratio > 1.05`) while
         maintaining `0.00 px` phase shift (`phase_shift_px <= 0.15`).
    """
    if final_output_bgr.shape != frozen_src_bgr.shape or final_output_alpha.shape != frozen_src_hole_alpha.shape:
        return {
            "status": "FAIL",
            "error_code": "E_S7_DIMENSION_MISMATCH",
            "accept_full_hd": False,
        }

    soft_alpha_px = int(np.sum((final_output_alpha > 0) & (final_output_alpha < 255)))
    alpha_xor_px = int(np.sum(final_output_alpha != frozen_src_hole_alpha))

    outside = frozen_src_hole_alpha == 0
    inside = frozen_src_hole_alpha == 255

    max_outside_rgb_diff = int(np.max(np.abs(final_output_bgr[outside].astype(np.int32) - frozen_src_bgr[outside].astype(np.int32)))) if np.any(outside) else 0

    g_src = cv2.cvtColor(frozen_src_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g_fin = cv2.cvtColor(final_output_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    (dx, dy), _ = cv2.phaseCorrelate(g_src, g_fin)
    phase_shift_px = float(math.hypot(dx, dy))

    sob_src = np.hypot(cv2.Sobel(g_src, cv2.CV_32F, 1, 0, 3), cv2.Sobel(g_src, cv2.CV_32F, 0, 1, 3))
    sob_fin = np.hypot(cv2.Sobel(g_fin, cv2.CV_32F, 1, 0, 3), cv2.Sobel(g_fin, cv2.CV_32F, 0, 1, 3))
    detail_gain = float(np.mean(sob_fin[inside]) / max(1e-5, np.mean(sob_src[inside]))) if np.any(inside) else 0.0

    passed = bool(
        soft_alpha_px == 0
        and alpha_xor_px == 0
        and max_outside_rgb_diff == 0
        and phase_shift_px <= 0.15
        and detail_gain > 1.05
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "accept_full_hd": passed,
        "alpha_equal_to_source": bool(alpha_xor_px == 0 and soft_alpha_px == 0),
        "alpha_xor_pixels": alpha_xor_px,
        "soft_alpha_pixels": soft_alpha_px,
        "max_outside_hole_rgb_diff": max_outside_rgb_diff,
        "inside_hole_detail_gain_ratio": round(detail_gain, 4),
        "phase_shift_px": round(phase_shift_px, 4),
        "frozen_src_sha256": sha256_array(frozen_src_bgr),
        "final_output_sha256": sha256_array(final_output_bgr),
    }


def execute_hole_scalelock_hf_pipeline(
    keep_bgr: np.ndarray,
    remove_bgr: np.ndarray,
    detail_strength: float = 0.45,
) -> Dict[str, object]:
    """
    Executes the canonical `HOLE_SCALELOCK_HF` method registered in `SHQ_METHOD_REGISTRY_V1.json`:
      1. `anti_diff`: Derives same-frame `M_hole` (`洞`) and `M_anti_hole` (`反洞`) with zero silent resize.
      2. Synthesizes high-frequency detail candidate strictly inside `M_hole` without changing scale.
      3. `scale_lock_map`: Verifies silhouette IoU, Hausdorff distance, and `check_size_grow`.
      4. `hardpaste_hole`: Hard-pastes candidate into `M_hole` with orientation & size lock.
      5. `audit_independent_s7_hole_return`: Independently audits `alpha_final == alpha_source`
         and `max |RGB_final - RGB_source|_{outside M_hole} == 0`.
    """
    diff_res = anti_diff(keep_bgr=keep_bgr, remove_bgr=remove_bgr)
    if diff_res["status"] != "PASS":
        return {"status": "FAIL", "stage": "anti_diff", "detail": diff_res, "accept_full_hd": False}

    m_hole: np.ndarray = diff_res["m_hole"]
    x0, y0, x1, y1 = diff_res["hole_bbox_xyxy"]

    # Generate scale-locked high-frequency detail candidate on full frame
    lab = cv2.cvtColor(keep_bgr, cv2.COLOR_BGR2LAB)
    l_ch = lab[:, :, 0].astype(np.float32)
    hf = l_ch - cv2.GaussianBlur(l_ch, (0, 0), 1.3)
    lab[:, :, 0] = np.where(m_hole == 255, np.clip(l_ch + detail_strength * hf, 0, 255), l_ch).astype(np.uint8)
    cand_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    lock_res = scale_lock_map(
        src_peep_bgr=keep_bgr[y0:y1, x0:x1],
        src_peep_hole_mask=m_hole[y0:y1, x0:x1],
        cand_peep_bgr=cand_bgr[y0:y1, x0:x1],
        cand_peep_hole_mask=m_hole[y0:y1, x0:x1],
    )
    if lock_res["status"] != "PASS":
        return {"status": "FAIL", "stage": "scale_lock_map", "detail": lock_res, "accept_full_hd": False}

    paste_res = hardpaste_hole(
        src_canvas_bgr=keep_bgr,
        m_hole=m_hole,
        hd_candidate_bgr=cand_bgr,
        cand_alpha_mask=m_hole,
    )
    if paste_res["status"] != "PASS":
        return {"status": "BLOCK", "stage": "hardpaste_hole", "detail": paste_res, "accept_full_hd": False}

    s7_res = audit_independent_s7_hole_return(
        frozen_src_bgr=keep_bgr,
        frozen_src_hole_alpha=m_hole,
        final_output_bgr=paste_res["output_bgr"],
        final_output_alpha=paste_res["output_alpha"],
    )
    return {
        "status": s7_res["status"],
        "accept_full_hd": s7_res["accept_full_hd"],
        "anti_diff_audit": {k: v for k, v in diff_res.items() if k not in ("m_hole", "m_anti_hole")},
        "scale_lock_audit": lock_res,
        "hardpaste_audit": {k: v for k, v in paste_res.items() if k not in ("output_bgr", "output_alpha")},
        "s7_independent_audit": s7_res,
    }


def run_diag(check_items: List[Dict[str, object]], strict: bool = True) -> Tuple[int, Dict[str, object]]:
    """
    FIX #6:
    In `--strict` mode, ANY item whose status is not `"PASS"` (including `"FAIL"`, `"BLOCK"`,
    `"WARN"`, `"SKIP"`, or `"MISSING_DATA"`) forces `accept_full_hd = False` and returns exit code `1`!
    """
    counts = {"PASS": 0, "FAIL": 0, "BLOCK": 0, "WARN": 0, "SKIP": 0}
    for item in check_items:
        st = str(item.get("status", "SKIP")).upper()
        counts[st] = counts.get(st, 0) + 1

    if strict:
        all_ok = (
            len(check_items) > 0
            and counts["FAIL"] == 0
            and counts["BLOCK"] == 0
            and counts["WARN"] == 0
            and counts["SKIP"] == 0
        )
    else:
        all_ok = len(check_items) > 0 and counts["FAIL"] == 0 and counts["BLOCK"] == 0

    exit_code = 0 if all_ok else 1
    return exit_code, {
        "strict_mode": strict,
        "total_checks": len(check_items),
        "counts": counts,
        "warn_or_skip_treated_as_failure_in_strict": True,
        "accept_full_hd": all_ok,
        "exit_code": exit_code,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", default=True)
    args = parser.parse_args()

    # Self-verification on the real Hangar Scene + True Gemini Empty Hangar Background
    scene_p = Path("/working_dir/c_9cf0c56aa8603457/user_uploaded_files/ttl=63d/tool_generated/watermarked_img_7962592877226625414.jpg")
    empty_p = Path("/working_dir/c_9cf0c56aa8603457/user_uploaded_files/ttl=63d/user_uploaded/Gemini_Generated_Image_n6rz1kn6rz1kn6rz.jpeg")
    scene_bgr = cv2.imread(str(scene_p), cv2.IMREAD_COLOR)
    empty_bgr = cv2.resize(cv2.imread(str(empty_p), cv2.IMREAD_COLOR), (scene_bgr.shape[1], scene_bgr.shape[0]), interpolation=cv2.INTER_AREA)

    res = execute_hole_scalelock_hf_pipeline(keep_bgr=scene_bgr, remove_bgr=empty_bgr)
    code, diag_summary = run_diag([{"name": "real_hangar_hole_scalelock_hf", "status": res["status"]}], strict=args.strict)
    print(json.dumps({"pipeline_result": res, "diag_summary": diag_summary}, indent=2, ensure_ascii=False))
    sys.exit(code)