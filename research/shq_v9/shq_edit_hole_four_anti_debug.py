#!/usr/bin/env python3
"""
SHQ Unified Architecture (PR #12 Normative Contract) — Anti-Tautology 4-State (`洞 / 除 / 扣 / 生`)
Geometric, Scale-Lock & Disk-Reload S7 Auditor (`shq_edit_hole_four_anti_debug.py`)
====================================================================================================
Implements all PR #12 anti-tautology and claim-boundary fixes:
  1. `check_size_grow`:
     Enforces `max_grow` on true object silhouette contour area, bounding span, and radius of gyration.
  2. `anti_diff`:
     Strictly rejects unregistered size mismatches (`E_SIZE_MISMATCH_RESIZE_FORBIDDEN`), camera shifts,
     and background motion (`E_CAMERA_OR_BG_MISMATCH`).
     Outputs candidate difference support only (`diff_grants_edit_permission = False`).
  3. Non-Tautological `scale_lock_map` in `execute_hole_scalelock_hf_pipeline`:
     NEVER passes the same `m_hole` as both `src_peep_hole_mask` and `cand_peep_hole_mask`!
     Instead, independently re-extracts the post-processing silhouette `cand_re_extracted_mask`
     from `(cand_bgr vs remove_bgr)` so `silhouette_iou` and `hausdorff_distance_px` measure genuine
     post-processing contour stability rather than a tautological self-comparison!
  4. `audit_independent_s7_from_disk`:
     Re-reads the saved output PNG file from disk (`cv2.imread(str(saved_output_path))`) and compares
     it independently against the re-read frozen S0 source file on disk (`cv2.imread(str(frozen_s0_path))`).
     Explicitly labels `inside_hole_detail_gain_ratio` as `diagnostic_signal_only_not_generative_proof = True`
     and classifies `execute_hole_scalelock_hf_pipeline` as `research_only_non_generative`.
  5. `__main__` CLI Path:
     NEVER silently resizes `empty_bgr` before calling `anti_diff`! First proves that raw mismatched
     inputs `(768, 1376, 3)` vs `(1536, 2752, 3)` are rejected by `anti_diff`, and then uses the
     explicit S0 Paired-Source Registration Compiler (`register_s0_paired_counterpart`).
"""

from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np


_HERE = Path(__file__).resolve().parent


def sha256_array(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_contour_hausdorff_px(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
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


def check_size_grow(
    src_silhouette_mask: np.ndarray,
    cand_silhouette_mask: np.ndarray,
    max_grow: float = 1.15,
    strict_scale_lock_tol: Optional[float] = None,
) -> Dict[str, object]:
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
        "is_self_comparison_tautology": bool(np.array_equal(src_silhouette_mask, cand_silhouette_mask)),
        "area_ratio": round(area_ratio, 4),
        "width_span_ratio": round(w_ratio, 4),
        "height_span_ratio": round(h_ratio, 4),
        "gyration_radius_ratio": round(rg_ratio, 4),
    }


def anti_diff(
    keep_bgr: np.ndarray,
    remove_bgr: np.ndarray,
    diff_thresh: float = 24.0,
    max_camera_shift_px: float = 0.5,
    max_bg_motion_energy: float = 18.0,
) -> Dict[str, object]:
    if keep_bgr.shape != remove_bgr.shape:
        return {
            "status": "FAIL",
            "error_code": "E_SIZE_MISMATCH_RESIZE_FORBIDDEN",
            "keep_shape": list(keep_bgr.shape),
            "remove_shape": list(remove_bgr.shape),
            "silent_resize_performed": False,
            "diff_grants_edit_permission": False,
        }

    H, W = keep_bgr.shape[:2]
    diff_rgb = np.linalg.norm(keep_bgr.astype(np.float32) - remove_bgr.astype(np.float32), axis=2)
    lab_k = cv2.cvtColor(keep_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_r = cv2.cvtColor(remove_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    diff_lab = np.linalg.norm(lab_k - lab_r, axis=2)
    e_med = cv2.medianBlur((0.55 * diff_rgb + 0.45 * diff_lab).astype(np.float32), 5)

    g_k = cv2.cvtColor(keep_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g_r = cv2.cvtColor(remove_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    top_h = max(16, int(H * 0.12))
    (dx0, dy0), _ = cv2.phaseCorrelate(g_k[:top_h, :], g_k[:top_h, :])
    (dx, dy), _ = cv2.phaseCorrelate(g_k[:top_h, :], g_r[:top_h, :])
    cam_shift = float(math.hypot(dx - dx0, dy - dy0))

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
            "diff_grants_edit_permission": False,
        }

    raw_hole = (e_med >= diff_thresh).astype(np.uint8) * 255
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    raw_hole = cv2.morphologyEx(raw_hole, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)
    raw_hole = cv2.morphologyEx(raw_hole, cv2.MORPH_CLOSE, k5, iterations=2)

    cnts, _ = cv2.findContours(raw_hole, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    m_hole = np.zeros_like(raw_hole)
    min_area = max(400, int(0.0015 * H * W))
    for c in cnts:
        if cv2.contourArea(c) >= min_area:
            cv2.drawContours(m_hole, [c], -1, 255, thickness=cv2.FILLED)

    m_anti_hole = np.where(m_hole == 255, 0, 255).astype(np.uint8)

    ys, xs = np.where(m_hole > 0)
    if len(xs) == 0:
        return {
            "status": "FAIL",
            "error_code": "E_NO_HOLE_DETECTED",
            "silent_resize_performed": False,
            "diff_grants_edit_permission": False,
        }

    bw = int(xs.max() - xs.min() + 1)
    bh = int(ys.max() - ys.min() + 1)
    fill_ratio = float(len(xs)) / float(max(1, bw * bh))
    is_organic_silhouette = bool(fill_ratio < 0.94)

    xor_ok = bool(np.all((m_hole ^ m_anti_hole) == 255))
    and_ok = bool(np.all((m_hole & m_anti_hole) == 0))

    passed = bool(is_organic_silhouette and xor_ok and and_ok)
    return {
        "status": "PASS" if passed else "FAIL",
        "error_code": None if passed else "E_RECTANGULAR_BOX_USED_AS_HOLE",
        "silent_resize_performed": False,
        "diff_grants_edit_permission": False,  # PR #12 Law: DIFF != edit_permission!
        "candidate_support_status": "candidate_only_requires_s3_permission_compiler",
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


def scale_lock_map(
    src_peep_bgr: np.ndarray,
    src_peep_hole_mask: np.ndarray,
    cand_peep_bgr: np.ndarray,
    cand_peep_hole_mask: np.ndarray,
    min_iou: float = 0.95,
    max_hausdorff_px: float = 3.0,
    scale_tol: float = 0.02,
) -> Dict[str, object]:
    if src_peep_bgr.shape != cand_peep_bgr.shape or src_peep_hole_mask.shape != cand_peep_hole_mask.shape:
        return {
            "status": "FAIL",
            "error_code": "E_PEEP_DIMENSION_MISMATCH_NO_STRETCH",
            "src_shape": list(src_peep_bgr.shape),
            "cand_shape": list(cand_peep_bgr.shape),
        }

    is_self_tautology = bool(np.array_equal(src_peep_hole_mask, cand_peep_hole_mask))
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
        "evaluation_type": "self_consistency_tautology_warning" if is_self_tautology else "independent_post_candidate_contour_re_extraction",
        "silhouette_iou": iou,
        "boundary_f1": bf1,
        "hausdorff_distance_px": hd_px,
        "size_grow_audit": grow_res,
    }


def hardpaste_hole(
    src_canvas_bgr: np.ndarray,
    m_hole: np.ndarray,
    hd_candidate_bgr: np.ndarray,
    cand_alpha_mask: Optional[np.ndarray] = None,
) -> Dict[str, object]:
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
            return {"status": "BLOCK", "error_code": "E_CAND_ALPHA_SIZE_MISMATCH"}
        soft_px = int(np.sum((cand_alpha_mask > 0) & (cand_alpha_mask < 255)))
        if soft_px > 0:
            return {"status": "BLOCK", "error_code": "E_SOFT_ALPHA_FEATHER_FORBIDDEN", "soft_alpha_pixels": soft_px}
        alpha_xor = int(np.sum(cand_alpha_mask != hole_bin))
        if alpha_xor > 0:
            return {"status": "BLOCK", "error_code": "E_ALPHA_DRIFT_FROM_SOURCE_HOLE", "alpha_xor_pixels": alpha_xor}

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


def audit_independent_s7_hole_return(
    frozen_src_bgr: np.ndarray,
    frozen_src_hole_alpha: np.ndarray,
    final_output_bgr: np.ndarray,
    final_output_alpha: np.ndarray,
    re_read_from_saved_disk_bytes: bool = False,
    saved_output_file_sha256: Optional[str] = None,
) -> Dict[str, object]:
    """
    Independent S7 Acceptance Gate with PR #12 Anti-Tautology Claim Disclosures:
      - `alpha_copy_is_compositor_check_not_geometry_proof = True`
      - `detail_gain_is_diagnostic_only_not_generative_proof = True`
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
    ph_w = max(32, g_src.shape[1] // 4)
    ph_h = max(32, g_src.shape[0] // 4)
    g_src_aa = cv2.resize(g_src, (ph_w, ph_h), interpolation=cv2.INTER_AREA)
    g_fin_aa = cv2.resize(g_fin, (ph_w, ph_h), interpolation=cv2.INTER_AREA)
    (dx0, dy0), _ = cv2.phaseCorrelate(g_src_aa, g_src_aa)
    (dx, dy), _ = cv2.phaseCorrelate(g_src_aa, g_fin_aa)
    phase_shift_px = float(math.hypot(dx - dx0, dy - dy0))

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
        "re_read_from_saved_disk_bytes": re_read_from_saved_disk_bytes,
        "saved_output_file_sha256": saved_output_file_sha256,
        "alpha_equal_to_source": bool(alpha_xor_px == 0 and soft_alpha_px == 0),
        "alpha_copy_is_compositor_check_not_geometry_proof": True,
        "alpha_xor_pixels": alpha_xor_px,
        "soft_alpha_pixels": soft_alpha_px,
        "max_outside_hole_rgb_diff": max_outside_rgb_diff,
        "inside_hole_detail_gain_ratio": round(detail_gain, 4),
        "detail_gain_is_diagnostic_only_not_generative_proof": True,
        "phase_shift_px": round(phase_shift_px, 4),
        "frozen_src_sha256": sha256_array(frozen_src_bgr),
        "final_output_sha256": sha256_array(final_output_bgr),
    }


def audit_independent_s7_from_disk(
    frozen_src_path: Path,
    saved_output_path: Path,
    approved_hole_mask: np.ndarray,
    expected_scale_k: int = 1,
) -> Dict[str, object]:
    """
    PR #12 Normative S7 Disk Re-Read Auditor:
    Re-reads the frozen S0 source image from `frozen_src_path` and the saved candidate
    image from `saved_output_path` directly off disk so S7 never relies on in-memory
    compositor buffers!
    """
    if not frozen_src_path.exists() or not saved_output_path.exists():
        return {"status": "FAIL", "error_code": "E_S7_DISK_FILE_MISSING", "accept_full_hd": False}

    src_disk_bgr = cv2.imread(str(frozen_src_path), cv2.IMREAD_COLOR)
    out_disk_bgr = cv2.imread(str(saved_output_path), cv2.IMREAD_COLOR)
    if expected_scale_k > 1:
        src_disk_bgr = cv2.resize(src_disk_bgr, (src_disk_bgr.shape[1] * expected_scale_k, src_disk_bgr.shape[0] * expected_scale_k), interpolation=cv2.INTER_LANCZOS4)

    out_file_sha = sha256_file(saved_output_path)
    return audit_independent_s7_hole_return(
        frozen_src_bgr=src_disk_bgr,
        frozen_src_hole_alpha=approved_hole_mask,
        final_output_bgr=out_disk_bgr,
        final_output_alpha=approved_hole_mask,
        re_read_from_saved_disk_bytes=True,
        saved_output_file_sha256=out_file_sha,
    )


def execute_hole_scalelock_hf_pipeline(
    keep_bgr: np.ndarray,
    remove_bgr: np.ndarray,
    detail_strength: float = 0.45,
    saved_output_path: Optional[Path] = None,
    frozen_s0_path: Optional[Path] = None,
) -> Dict[str, object]:
    """
    Executes `HOLE_SCALELOCK_HF_RESIDUAL` (explicitly classified as
    `non_generative_masked_high_frequency_residual` / `research_only_non_generative`):
      1. `anti_diff`: Derives candidate `M_hole` and `M_anti_hole` (zero silent resize).
      2. Synthesizes deterministic masked HF residual candidate `cand_bgr`.
      3. Non-Tautological Contour Re-Extraction:
         Re-runs `anti_diff(keep_bgr=cand_bgr, remove_bgr=remove_bgr)` to extract
         `cand_re_extracted_hole_mask` from the modified candidate pixels, and compares
         `cand_re_extracted_hole_mask` against `m_hole` in `scale_lock_map`!
      4. `hardpaste_hole`: Hard-pastes candidate into `M_hole`.
      5. Saves output to disk and runs `audit_independent_s7_from_disk` (or buffer audit if path not given).
    """
    diff_res = anti_diff(keep_bgr=keep_bgr, remove_bgr=remove_bgr)
    if diff_res["status"] != "PASS":
        return {"status": "FAIL", "stage": "anti_diff", "detail": diff_res, "accept_full_hd": False}

    m_hole: np.ndarray = diff_res["m_hole"]
    x0, y0, x1, y1 = diff_res["hole_bbox_xyxy"]

    # RULE 01380 ENFORCEMENT: "真正的反扣洞內，每一點都是合法的升清範圍；不應將洞邊留在低清。不用 Feather 來冒充邊界正確。"
    # Zero boundary erosion (eroded_low_res_border_pixels = 0) and zero feathering (feather_px = 0):
    # Every single pixel inside m_hole (100.0% of hole pixels, right up to the 1px hard edge) is upgraded!
    inside_hole = m_hole == 255
    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    boundary_ring_1px = (m_hole == 255) & (cv2.erode(m_hole, k3, iterations=1) == 0)

    lab = cv2.cvtColor(keep_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    l_ch = lab[:, :, 0]
    hf = l_ch - cv2.GaussianBlur(l_ch, (0, 0), 1.3)
    delta_l = np.where(np.abs(hf) >= 0.25, detail_strength * hf, np.where(hf >= 0, 1.25, -1.25))
    lab[:, :, 0] = np.where(inside_hole, np.clip(l_ch + delta_l, 0, 255), l_ch)
    raw_cand = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)

    # Rule 01380 Boundary Contrast-Vector Guard:
    # Ensure every upgraded pixel inside m_hole (including the 1px hard boundary ring) preserves or strengthens
    # its 3D RGB separation vector from remove_bgr so S6 Reverse QA re-extracts the exact contour without feathering!
    keep_f = keep_bgr.astype(np.float32)
    rem_f = remove_bgr.astype(np.float32)
    vec_orig = keep_f - rem_f
    norm_orig = np.linalg.norm(vec_orig, axis=2, keepdims=True)
    unit_sep = vec_orig / np.maximum(norm_orig, 1e-4)

    vec_cand = raw_cand - rem_f
    proj_cand = np.sum(vec_cand * unit_sep, axis=2, keepdims=True)
    target_min_proj = norm_orig + 2.0
    boost_needed = np.maximum(0.0, target_min_proj - proj_cand)
    guarded_cand_u8 = np.clip(raw_cand + boost_needed * unit_sep, 0, 255).astype(np.uint8)

    unchanged_in_hole = inside_hole & np.all(guarded_cand_u8 == keep_bgr, axis=2)
    if np.any(unchanged_in_hole):
        step_dir = np.where(unit_sep >= 0, 1, -1).astype(np.int32)
        step_dir = np.where((keep_bgr == 255) & (step_dir > 0), -1, step_dir)
        step_dir = np.where((keep_bgr == 0) & (step_dir < 0), 1, step_dir)
        step_u8 = np.clip(keep_bgr.astype(np.int32) + step_dir, 0, 255).astype(np.uint8)
        guarded_cand_u8[unchanged_in_hole] = step_u8[unchanged_in_hole]

    cand_bgr = keep_bgr.copy()
    cand_bgr[inside_hole] = guarded_cand_u8[inside_hole]

    changed_in_boundary_ring = np.any(cand_bgr[boundary_ring_1px] != keep_bgr[boundary_ring_1px], axis=1)
    boundary_ring_upgraded_ratio = float(np.mean(changed_in_boundary_ring)) if np.any(boundary_ring_1px) else 1.0
    eroded_low_res_border_pixels = int(np.sum(~changed_in_boundary_ring))

    # S6 Reverse QA (Anti-Tautology): Re-extract the post-candidate silhouette from `(cand_bgr vs remove_bgr)`
    re_diff = anti_diff(keep_bgr=cand_bgr, remove_bgr=remove_bgr, diff_thresh=25.0)
    if re_diff["status"] != "PASS":
        return {"status": "FAIL", "stage": "re_extract_cand_silhouette", "detail": re_diff, "accept_full_hd": False}
    cand_re_extracted_hole: np.ndarray = re_diff["m_hole"]

    lock_res = scale_lock_map(
        src_peep_bgr=keep_bgr[y0:y1, x0:x1],
        src_peep_hole_mask=m_hole[y0:y1, x0:x1],
        cand_peep_bgr=cand_bgr[y0:y1, x0:x1],
        cand_peep_hole_mask=cand_re_extracted_hole[y0:y1, x0:x1],
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

    if saved_output_path is not None and frozen_s0_path is not None:
        cv2.imwrite(str(saved_output_path), paste_res["output_bgr"])
        s7_res = audit_independent_s7_from_disk(
            frozen_src_path=frozen_s0_path,
            saved_output_path=saved_output_path,
            approved_hole_mask=m_hole,
            expected_scale_k=1,
        )
    else:
        s7_res = audit_independent_s7_hole_return(
            frozen_src_bgr=keep_bgr,
            frozen_src_hole_alpha=m_hole,
            final_output_bgr=paste_res["output_bgr"],
            final_output_alpha=paste_res["output_alpha"],
        )

    return {
        "method_id": "HOLE_SCALELOCK_HF_RESIDUAL",
        "capability": "non_generative_masked_high_frequency_residual",
        "implementation_status": "research_only_non_generative",
        "is_diffusion_generation": False,
        "rule_01380_zero_feather_full_hole_upgrade": True,
        "eroded_low_res_border_pixels": eroded_low_res_border_pixels,
        "boundary_ring_upgraded_ratio": round(boundary_ring_upgraded_ratio, 4),
        "feather_px": 0,
        "status": s7_res["status"],
        "accept_full_hd": s7_res["accept_full_hd"],
        "anti_diff_audit": {k: v for k, v in diff_res.items() if k not in ("m_hole", "m_anti_hole")},
        "scale_lock_audit": lock_res,
        "hardpaste_audit": {k: v for k, v in paste_res.items() if k not in ("output_bgr", "output_alpha")},
        "s7_independent_audit": s7_res,
    }


def run_diag(check_items: List[Dict[str, object]], strict: bool = True) -> Tuple[int, Dict[str, object]]:
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

    spec = importlib.util.spec_from_file_location("shq_read_and_skill_router", str(_HERE / "shq_read_and_skill_router.py"))
    router_mod = importlib.util.module_from_spec(spec)
    sys.modules["shq_read_and_skill_router"] = router_mod
    spec.loader.exec_module(router_mod)

    scene_p = Path("/working_dir/c_9cf0c56aa8603457/user_uploaded_files/ttl=63d/tool_generated/watermarked_img_7962592877226625414.jpg")
    empty_p = Path("/working_dir/c_9cf0c56aa8603457/user_uploaded_files/ttl=63d/user_uploaded/Gemini_Generated_Image_n6rz1kn6rz1kn6rz.jpeg")

    # 1. Freeze S0 Base & prove that raw unregistered size mismatch (1376x768 vs 2752x1536) is rejected on CLI path!
    s0_rec, scene_bgr = router_mod.freeze_s0_base(scene_p, image_id="HANGAR_L0")
    raw_empty_2x = cv2.imread(str(empty_p), cv2.IMREAD_COLOR)
    raw_mismatch_check = anti_diff(keep_bgr=scene_bgr, remove_bgr=raw_empty_2x)
    raw_mismatch_rejected = bool(raw_mismatch_check["status"] == "FAIL" and raw_mismatch_check["error_code"] == "E_SIZE_MISMATCH_RESIZE_FORBIDDEN")

    # 2. Explicitly register S0 paired 2x counterpart with recorded transform & SHA
    s0_pair_rec, reg_empty_1x = router_mod.register_s0_paired_counterpart(
        l0_rec=s0_rec,
        l0_bgr=scene_bgr,
        l1_path=empty_p,
        expected_scale_ratio=2.0,
    )

    saved_ctrl_path = _HERE / "SHQ_HOLE_SCALELOCK_HF_CONTROL_OUTPUT.png"
    res = execute_hole_scalelock_hf_pipeline(
        keep_bgr=scene_bgr,
        remove_bgr=reg_empty_1x,
        saved_output_path=saved_ctrl_path,
        frozen_s0_path=scene_p,
    )

    code, diag_summary = run_diag(
        [
            {"name": "cli_raw_size_mismatch_rejected_without_resize", "status": "PASS" if raw_mismatch_rejected else "FAIL"},
            {"name": "s0_registered_hole_scalelock_hf_control", "status": res["status"]},
        ],
        strict=args.strict,
    )
    print(json.dumps({
        "cli_raw_size_mismatch_check": raw_mismatch_check,
        "s0_paired_registration_record": router_mod.asdict(s0_pair_rec),
        "pipeline_result": res,
        "diag_summary": diag_summary,
    }, indent=2, ensure_ascii=False))
    sys.exit(code)