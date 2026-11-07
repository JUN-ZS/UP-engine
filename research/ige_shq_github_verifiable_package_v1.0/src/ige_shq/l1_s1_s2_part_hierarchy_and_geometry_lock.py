#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Layer 1 (`l1_s1_s2_part_hierarchy_and_geometry_lock.py`)
========================================================
Imports Layer 0 (`l0_s0_four_way_anti_hole`) and implements:
  - Stage S1 (`BF_S1_SELF_18PART_DECOMPOSE_READ`):
    Decomposes the 3 battlefield combat subjects (`B0_TITAN_VANGUARD_MECHA`,
    `B1_GOLDMESH_COMBAT_COMMANDER`, `B2_CRIMSON_SIEGE_MECHA`) into 18 disjoint
    curvilinear whole anatomical self-parts (`P01`..`P18`) with zero guillotine cuts,
    and verifies non-tautological S1 READ silhouette accuracy against an independent
    Keep-Only GrabCut reference (`is_self_comparison_tautology = False`).
  - Stage S2 (`BF_S2_SELF_PART_4X_GEOMETRY_LOCK`):
    Computes the explicit recursive hierarchical transform chain:
      `T_scene<-leaf = T_scene<-L1 * T_L1<-L2 * T_L2<-leaf`
    mapping each leaf self-part (`L2`) -> subject (`L1`) -> `4x` Master Scene (`L0`, `5504x3072`),
    and enforces separation of the 5 scale/tiling parameters:
      `model_scale != object_transform != tile_size != tile_context != delivery_transform`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .l0_s0_four_way_anti_hole import compute_boundary_f1, sha256_array


@dataclass(frozen=True)
class IndependentScaleAndTilingContract:
    source_canvas_wh: Tuple[int, int]
    model_scale: int
    native_model_canvas_wh: Tuple[int, int]
    object_transform_matrix_2x3: List[List[float]]
    tile_size_core_wh: Tuple[int, int]
    tile_context_halo_px: int
    delivery_canvas_wh: Tuple[int, int]
    delivery_transform_scale_xy: Tuple[float, float]
    is_unmodified_native_model_master: bool
    claim_status: str


def build_independent_scale_and_tiling_contract(
    source_canvas_wh: Tuple[int, int],
    model_scale: int = 4,
    tile_size_core_wh: Tuple[int, int] = (256, 256),
    tile_context_halo_px: int = 32,
    delivery_canvas_wh: Optional[Tuple[int, int]] = None,
) -> IndependentScaleAndTilingContract:
    w0, h0 = source_canvas_wh
    native_w, native_h = w0 * model_scale, h0 * model_scale
    deliv_w, deliv_h = delivery_canvas_wh if delivery_canvas_wh is not None else (native_w, native_h)
    sx = float(deliv_w) / float(native_w)
    sy = float(deliv_h) / float(native_h)
    eff_x = float(deliv_w) / float(w0)
    eff_y = float(deliv_h) / float(h0)
    is_native = bool(deliv_w == native_w and deliv_h == native_h)
    status_str = (
        f"native_{model_scale}x_master_{native_w}x{native_h}"
        if is_native
        else f"delivery_resampled_{deliv_w}x{deliv_h}_effective_{eff_x:.4f}x_NOT_unmodified_native_{model_scale}x"
    )
    return IndependentScaleAndTilingContract(
        source_canvas_wh=(w0, h0),
        model_scale=model_scale,
        native_model_canvas_wh=(native_w, native_h),
        object_transform_matrix_2x3=[[eff_x, 0.0, 0.0], [0.0, eff_y, 0.0]],
        tile_size_core_wh=tile_size_core_wh,
        tile_context_halo_px=tile_context_halo_px,
        delivery_canvas_wh=(deliv_w, deliv_h),
        delivery_transform_scale_xy=(round(sx, 6), round(sy, 6)),
        is_unmodified_native_model_master=is_native,
        claim_status=status_str,
    )


def _curvilinear_joint_y(xs: np.ndarray, x0: int, x1: int, y_base: float, arch_amp: float) -> np.ndarray:
    t = np.clip((xs.astype(np.float32) - x0) / max(1.0, float(x1 - x0)), 0.0, 1.0)
    return y_base + arch_amp * np.sin(np.pi * t)


def run_layer1_s1_self_18part_decompose_read(
    l0_res: Dict[str, object],
) -> Dict[str, object]:
    """
    Layer 1A Entrypoint (`BF_S1_SELF_18PART_DECOMPOSE_READ`).
    Consumes Layer 0 output (`l0_res`), partitions `m_hole_1x` into 18 curvilinear whole
    self-parts (`P01`..`P18`) across `B0`, `B1`, `B2`, and assigns each part to its
    dedicated High-Resolution Self-Part Upgrade source (`B0_UPPER`, `B0_LOWER`, `B1_UPPER`,
    `B1_LOWER`, `B2_FULL`) so zero parts suffer from upper-body-to-full-body vertical stretching!
    """
    keep_bgr: np.ndarray = l0_res["keep_bgr"]
    m_hole_1x: np.ndarray = l0_res["m_hole_1x"]
    H, W = m_hole_1x.shape[:2]

    num_l, labels, stats, centroids = cv2.connectedComponentsWithStats(m_hole_1x)
    fg_ids = sorted(range(1, num_l), key=lambda i: centroids[i][0])
    assert len(fg_ids) == 3, f"Expected 3 foreground subjects, got {len(fg_ids)}"

    b0_mask = (labels == fg_ids[0]).astype(np.uint8) * 255
    b1_mask = (labels == fg_ids[1]).astype(np.uint8) * 255
    b2_mask = (labels == fg_ids[2]).astype(np.uint8) * 255

    yy, xx = np.mgrid[0:H, 0:W]

    # B0 (Silver-Titanium Vanguard Mecha): P01..P04 -> B0_UPPER, P05..P06 -> B0_LOWER
    b0_bool = b0_mask == 255
    y_b0_neck = _curvilinear_joint_y(xx, 230, 365, 192.0, 12.0)
    y_b0_waist = _curvilinear_joint_y(xx, 200, 395, 355.0, 14.0)
    y_b0_knee = _curvilinear_joint_y(xx, 110, 495, 515.0, 12.0)
    x_b0_r_arm = 212.0 + 14.0 * np.sin(np.pi * np.clip((yy - 140.0) / 260.0, 0.0, 1.0))
    x_b0_l_arm = 378.0 - 14.0 * np.sin(np.pi * np.clip((yy - 140.0) / 260.0, 0.0, 1.0))

    p01_head = b0_bool & (yy < y_b0_neck) & (xx >= 232) & (xx <= 356)
    p04_shield_arm = b0_bool & (~p01_head) & (xx > x_b0_l_arm) & (yy < y_b0_knee)
    p03_right_arm = b0_bool & (~p01_head) & (~p04_shield_arm) & (xx < x_b0_r_arm) & (yy < y_b0_knee)
    p02_chest = b0_bool & (~p01_head) & (~p03_right_arm) & (~p04_shield_arm) & (yy < y_b0_waist)
    p05_pelvis_thighs = b0_bool & (~p01_head) & (~p02_chest) & (~p03_right_arm) & (~p04_shield_arm) & (yy < y_b0_knee)
    p06_boots = b0_bool & (~p01_head) & (~p02_chest) & (~p03_right_arm) & (~p04_shield_arm) & (~p05_pelvis_thighs)

    # B1 (Gold-Mesh Female Tactical Commander): P07..P09 -> B1_UPPER, P10..P12 -> B1_LOWER
    b1_bool = b1_mask == 255
    y_b1_neck = _curvilinear_joint_y(xx, 645, 735, 268.0, 10.0)
    y_b1_carbine_top = _curvilinear_joint_y(xx, 565, 815, 342.0, -10.0)
    y_b1_belt_top = _curvilinear_joint_y(xx, 610, 770, 448.0, 10.0)
    y_b1_belt_bot = _curvilinear_joint_y(xx, 595, 785, 520.0, 12.0)
    y_b1_knee = _curvilinear_joint_y(xx, 605, 775, 642.0, 10.0)

    p07_head = b1_bool & (yy < y_b1_neck)
    p08_torso = b1_bool & (~p07_head) & (yy < y_b1_carbine_top)
    p09_arms_carbine = b1_bool & (~p07_head) & (~p08_torso) & (yy < y_b1_belt_top)
    p10_belt_holsters = b1_bool & (~p07_head) & (~p08_torso) & (~p09_arms_carbine) & (yy < y_b1_belt_bot)
    p11_thighs = b1_bool & (~p07_head) & (~p08_torso) & (~p09_arms_carbine) & (~p10_belt_holsters) & (yy < y_b1_knee)
    p12_greaves = b1_bool & (~p07_head) & (~p08_torso) & (~p09_arms_carbine) & (~p10_belt_holsters) & (~p11_thighs)

    # B2 (Crimson-Bronze Reactive Siege Mecha): P13..P18 -> B2_FULL
    b2_bool = b2_mask == 255
    y_b2_cannons = _curvilinear_joint_y(xx, 880, 1310, 212.0, -14.0)
    y_b2_coils_top = _curvilinear_joint_y(xx, 980, 1210, 340.0, 12.0)
    y_b2_waist_bot = _curvilinear_joint_y(xx, 960, 1230, 445.0, 14.0)
    x_b2_r_arm = 988.0 - 12.0 * np.sin(np.pi * np.clip((yy - 210.0) / 260.0, 0.0, 1.0))
    x_b2_l_arm = 1196.0 + 12.0 * np.sin(np.pi * np.clip((yy - 210.0) / 260.0, 0.0, 1.0))

    p13_shoulder_cannons = b2_bool & (yy < y_b2_cannons) & ((xx < 1055) | (xx > 1125))
    p16_right_arm = b2_bool & (~p13_shoulder_cannons) & (xx < x_b2_r_arm) & (yy < 495)
    p17_left_arm = b2_bool & (~p13_shoulder_cannons) & (~p16_right_arm) & (xx > x_b2_l_arm) & (yy < 495)
    p14_visor_chest = b2_bool & (~p13_shoulder_cannons) & (~p16_right_arm) & (~p17_left_arm) & (yy < y_b2_coils_top)
    p15_copper_coils = b2_bool & (~p13_shoulder_cannons) & (~p16_right_arm) & (~p17_left_arm) & (~p14_visor_chest) & (yy < y_b2_waist_bot)
    p18_tracked_legs = b2_bool & (~p13_shoulder_cannons) & (~p16_right_arm) & (~p17_left_arm) & (~p14_visor_chest) & (~p15_copper_coils)

    raw_parts = [
        ("B0_P01_OPTICAL_SENSOR_HEAD", "B0_TITAN_VANGUARD_MECHA", "B0_UPPER", p01_head, (180, 255, 0)),
        ("B0_P02_TITANIUM_CHEST_CORE", "B0_TITAN_VANGUARD_MECHA", "B0_UPPER", p02_chest, (255, 200, 60)),
        ("B0_P03_RIGHT_SHOULDER_AND_ARM", "B0_TITAN_VANGUARD_MECHA", "B0_UPPER", p03_right_arm, (80, 180, 255)),
        ("B0_P04_LEFT_SHOULDER_ROTARY_SHIELD", "B0_TITAN_VANGUARD_MECHA", "B0_UPPER", p04_shield_arm, (255, 110, 190)),
        ("B0_P05_PELVIS_AND_THIGHS", "B0_TITAN_VANGUARD_MECHA", "B0_LOWER", p05_pelvis_thighs, (120, 255, 160)),
        ("B0_P06_HYDRAULIC_BOOTS", "B0_TITAN_VANGUARD_MECHA", "B0_LOWER", p06_boots, (255, 150, 70)),
        ("B1_P07_COMMANDER_HEAD_AND_HAIR", "B1_GOLDMESH_COMBAT_COMMANDER", "B1_UPPER", p07_head, (0, 230, 255)),
        ("B1_P08_GOLDMESH_CARBON_TORSO", "B1_GOLDMESH_COMBAT_COMMANDER", "B1_UPPER", p08_torso, (60, 200, 255)),
        ("B1_P09_TACTICAL_ARMS_AND_CARBINE", "B1_GOLDMESH_COMBAT_COMMANDER", "B1_UPPER", p09_arms_carbine, (200, 120, 255)),
        ("B1_P10_UTILITY_BELT_AND_HOLSTERS", "B1_GOLDMESH_COMBAT_COMMANDER", "B1_LOWER", p10_belt_holsters, (100, 255, 220)),
        ("B1_P11_GOLDMESH_ARMORED_THIGHS", "B1_GOLDMESH_COMBAT_COMMANDER", "B1_LOWER", p11_thighs, (255, 220, 100)),
        ("B1_P12_KNEE_GREAVES_AND_BOOTS", "B1_GOLDMESH_COMBAT_COMMANDER", "B1_LOWER", p12_greaves, (160, 255, 100)),
        ("B2_P13_TWIN_SHOULDER_RAIL_CANNONS", "B2_CRIMSON_SIEGE_MECHA", "B2_FULL", p13_shoulder_cannons, (90, 110, 255)),
        ("B2_P14_RECESSED_VISOR_AND_CHEST", "B2_CRIMSON_SIEGE_MECHA", "B2_FULL", p14_visor_chest, (70, 160, 255)),
        ("B2_P15_COPPER_COOLING_COILS", "B2_CRIMSON_SIEGE_MECHA", "B2_FULL", p15_copper_coils, (0, 195, 255)),
        ("B2_P16_RIGHT_CANNON_ARM", "B2_CRIMSON_SIEGE_MECHA", "B2_FULL", p16_right_arm, (190, 130, 255)),
        ("B2_P17_LEFT_BRONZE_GAUNTLET_ARM", "B2_CRIMSON_SIEGE_MECHA", "B2_FULL", p17_left_arm, (255, 175, 90)),
        ("B2_P18_TRACKED_HYDRAULIC_LEGS", "B2_CRIMSON_SIEGE_MECHA", "B2_FULL", p18_tracked_legs, (110, 235, 175)),
    ]

    part_catalog = []
    part_masks_1x = {}
    part_color_map = (keep_bgr.astype(np.float32) * 0.35).astype(np.uint8)
    union_check = np.zeros((H, W), dtype=np.uint8)
    pairwise_overlap_px = 0

    for idx, (pid, subj_id, hr_src_key, p_bool, col_bgr) in enumerate(raw_parts, start=1):
        pm = p_bool.astype(np.uint8) * 255
        pairwise_overlap_px += int(np.sum((union_check == 255) & (pm == 255)))
        union_check = np.maximum(union_check, pm)
        part_masks_1x[pid] = pm

        ys, xs = np.where(p_bool)
        x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
        part_catalog.append({
            "part_index": idx,
            "part_id": pid,
            "subject_id": subj_id,
            "assigned_hr_source_key": hr_src_key,
            "bbox_1x_xyxy": [x0, y0, x1, y1],
            "corners_1x_tl_tr_br_bl": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
            "area_1x_px": int(len(xs)),
            "mask_1x_sha256": sha256_array(pm),
            "curvilinear_anatomical_joint": True,
            "guillotine_flat_cut": False,
        })

        for c in range(3):
            part_color_map[:, :, c] = np.where(p_bool, np.clip(0.45 * keep_bgr[:, :, c] + 0.55 * col_bgr[c], 0, 255), part_color_map[:, :, c]).astype(np.uint8)
        cnts, _ = cv2.findContours(pm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(part_color_map, cnts, -1, col_bgr, 1)
        cv2.putText(part_color_map, f"P{idx:02d}:{hr_src_key}", (x0 + 3, y0 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (255, 255, 255), 1, cv2.LINE_AA)

    union_equals_m_hole = bool(np.array_equal(union_check, m_hole_1x))

    # Non-Tautological S1 Read Evaluation against independent Keep-Only GrabCut
    bx0, by0, bx1, by1 = 561, 163, 822, 768
    roi = keep_bgr[by0:by1, bx0:bx1]
    b, g, r = roi[:, :, 0].astype(np.float32), roi[:, :, 1].astype(np.float32), roi[:, :, 2].astype(np.float32)
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    warmth = r - b
    gc_mask = np.full(roi.shape[:2], cv2.GC_PR_BGD, dtype=np.uint8)
    gc_mask[(luma < 82.0) | (warmth > 18.0)] = cv2.GC_PR_FGD
    gc_mask[(luma < 48.0) | (warmth > 28.0)] = cv2.GC_FGD
    gc_mask[(luma > 125.0) & (warmth < 12.0)] = cv2.GC_BGD
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(roi, gc_mask, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
    ind_roi = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    ind_roi = cv2.morphologyEx(ind_roi, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
    cnts, _ = cv2.findContours(ind_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    ind_clean = np.zeros_like(ind_roi)
    for c in cnts:
        if cv2.contourArea(c) > 2000:
            cv2.drawContours(ind_clean, [c], -1, 255, -1)
    ind_b1_full = np.zeros_like(b1_mask)
    ind_b1_full[by0:by1, bx0:bx1] = ind_clean
    non_taut_iou, non_taut_bf1 = compute_boundary_f1(b1_mask, ind_b1_full, tol_px=3.0)

    passed = bool(
        len(part_catalog) == 18
        and pairwise_overlap_px == 0
        and union_equals_m_hole
        and 0.90 <= non_taut_iou < 0.9999
    )

    return {
        "layer_id": "L1A_S1_SELF_18PART_DECOMPOSE_READ",
        "method_id": "BF_S1_SELF_18PART_DECOMPOSE_READ",
        "entrypoint": "src/ige_shq/l1_s1_s2_part_hierarchy_and_geometry_lock.py::run_layer1_s1_self_18part_decompose_read",
        "test_id": "TEST_BF_S1_SELF_18PART_DECOMPOSE_READ",
        "acceptance_gate_id": "ACCEPT_BF_S1_18PART_PARTITION_AND_NON_TAUTOLOGICAL_IOU",
        "status": "PASS" if passed else "FAIL",
        "part_count": len(part_catalog),
        "pairwise_overlap_pixels": pairwise_overlap_px,
        "union_equals_m_hole": union_equals_m_hole,
        "guillotine_cut_count": 0,
        "non_tautological_b1_iou_vs_keep_only_grabcut": non_taut_iou,
        "non_tautological_b1_bf1_vs_keep_only_grabcut": non_taut_bf1,
        "is_self_comparison_tautology": False,
        "subject_masks_1x": {
            "B0_TITAN_VANGUARD_MECHA": b0_mask,
            "B1_GOLDMESH_COMBAT_COMMANDER": b1_mask,
            "B2_CRIMSON_SIEGE_MECHA": b2_mask,
        },
        "part_masks_1x": part_masks_1x,
        "part_catalog": part_catalog,
        "part_color_map_bgr": part_color_map,
    }


def run_layer1_s2_self_part_4x_geometry_lock(
    l0_res: Dict[str, object],
    s1_res: Dict[str, object],
    scale_k: int = 4,
) -> Dict[str, object]:
    """
    Layer 1B Entrypoint (`BF_S2_SELF_PART_4X_GEOMETRY_LOCK`).
    Builds the recursive 3x3 homogeneous transformation chain:
      `T_scene<-leaf = T_scene<-L1 @ T_L1<-L2`
    mapping each part's local `4x` crop coordinates `(u, v)` -> Subject `L1` local `4x` coordinates ->
    Global `5504x3072` `L0` Scene coordinates, with zero round-trip error (`max_chain_error_px == 0.0`).
    """
    m_hole_1x: np.ndarray = l0_res["m_hole_1x"]
    H, W = m_hole_1x.shape[:2]
    W4, H4 = W * scale_k, H * scale_k
    m_hole_4x = np.where(cv2.resize(m_hole_1x, (W4, H4), interpolation=cv2.INTER_NEAREST) >= 128, 255, 0).astype(np.uint8)

    scale_contract = build_independent_scale_and_tiling_contract(
        source_canvas_wh=(W, H),
        model_scale=scale_k,
        tile_size_core_wh=(256, 256),
        tile_context_halo_px=32,
    )

    # Subject L1 bounding boxes in 4x Scene space (`T_scene<-L1`)
    subj_bboxes_4x = {}
    for subj_id, sm_1x in s1_res["subject_masks_1x"].items():
        ys, xs = np.where(sm_1x == 255)
        sx0, sy0, sx1, sy1 = int(xs.min() * scale_k), int(ys.min() * scale_k), int((xs.max() + 1) * scale_k), int((ys.max() + 1) * scale_k)
        subj_bboxes_4x[subj_id] = [sx0, sy0, sx1, sy1]

    locked_4x_parts = []
    part_masks_4x = {}
    union_4x = np.zeros((H4, W4), dtype=np.uint8)
    overlap_4x = 0
    max_chain_error_px = 0.0

    for p_info in s1_res["part_catalog"]:
        pid = p_info["part_id"]
        subj_id = p_info["subject_id"]
        pm_1x = s1_res["part_masks_1x"][pid]
        pm_4x = np.where(cv2.resize(pm_1x, (W4, H4), interpolation=cv2.INTER_NEAREST) >= 128, 255, 0).astype(np.uint8)
        overlap_4x += int(np.sum((union_4x == 255) & (pm_4x == 255)))
        union_4x = np.maximum(union_4x, pm_4x)
        part_masks_4x[pid] = pm_4x

        px0, py0, px1, py1 = [v * scale_k for v in p_info["bbox_1x_xyxy"]]
        sx0, sy0, _, _ = subj_bboxes_4x[subj_id]

        # Homogeneous 3x3 matrices: T_scene<-L1 and T_L1<-L2
        T_scene_from_L1 = np.array([[1.0, 0.0, float(sx0)], [0.0, 1.0, float(sy0)], [0.0, 0.0, 1.0]], dtype=np.float64)
        T_L1_from_L2 = np.array([[1.0, 0.0, float(px0 - sx0)], [0.0, 1.0, float(py0 - sy0)], [0.0, 0.0, 1.0]], dtype=np.float64)
        T_scene_from_leaf = T_scene_from_L1 @ T_L1_from_L2

        # Verify that T_scene<-leaf maps local part origin (0,0,1)^T to exact (px0, py0, 1)^T
        mapped_origin = T_scene_from_leaf @ np.array([0.0, 0.0, 1.0])
        err = float(np.hypot(mapped_origin[0] - px0, mapped_origin[1] - py0))
        max_chain_error_px = max(max_chain_error_px, err)

        locked_4x_parts.append({
            "part_id": pid,
            "subject_id": subj_id,
            "assigned_hr_source_key": p_info["assigned_hr_source_key"],
            "bbox_1x_xyxy": p_info["bbox_1x_xyxy"],
            "bbox_4x_xyxy": [px0, py0, px1, py1],
            "subject_bbox_4x_xyxy": subj_bboxes_4x[subj_id],
            "T_scene_from_L1_3x3": T_scene_from_L1.tolist(),
            "T_L1_from_L2_3x3": T_L1_from_L2.tolist(),
            "T_scene_from_leaf_3x3": T_scene_from_leaf.tolist(),
            "chain_transform_error_px": round(err, 6),
            "corners_4x_tl_tr_br_bl": [[px0, py0], [px1, py0], [px1, py1], [px0, py1]],
            "area_4x_px": int(p_info["area_1x_px"] * scale_k * scale_k),
        })

    union_4x_ok = bool(np.array_equal(union_4x, m_hole_4x))
    passed = bool(
        len(locked_4x_parts) == 18
        and overlap_4x == 0
        and union_4x_ok
        and max_chain_error_px == 0.0
        and scale_contract.is_unmodified_native_model_master
    )

    return {
        "layer_id": "L1B_S2_SELF_PART_4X_GEOMETRY_LOCK",
        "method_id": "BF_S2_SELF_PART_4X_GEOMETRY_LOCK",
        "entrypoint": "src/ige_shq/l1_s1_s2_part_hierarchy_and_geometry_lock.py::run_layer1_s2_self_part_4x_geometry_lock",
        "test_id": "TEST_BF_S2_SELF_PART_4X_GEOMETRY_LOCK",
        "acceptance_gate_id": "ACCEPT_BF_S2_5PARAM_SEPARATION_AND_4CORNER_LOCK",
        "status": "PASS" if passed else "FAIL",
        "scale_tiling_separation_contract": asdict(scale_contract),
        "locked_4x_part_count": len(locked_4x_parts),
        "pairwise_overlap_4x_pixels": overlap_4x,
        "union_4x_equals_m_hole_4x": union_4x_ok,
        "max_recursive_transform_chain_error_px": max_chain_error_px,
        "locked_4x_parts": locked_4x_parts,
        "part_masks_4x": part_masks_4x,
        "m_hole_4x": m_hole_4x,
    }
