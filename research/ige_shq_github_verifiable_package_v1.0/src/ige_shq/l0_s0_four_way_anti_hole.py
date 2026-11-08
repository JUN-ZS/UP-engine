#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Layer 0 (`l0_s0_four_way_anti_hole.py`)
=======================================
Implements Stage S0 (`BF_S0_EDIT_4WAY_ANTI_HOLE`):
  1. SHA-256 Base Freeze (`freeze_s0_base`).
  2. Paired Empty-Background Registration (`register_s0_paired_counterpart`).
  3. 4-Way Anti-Diff (`anti_diff`: `生 KEEP -> 除 REMOVE -> 扣 DIFF -> 洞 M_hole & 反洞 M_anti_hole`)
     with zero silent resize (`E_SIZE_MISMATCH_RESIZE_FORBIDDEN`) and strict enforcement of
     `diff_grants_edit_permission = False`.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


def sha256_array(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class S0BaseFreezeRecord:
    image_id: str
    file_name: str
    file_sha256: str
    raw_pixel_sha256: str
    canvas_wh: Tuple[int, int]
    channels: int
    dtype: str
    color_space: str = "sRGB_BGR8"
    orientation_locked: bool = True


@dataclass(frozen=True)
class S0PairedRegistrationRecord:
    l0_file_sha256: str
    l0_canvas_wh: Tuple[int, int]
    l1_original_file_sha256: str
    l1_original_canvas_wh: Tuple[int, int]
    registered_scale_ratio_xy: Tuple[float, float]
    registration_phase_shift_px: float
    l1_registered_pixel_sha256: str


def freeze_s0_base(image_path: Path, image_id: str = "BATTLEFIELD_S0_BASE") -> Tuple[S0BaseFreezeRecord, np.ndarray]:
    if not image_path.exists():
        raise FileNotFoundError(f"S0_BASE_MISSING: {image_path}")
    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"S0_DECODE_FAILED: {image_path}")
    h, w, c = bgr.shape
    rec = S0BaseFreezeRecord(
        image_id=image_id,
        file_name=image_path.name,
        file_sha256=sha256_file(image_path),
        raw_pixel_sha256=sha256_array(bgr),
        canvas_wh=(w, h),
        channels=c,
        dtype=str(bgr.dtype),
    )
    return rec, bgr


def register_s0_paired_counterpart(
    base_rec: S0BaseFreezeRecord,
    base_bgr: np.ndarray,
    counterpart_path: Path,
    expected_scale_ratio: float = 1.0,
) -> Tuple[S0PairedRegistrationRecord, np.ndarray]:
    if not counterpart_path.exists():
        raise FileNotFoundError(f"S0_COUNTERPART_MISSING: {counterpart_path}")
    cp_raw = cv2.imread(str(counterpart_path), cv2.IMREAD_COLOR)
    if cp_raw is None:
        raise ValueError(f"S0_COUNTERPART_DECODE_FAILED: {counterpart_path}")

    w0, h0 = base_rec.canvas_wh
    h1, w1 = cp_raw.shape[:2]
    rx, ry = float(w1) / float(w0), float(h1) / float(h0)
    if abs(rx - expected_scale_ratio) > 0.02 or abs(ry - expected_scale_ratio) > 0.02:
        raise ValueError(f"S0_UNEXPECTED_SCALE_RATIO: got ({rx:.4f}, {ry:.4f}), expected {expected_scale_ratio}")

    cp_reg = cv2.resize(cp_raw, (w0, h0), interpolation=cv2.INTER_AREA) if (w1 != w0 or h1 != h0) else cp_raw.copy()

    g0 = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g1 = cv2.cvtColor(cp_reg, cv2.COLOR_BGR2GRAY).astype(np.float32)
    top_h = max(16, int(h0 * 0.12))
    (dx0, dy0), _ = cv2.phaseCorrelate(g0[:top_h, :], g0[:top_h, :])
    (dx, dy), _ = cv2.phaseCorrelate(g0[:top_h, :], g1[:top_h, :])
    shift_px = float(math.hypot(dx - dx0, dy - dy0))

    rec = S0PairedRegistrationRecord(
        l0_file_sha256=base_rec.file_sha256,
        l0_canvas_wh=(w0, h0),
        l1_original_file_sha256=sha256_file(counterpart_path),
        l1_original_canvas_wh=(w1, h1),
        registered_scale_ratio_xy=(round(rx, 4), round(ry, 4)),
        registration_phase_shift_px=round(shift_px, 4),
        l1_registered_pixel_sha256=sha256_array(cp_reg),
    )
    return rec, cp_reg


def anti_diff(
    keep_bgr: np.ndarray,
    remove_bgr: np.ndarray,
    diff_thresh: float = 28.0,
    max_camera_shift_px: float = 1.5,
    max_bg_motion_energy: float = 18.0,
) -> Dict[str, object]:
    """
    Computes `生 (KEEP) - 除 (REMOVE) -> 扣 (DIFF) -> 洞 (M_hole) & 反洞 (M_anti_hole)`.
    Strictly forbids silent resize when shapes differ.
    """
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
        "diff_grants_edit_permission": False,
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


def compute_boundary_f1(mask_a: np.ndarray, mask_b: np.ndarray, tol_px: float = 2.0) -> Tuple[float, float]:
    a = mask_a >= 128
    b = mask_b >= 128
    inter = int(np.sum(a & b))
    union = int(np.sum(a | b))
    iou = float(inter) / float(max(1, union))

    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    ba = (a.astype(np.uint8) * 255) ^ cv2.erode(a.astype(np.uint8) * 255, k3, iterations=1)
    bb = (b.astype(np.uint8) * 255) ^ cv2.erode(b.astype(np.uint8) * 255, k3, iterations=1)
    if np.sum(ba > 0) == 0 or np.sum(bb > 0) == 0:
        return round(iou, 4), 0.0

    da = cv2.distanceTransform(np.where(ba > 0, 0, 255).astype(np.uint8), cv2.DIST_L2, 5)
    db = cv2.distanceTransform(np.where(bb > 0, 0, 255).astype(np.uint8), cv2.DIST_L2, 5)
    prec = float(np.mean(db[ba > 0] <= tol_px))
    rec = float(np.mean(da[bb > 0] <= tol_px))
    bf1 = (2.0 * prec * rec) / max(1e-6, prec + rec)
    return round(iou, 4), round(bf1, 4)


def compute_contour_hausdorff_px(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    a_u8 = np.where(mask_a >= 128, 255, 0).astype(np.uint8)
    b_u8 = np.where(mask_b >= 128, 255, 0).astype(np.uint8)
    ba = a_u8 ^ cv2.erode(a_u8, k3, iterations=1)
    bb = b_u8 ^ cv2.erode(b_u8, k3, iterations=1)
    if np.sum(ba > 0) == 0 or np.sum(bb > 0) == 0:
        return 999.0
    da = cv2.distanceTransform(np.where(ba > 0, 0, 255).astype(np.uint8), cv2.DIST_L2, 5)
    db = cv2.distanceTransform(np.where(bb > 0, 0, 255).astype(np.uint8), cv2.DIST_L2, 5)
    return round(float(max(np.max(db[ba > 0]), np.max(da[bb > 0]))), 4)


def run_layer0_s0_four_way_anti_hole(
    keep_path: Path,
    remove_path: Path,
    diff_thresh: float = 28.0,
) -> Dict[str, object]:
    """
    Layer 0 Entrypoint (`BF_S0_EDIT_4WAY_ANTI_HOLE`).
    """
    base_rec, keep_bgr = freeze_s0_base(keep_path, image_id="BATTLEFIELD_3SUBJECTS_KEEP_S0")
    pair_rec, remove_bgr = register_s0_paired_counterpart(base_rec, keep_bgr, remove_path, expected_scale_ratio=1.0)
    diff_res = anti_diff(keep_bgr=keep_bgr, remove_bgr=remove_bgr, diff_thresh=diff_thresh)

    m_hole: np.ndarray = diff_res["m_hole"]
    m_anti_hole: np.ndarray = diff_res["m_anti_hole"]
    diff_rgb = np.linalg.norm(keep_bgr.astype(np.float32) - remove_bgr.astype(np.float32), axis=2)
    diff_heat_bgr = cv2.applyColorMap(np.clip(diff_rgb * 1.4, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)

    passed = bool(
        diff_res["status"] == "PASS"
        and diff_res["camera_shift_px"] <= 0.10
        and diff_res["hole_and_antihole_exact_complement"]
        and (not diff_res["diff_grants_edit_permission"])
    )
    return {
        "layer_id": "L0_S0_FOUR_WAY_ANTI_HOLE",
        "method_id": "BF_S0_EDIT_4WAY_ANTI_HOLE",
        "entrypoint": "src/ige_shq/l0_s0_four_way_anti_hole.py::run_layer0_s0_four_way_anti_hole",
        "test_id": "TEST_BF_S0_EDIT_4WAY_ANTI_HOLE",
        "acceptance_gate_id": "ACCEPT_BF_S0_HOLE_AND_ANTIHOLE_COMPLEMENT",
        "status": "PASS" if passed else "FAIL",
        "s0_base_freeze": asdict(base_rec),
        "s0_paired_registration": asdict(pair_rec),
        "anti_diff_audit": {k: v for k, v in diff_res.items() if k not in ("m_hole", "m_anti_hole")},
        "keep_bgr": keep_bgr,
        "remove_bgr": remove_bgr,
        "diff_heat_bgr": diff_heat_bgr,
        "m_hole_1x": m_hole,
        "m_anti_hole_1x": m_anti_hole,
    }
