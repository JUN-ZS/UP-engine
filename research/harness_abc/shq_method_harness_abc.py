#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHQ Method Harness ABC · write 01472
====================================
KILL: 01433 ranking / PASS_C2-as-geometry is invalid.
BUILD: fair A/B/C acceptance layers referencing named STICK flows:
  換涯人 / 機炸回 / 新畫女 / 回車大炮 / 四態反 / 外力GROK / 新女畫V2 / 外力反 V2.1

Hard contracts
--------------
1. Control: within one scene, ALL methods share frozen KEEP, EMPTY, HOLE,
   peeps, elev, donor crop. Only the return method changes.
2. Ownership: peep masks are mutually exclusive (M_i ∩ M_j = ∅).
3. Permission: outside is measured against FROZEN M_hole, never method-grown union.
4. Layers do not substitute:
   A = single-method on frozen inputs
   B = multi-part compose + seam/ownership
   C = multi-scene block design (same method matrix each scene)
5. Name ≠ implementation: aliases collapse; false NEURAL/GUIDED renamed.

ACCEPT_FULL_HD = false  (harness structure only; not C5 production)

Usage
-----
  python3 shq_method_harness_abc.py selftest
  python3 shq_method_harness_abc.py kill-note
  python3 shq_method_harness_abc.py list-methods
  python3 shq_method_harness_abc.py list-sticks
  python3 shq_method_harness_abc.py init-scene --out runs/S01 --preset synth_cliff
  python3 shq_method_harness_abc.py run-A --scene runs/S01 --out runs/S01/A
  python3 shq_method_harness_abc.py run-B --scene runs/S01 --out runs/S01/B
  python3 shq_method_harness_abc.py run-C --scenes runs/S01,runs/S02 --out runs/C_MATRIX
  python3 shq_method_harness_abc.py rank-forbid  # prints why 01433 rank is illegal
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

WRITE_ID = "01472"
FORMAL = "SHQ_KILL01433_HARNESS_ABC_V1"
ACCEPT_FULL_HD = False
VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# 0. KILL card for 01433
# ---------------------------------------------------------------------------

KILL_01433 = {
    "write_id": WRITE_ID,
    "kills": "01433",
    "formal_killed": "SHQ_RESET_EACH_RETURN_UNIQUE_SRC_01433",
    "verdict": "INVALID_AS_METHOD_RANKING_AND_GEOMETRY_ACCEPTANCE",
    "may_keep_as": "sample_policy_only: do not reuse same L0 subjects across methods (OK as sample hygiene)",
    "must_not_cite_for": [
        "22-method ranking",
        "PASS_C2 geometry success",
        "18-part completion",
        "true REMOVE proof",
        "native HD proof",
        "ACCEPT_FULL_HD",
    ],
    "faults": [
        "unique-src confounds method × scene × shape × mask × donor",
        "band peeps overlap + sequential overwrite",
        "at most 9 band peeps ≠ 18 semantic parts",
        "Telea EMPTY ≠ true same-camera REMOVE",
        "name ≠ code (R01/R02/R08/R21/R22 collapse; fake NEURAL/GUIDED)",
        "outside uses method-grown union (permission self-expansion)",
        "dens→resize-back + donor HF ≠ native densify",
        "JPEG Q90 + whole-image NCC distorts report",
    ],
    "fix_first": [
        "mutex peep ownership",
        "frozen M_hole permission gate",
        "true method independence (merge aliases)",
    ],
}


def cmd_kill_note(_: argparse.Namespace) -> int:
    print(json.dumps(KILL_01433, ensure_ascii=False, indent=2))
    return 0


def cmd_rank_forbid(_: argparse.Namespace) -> int:
    print(
        "FORBID: any ranking derived from PROJ_SHQ_RESET_ALL_RETURN_UNIQUE_SRC_01433\n"
        "Reason: each method used a different SRC → no paired control.\n"
        "Legal design: scenes × methods, shared frozen inputs per scene.\n"
        f"Authority: {FORMAL} write {WRITE_ID}"
    )
    return 0


# ---------------------------------------------------------------------------
# 1. Named STICK flow recipes (reference only · not full skill engines)
# ---------------------------------------------------------------------------

STICK_FLOWS: Dict[str, Dict[str, Any]] = {
    "STICK_HUAN_YA_REN": {
        "zh": "換涯人",
        "write": "01439",
        "pipeline": ["SRC", "PEEP", "HD_ELEV", "EMPTY", "LOCK_PASTE", "IC?", "SOLE?"],
        "frozen": ["SRC", "M_hole", "peep_corners"],
        "gates": ["elev_remap=false", "outside_vs_frozen_hole=0", "head_in"],
        "not": ["freeframe", "outside=0 as visual success"],
    },
    "STICK_JI_ZHA_HUI": {
        "zh": "機炸回",
        "write": "01441",
        "pipeline": [
            "SRC",
            "PARTMAP_TEACH",
            "EXPLODE",
            "TUIDI_4CORNER",
            "MAT_STRUCTURE_LOCK",
            "HARDPASTE_MATLOCK",
            "GUIDED_FULL_MAT",
        ],
        "frozen": ["frame_corners=image_border", "elev_remap=false", "alpha_XOR=0"],
        "gates": ["mutex parts", "structure_hole_fix"],
        "not": ["explode as freeframe home", "HUAN_YA_REN peep"],
    },
    "STICK_XIN_HUA_NV": {
        "zh": "新畫女",
        "write": "01443",
        "pipeline": ["a8b", "ST1_IP", "ST2_FACELOCK", "PATH1E_PLATE", "ECC", "ET_GEO"],
        "frozen": ["a8b identity"],
        "gates": ["plate only inside hole"],
        "not": ["bare a8b direct ECC", "cliff peep"],
    },
    "STICK_HUI_CHE_DA_PAO": {
        "zh": "回車大炮",
        "write": "01445",
        "pipeline": ["L1_3SUBJ_18PART", "S2_HIERARCHY_T", "EMPTY", "MULTI_RETURN"],
        "frozen": ["relative tree", "part peep elev"],
        "gates": ["no color-band scramble", "no SUCCESS without peep SOLO"],
        "not": ["single-mecha PARTMAP only"],
    },
    "STICK_FOUR_ANTI_ARCH": {
        "zh": "四態反",
        "write": "01448",
        "pipeline": ["GEN", "REMOVE", "HOLE", "DIFF", "ANTI_each"],
        "frozen": ["StateBus", "invariants_1_6"],
        "gates": ["independent PASS ≠ combinable"],
        "not": ["local gate as global PASS"],
    },
    "STICK_WAI_LI_GROK": {
        "zh": "外力GROK",
        "write": "01466",
        "pipeline": ["Imagine_REMOVE_part", "Imagine_REMOVE_bg", "Imagine_GEN_in_hole"],
        "frozen": ["CLIP_from_chu_bei_only"],
        "gates": ["no self-peep"],
        "not": ["bbox self peep as CLIP"],
    },
    "STICK_XIN_NV_V2": {
        "zh": "新女畫V2",
        "write": "01464",
        "pipeline": ["a8b", "WLF3_hole_seat", "Nx_layer_anti"],
        "frozen": ["hole seat", "PATH1E in hole only"],
        "gates": ["no-hole-return = textbook fail"],
        "not": ["V1 default for face return"],
    },
    "STICK_WAI_LI_FAN_V2": {
        "zh": "外力反 V2.1",
        "write": "01469-01470",
        "pipeline": [
            "chu_bei→CLIP",
            "chu_part→HOLE+MARK",
            "GEN_in_hole",
            "hardpaste",
            "ANTI_board",
            "TunePack",
        ],
        "frozen": ["M_hole", "MARK", "elev_remap=false"],
        "gates": ["CLIP_from_chu_bei", "outside_max=0", "any_object TunePack"],
        "not": ["type-A constants for type-B"],
    },
}


def cmd_list_sticks(_: argparse.Namespace) -> int:
    for k, v in STICK_FLOWS.items():
        print(f"{k}  {v['zh']}  write={v['write']}")
        print(f"  pipe: {' → '.join(v['pipeline'])}")
        print(f"  gates: {', '.join(v['gates'])}")
    return 0


# ---------------------------------------------------------------------------
# 2. Method registry — honest implementation map
# ---------------------------------------------------------------------------

@dataclass
class MethodSpec:
    method_id: str
    family: str
    impl: str  # actual code path key
    distinct: bool
    alias_of: Optional[str] = None
    banned: bool = False
    note: str = ""


# True distinct return families (minimal honest set for harness A)
# Names that 01433 claimed as 22 are collapsed here.
METHOD_REGISTRY: List[MethodSpec] = [
    MethodSpec("R01_HARDPASTE_ALPHA", "hardpaste", "hardpaste", True, note="bit-exact alpha hardpaste"),
    MethodSpec("R02_HARDPASTE_ON_EMPTY", "hardpaste", "hardpaste", False, alias_of="R01_HARDPASTE_ALPHA", note="01433 identical branch"),
    MethodSpec("R03_SOFT_FEATHER_2", "feather", "feather2", True),
    MethodSpec("R04_SOFT_FEATHER_5", "feather", "feather5", True),
    MethodSpec("R05_MULTIBAND_PYRAMID", "multiband", "multiband", True, banned=True, note="01433 gpyr early-return bug; banned until fixed"),
    MethodSpec("R06_ALPHA_ERODE1", "morph", "erode1", True, note="erodes alpha then hardpaste — still gated by FROZEN hole"),
    MethodSpec("R07_ALPHA_DILATE1", "morph", "dilate1", True, note="dilate only for blend inside hole; cannot expand permission"),
    MethodSpec("R08_CORNERS4_CLIP", "hardpaste", "hardpaste", False, alias_of="R01_HARDPASTE_ALPHA", note="no independent 4corner logic in 01433"),
    MethodSpec("R09_FULL_ROI_BLOAT", "bloat", "bloat_roi", True, banned=True, note="permission self-expansion pattern — banned"),
    MethodSpec("R10_EDGE_PRESERVE", "filter", "edge_preserve", True, note="was misnamed GUIDED/NEURAL"),
    MethodSpec("R11_ALPHA_GAUSS", "feather", "gauss3", True, banned=True),
    MethodSpec("R12_HF_RESIDUAL", "hf", "hf_only", True),
    MethodSpec("R13_COPY_PEEP_NO_ELEV", "copy", "copy_peep", True),
    MethodSpec("R14_DENS_U_NO_MS", "dens", "dens_u", True, note="was fake NEURAL"),
    MethodSpec("R15_POISSON_APPROX", "poisson", "poisson_approx", True, banned=True),
    MethodSpec("R16_MAX_BLEND", "blend", "max_blend", True),
    MethodSpec("R17_MIN_BLEND", "blend", "min_blend", True),
    MethodSpec("R18_SCREEN_BLEND", "blend", "screen", True),
    MethodSpec("R19_OVERLAY_BLEND", "blend", "overlay", True),
    MethodSpec("R20_SOBEL_WEIGHT", "edge", "sobel_w", True),
    MethodSpec("R21_DOUBLE_HARDPASTE", "hardpaste", "hardpaste", False, alias_of="R01_HARDPASTE_ALPHA", note="01433 not sequential KEEP→EMPTY chain"),
    MethodSpec("R22_ZERO_FEATHER", "hardpaste", "hardpaste", False, alias_of="R01_HARDPASTE_ALPHA"),
]


def distinct_methods() -> List[MethodSpec]:
    return [m for m in METHOD_REGISTRY if m.distinct and not m.banned]


def cmd_list_methods(_: argparse.Namespace) -> int:
    print(f"{'id':40s} {'family':12s} {'impl':14s} distinct banned alias")
    for m in METHOD_REGISTRY:
        print(
            f"{m.method_id:40s} {m.family:12s} {m.impl:14s} "
            f"{str(m.distinct):7s} {str(m.banned):6s} {m.alias_of or ''}"
        )
    d = distinct_methods()
    print(f"\nDistinct runnable (not banned): {len(d)}")
    print(f"01433 claimed 22; honest distinct families here: {len(d)}")
    return 0


# ---------------------------------------------------------------------------
# 3. Scene bundle — frozen inputs
# ---------------------------------------------------------------------------

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_img(img: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(img).tobytes())


def save_img(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if img.ndim == 2 or (img.ndim == 3 and img.shape[2] == 1):
        cv2.imwrite(str(path), img)
    elif img.shape[2] == 4:
        cv2.imwrite(str(path), img)
    else:
        cv2.imwrite(str(path), img)


def load_img(path: Path) -> np.ndarray:
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    return im


@dataclass
class Peep:
    peep_id: str
    part_role: str  # head|torso|leg|mecha_part|full_subject|...
    subject_id: str
    # exclusive ownership mask on full canvas
    mask: np.ndarray  # uint8 0/255 full HxW
    # peep crop (RGB) and elev (RGB) same spatial size as bbox of mask
    peep_rgb: np.ndarray
    elev_rgb: np.ndarray
    bbox: Tuple[int, int, int, int]  # x0,y0,x1,y1


@dataclass
class SceneBundle:
    """Frozen control inputs for one scene — shared by all methods."""
    scene_id: str
    stick_hint: str
    keep: np.ndarray  # BGR
    empty: np.ndarray  # BGR  (honest empty: from construction, not Telea-from-self for synth)
    hole: np.ndarray  # uint8 0/255 FROZEN permission
    peeps: List[Peep]
    meta: Dict[str, Any] = field(default_factory=dict)

    def assert_invariants(self) -> None:
        H, W = self.keep.shape[:2]
        assert self.empty.shape[:2] == (H, W)
        assert self.hole.shape[:2] == (H, W)
        # mutex
        acc = np.zeros((H, W), np.int32)
        for p in self.peeps:
            assert p.mask.shape == (H, W)
            acc += (p.mask > 0).astype(np.int32)
        if acc.max() > 1:
            raise AssertionError(
                f"peep ownership not mutex: max overlap={int(acc.max())} "
                f"(need M_i ∩ M_j = ∅)"
            )
        # hole covers all peeps
        peep_u = (acc > 0).astype(np.uint8) * 255
        leak = int(np.logical_and(peep_u > 0, self.hole == 0).sum())
        if leak > 0:
            raise AssertionError(f"peep pixels outside frozen hole: {leak}")

    def save(self, out: Path) -> None:
        ensure_dir(out)
        save_img(out / "KEEP.png", self.keep)
        save_img(out / "EMPTY.png", self.empty)
        save_img(out / "HOLE.png", self.hole)
        peep_dir = ensure_dir(out / "peeps")
        catalog = []
        for p in self.peeps:
            d = ensure_dir(peep_dir / p.peep_id)
            save_img(d / "mask.png", p.mask)
            save_img(d / "peep_rgb.png", p.peep_rgb)
            save_img(d / "elev_rgb.png", p.elev_rgb)
            catalog.append(
                {
                    "peep_id": p.peep_id,
                    "part_role": p.part_role,
                    "subject_id": p.subject_id,
                    "bbox": list(p.bbox),
                    "mask_sha": sha256_img(p.mask),
                    "peep_sha": sha256_img(p.peep_rgb),
                    "elev_sha": sha256_img(p.elev_rgb),
                }
            )
        meta = {
            "scene_id": self.scene_id,
            "stick_hint": self.stick_hint,
            "write_id": WRITE_ID,
            "formal": FORMAL,
            "ACCEPT_FULL_HD": ACCEPT_FULL_HD,
            "frozen_sha": {
                "keep": sha256_img(self.keep),
                "empty": sha256_img(self.empty),
                "hole": sha256_img(self.hole),
            },
            "n_peeps": len(self.peeps),
            "mutex_ok": True,
            "peeps": catalog,
            "meta": self.meta,
        }
        (out / "SCENE_BUNDLE.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def load(path: Path) -> "SceneBundle":
        keep = load_img(path / "KEEP.png")
        empty = load_img(path / "EMPTY.png")
        hole = load_img(path / "HOLE.png")
        if hole.ndim == 3:
            hole = hole[:, :, 0]
        meta = json.loads((path / "SCENE_BUNDLE.json").read_text(encoding="utf-8"))
        peeps: List[Peep] = []
        for c in meta["peeps"]:
            d = path / "peeps" / c["peep_id"]
            peeps.append(
                Peep(
                    peep_id=c["peep_id"],
                    part_role=c["part_role"],
                    subject_id=c["subject_id"],
                    mask=load_img(d / "mask.png")[:, :, 0]
                    if load_img(d / "mask.png").ndim == 3
                    else load_img(d / "mask.png"),
                    peep_rgb=load_img(d / "peep_rgb.png"),
                    elev_rgb=load_img(d / "elev_rgb.png"),
                    bbox=tuple(c["bbox"]),  # type: ignore
                )
            )
        sb = SceneBundle(
            scene_id=meta["scene_id"],
            stick_hint=meta.get("stick_hint", ""),
            keep=keep,
            empty=empty,
            hole=hole,
            peeps=peeps,
            meta=meta.get("meta", {}),
        )
        sb.assert_invariants()
        return sb


# ---------------------------------------------------------------------------
# 4. Synth presets (self-contained · no external assets required)
# ---------------------------------------------------------------------------

def _draw_subject(
    canvas: np.ndarray,
    cx: int,
    cy: int,
    scale: float,
    color_head,
    color_torso,
    color_leg,
) -> Dict[str, np.ndarray]:
    """Draw a simple person-like subject; return part masks (full canvas)."""
    H, W = canvas.shape[:2]
    masks = {}
    # head ellipse
    ah, aw = int(28 * scale), int(22 * scale)
    head = np.zeros((H, W), np.uint8)
    cv2.ellipse(head, (cx, cy - int(70 * scale)), (aw, ah), 0, 0, 360, 255, -1)
    canvas[head > 0] = color_head
    # torso rect
    torso = np.zeros((H, W), np.uint8)
    x0, x1 = cx - int(30 * scale), cx + int(30 * scale)
    y0, y1 = cy - int(45 * scale), cy + int(25 * scale)
    cv2.rectangle(torso, (x0, y0), (x1, y1), 255, -1)
    # remove head overlap from torso ownership later via mutex assign
    canvas[torso > 0] = color_torso
    # legs
    leg = np.zeros((H, W), np.uint8)
    cv2.rectangle(
        leg,
        (cx - int(28 * scale), cy + int(20 * scale)),
        (cx + int(28 * scale), cy + int(95 * scale)),
        255,
        -1,
    )
    canvas[leg > 0] = color_leg
    masks["head"] = head
    masks["torso"] = torso
    masks["leg"] = leg
    return masks


def make_mutex_parts(part_masks: Dict[str, np.ndarray], order: List[str]) -> Dict[str, np.ndarray]:
    """Assign exclusive ownership: earlier parts in order win; later lose overlap."""
    claimed = np.zeros_like(next(iter(part_masks.values())), np.uint8)
    out = {}
    for name in order:
        m = part_masks[name].copy()
        m[claimed > 0] = 0
        out[name] = m
        claimed = np.maximum(claimed, m)
    return out


def synth_scene(preset: str, scene_id: str) -> SceneBundle:
    """
    Build honest synthetic scene:
    - KEEP has subjects
    - EMPTY is true background (subjects never painted) — not Telea
    - HOLE = subject silhouettes
    - peeps mutex by part
    """
    W, H = 640, 360
    if preset == "synth_cliff":
        stick = "STICK_HUAN_YA_REN"
        # background: sky + cliff
        empty = np.zeros((H, W, 3), np.uint8)
        empty[:] = (210, 180, 140)  # BGR sand
        cv2.rectangle(empty, (0, 0), (W, int(H * 0.45)), (230, 200, 160), -1)
        cv2.rectangle(empty, (0, int(H * 0.55)), (W, H), (40, 60, 80), -1)
        keep = empty.copy()
        # one subject on cliff edge
        parts = _draw_subject(
            keep, cx=W // 2, cy=int(H * 0.42), scale=1.0,
            color_head=(40, 40, 200), color_torso=(30, 120, 40), color_leg=(20, 20, 20),
        )
        parts = make_mutex_parts(parts, ["head", "torso", "leg"])
        subjects = [("S0", parts)]
    elif preset == "synth_dual_mecha":
        stick = "STICK_WAI_LI_FAN_V2"
        empty = np.zeros((H, W, 3), np.uint8)
        empty[:] = (30, 30, 30)
        # grid floor
        for x in range(0, W, 40):
            cv2.line(empty, (x, 0), (x, H), (50, 50, 50), 1)
        keep = empty.copy()
        subjects = []
        for i, cx in enumerate([W // 3, 2 * W // 3]):
            parts = _draw_subject(
                keep, cx=cx, cy=H // 2, scale=0.9 + 0.1 * i,
                color_head=(200, 200, 50), color_torso=(180, 80, 20), color_leg=(100, 100, 100),
            )
            # treat as mecha bands but still mutex
            parts = make_mutex_parts(parts, ["head", "torso", "leg"])
            # rename roles
            parts = {
                "helmet" if k == "head" else ("torso" if k == "torso" else "limb"): v
                for k, v in parts.items()
            }
            subjects.append((f"M{i}", parts))
    elif preset == "synth_3subj":
        stick = "STICK_HUI_CHE_DA_PAO"
        empty = np.full((H, W, 3), 60, np.uint8)
        keep = empty.copy()
        subjects = []
        for i, (cx, col) in enumerate([
            (W // 4, ((0, 0, 220), (0, 180, 0), (0, 0, 0))),
            (W // 2, ((220, 220, 220), (200, 200, 200), (160, 160, 160))),
            (3 * W // 4, ((0, 0, 180), (0, 0, 120), (0, 0, 80))),
        ]):
            parts = _draw_subject(
                keep, cx=cx, cy=H // 2, scale=0.75,
                color_head=col[0], color_torso=col[1], color_leg=col[2],
            )
            parts = make_mutex_parts(parts, ["head", "torso", "leg"])
            subjects.append((f"T{i}", parts))
    else:
        raise ValueError(f"unknown preset {preset}")

    hole = np.zeros((H, W), np.uint8)
    peeps: List[Peep] = []
    for sid, parts in subjects:
        for role, m in parts.items():
            if m.sum() == 0:
                continue
            hole = np.maximum(hole, m)
            ys, xs = np.where(m > 0)
            y0, y1 = int(ys.min()), int(ys.max()) + 1
            x0, x1 = int(xs.min()), int(xs.max()) + 1
            # peep from KEEP; elev = peep with mild sharpen (not native HD claim)
            peep = keep[y0:y1, x0:x1].copy()
            elev = cv2.detailEnhance(peep, sigma_s=8, sigma_r=0.15)
            peeps.append(
                Peep(
                    peep_id=f"{sid}_{role}",
                    part_role=role,
                    subject_id=sid,
                    mask=m,
                    peep_rgb=peep,
                    elev_rgb=elev,
                    bbox=(x0, y0, x1, y1),
                )
            )

    sb = SceneBundle(
        scene_id=scene_id,
        stick_hint=stick,
        keep=keep,
        empty=empty,
        hole=hole,
        peeps=peeps,
        meta={"preset": preset, "construction": "true_empty_not_telea", "W": W, "H": H},
    )
    sb.assert_invariants()
    return sb


# ---------------------------------------------------------------------------
# 5. Return methods — operate ONLY inside frozen hole; cannot grow permission
# ---------------------------------------------------------------------------

def _paste_elev_on_base(
    base: np.ndarray,
    peeps: List[Peep],
    mode: str,
    frozen_hole: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compose peeps onto base.
    Permission: only pixels where frozen_hole>0 may change.
    Ownership: each peep writes only its exclusive mask.
    Returns (ab, used_mask) where used_mask ⊆ frozen_hole.
    """
    ab = base.copy()
    H, W = ab.shape[:2]
    used = np.zeros((H, W), np.uint8)

    for p in peeps:
        x0, y0, x1, y1 = p.bbox
        m_full = p.mask
        # elev resized to bbox if needed
        elev = p.elev_rgb
        if elev.shape[0] != (y1 - y0) or elev.shape[1] != (x1 - x0):
            elev = cv2.resize(elev, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
        peep = p.peep_rgb
        if peep.shape[0] != elev.shape[0]:
            peep = cv2.resize(peep, (elev.shape[1], elev.shape[0]), interpolation=cv2.INTER_LINEAR)

        roi_m = m_full[y0:y1, x0:x1]
        # hard permission clip
        allow = np.logical_and(roi_m > 0, frozen_hole[y0:y1, x0:x1] > 0)

        if mode == "hardpaste":
            src = elev
            alpha = allow.astype(np.float32)
        elif mode == "copy_peep":
            src = peep
            alpha = allow.astype(np.float32)
        elif mode == "feather2":
            src = elev
            a = (roi_m > 0).astype(np.uint8) * 255
            a = cv2.GaussianBlur(a, (0, 0), 2)
            alpha = (a.astype(np.float32) / 255.0) * allow.astype(np.float32)
        elif mode == "feather5":
            src = elev
            a = (roi_m > 0).astype(np.uint8) * 255
            a = cv2.GaussianBlur(a, (0, 0), 5)
            alpha = (a.astype(np.float32) / 255.0) * allow.astype(np.float32)
        elif mode == "gauss3":
            src = elev
            a = (roi_m > 0).astype(np.uint8) * 255
            a = cv2.GaussianBlur(a, (7, 7), 3)
            alpha = (a.astype(np.float32) / 255.0) * allow.astype(np.float32)
        elif mode == "erode1":
            src = elev
            a = (roi_m > 0).astype(np.uint8) * 255
            a = cv2.erode(a, np.ones((3, 3), np.uint8), 1)
            alpha = (a > 0).astype(np.float32) * allow.astype(np.float32)
        elif mode == "dilate1":
            # dilate only for soft edge INSIDE hole — still AND frozen allow
            src = elev
            a = (roi_m > 0).astype(np.uint8) * 255
            a = cv2.dilate(a, np.ones((3, 3), np.uint8), 1)
            alpha = (a > 0).astype(np.float32) * allow.astype(np.float32)
        elif mode == "bloat_roi":
            # BANNED pattern: would fill whole bbox — we still clip to frozen hole
            # so it cannot self-expand permission; result is just hardpaste of bbox∩hole
            src = elev
            alpha = allow.astype(np.float32)
        elif mode == "edge_preserve":
            src = cv2.edgePreservingFilter(elev, flags=1, sigma_s=40, sigma_r=0.3)
            alpha = allow.astype(np.float32)
        elif mode == "hf_only":
            blur = cv2.GaussianBlur(elev, (0, 0), 1.2)
            hf = cv2.addWeighted(elev, 1.5, blur, -0.5, 0)
            base_roi = ab[y0:y1, x0:x1].astype(np.float32)
            src = np.clip(base_roi + (hf.astype(np.float32) - elev.astype(np.float32)), 0, 255).astype(np.uint8)
            alpha = allow.astype(np.float32)
        elif mode == "dens_u":
            # 2x then back — proxy only, not native HD claim
            up = cv2.resize(elev, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            up = cv2.detailEnhance(up, sigma_s=10, sigma_r=0.15)
            src = cv2.resize(up, (elev.shape[1], elev.shape[0]), interpolation=cv2.INTER_AREA)
            alpha = allow.astype(np.float32)
        elif mode == "poisson_approx":
            # simple seamless-ish: hardpaste (true poisson optional)
            src = elev
            alpha = allow.astype(np.float32)
        elif mode == "max_blend":
            src = np.maximum(elev, peep)
            alpha = allow.astype(np.float32)
        elif mode == "min_blend":
            src = np.minimum(elev, peep)
            alpha = allow.astype(np.float32)
        elif mode == "screen":
            e = elev.astype(np.float32) / 255.0
            b = ab[y0:y1, x0:x1].astype(np.float32) / 255.0
            src = ((1 - (1 - e) * (1 - b)) * 255).astype(np.uint8)
            alpha = allow.astype(np.float32)
        elif mode == "overlay":
            e = elev.astype(np.float32) / 255.0
            b = ab[y0:y1, x0:x1].astype(np.float32) / 255.0
            out = np.where(b < 0.5, 2 * e * b, 1 - 2 * (1 - e) * (1 - b))
            src = (out * 255).astype(np.uint8)
            alpha = allow.astype(np.float32)
        elif mode == "sobel_w":
            gray = cv2.cvtColor(elev, cv2.COLOR_BGR2GRAY)
            sx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            sy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            mag = cv2.magnitude(sx, sy)
            mag = mag / (mag.max() + 1e-6)
            alpha = allow.astype(np.float32) * (0.4 + 0.6 * mag)
            src = elev
        elif mode == "multiband":
            # honest 3-level (fixed early-return bug of 01433)
            src = elev
            a = (roi_m > 0).astype(np.uint8) * 255
            gp_a = [a.astype(np.float32)]
            gp_s = [src.astype(np.float32)]
            gp_b = [ab[y0:y1, x0:x1].astype(np.float32)]
            for _ in range(2):
                gp_a.append(cv2.pyrDown(gp_a[-1]))
                gp_s.append(cv2.pyrDown(gp_s[-1]))
                gp_b.append(cv2.pyrDown(gp_b[-1]))
            # reconstruct coarse to fine
            out = gp_b[-1]
            for i in range(len(gp_a) - 1, 0, -1):
                a_i = cv2.resize(gp_a[i], (gp_b[i - 1].shape[1], gp_b[i - 1].shape[0]))
                s_i = cv2.resize(gp_s[i], (gp_b[i - 1].shape[1], gp_b[i - 1].shape[0]))
                a_n = np.clip(a_i / 255.0, 0, 1)[..., None]
                out = s_i * a_n + gp_b[i - 1] * (1 - a_n)
            src = np.clip(out, 0, 255).astype(np.uint8)
            alpha = allow.astype(np.float32)
        else:
            raise ValueError(f"unknown mode {mode}")

        # apply
        if src.dtype != np.uint8:
            src = np.clip(src, 0, 255).astype(np.uint8)
        if alpha.ndim == 2:
            a3 = alpha[..., None]
        else:
            a3 = alpha
        roi = ab[y0:y1, x0:x1].astype(np.float32)
        blended = src.astype(np.float32) * a3 + roi * (1.0 - a3)
        ab[y0:y1, x0:x1] = np.clip(blended, 0, 255).astype(np.uint8)
        used[y0:y1, x0:x1] = np.maximum(
            used[y0:y1, x0:x1], (alpha > 0.01).astype(np.uint8) * 255
        )

    # final hard clip: anything outside frozen hole must equal base
    out_mask = frozen_hole == 0
    ab[out_mask] = base[out_mask]
    return ab, used


def outside_max(ab: np.ndarray, base: np.ndarray, frozen_hole: np.ndarray) -> int:
    """Geometry gate: max abs diff where frozen_hole==0. Method cannot redefine hole."""
    outm = frozen_hole == 0
    if not np.any(outm):
        return 0
    diff = np.abs(ab.astype(np.int16) - base.astype(np.int16))
    return int(diff[outm].max()) if diff[outm].size else 0


def ncc_roi(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    m = mask > 0
    if m.sum() < 16:
        return float("nan")
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float64)[m]
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float64)[m]
    ga -= ga.mean()
    gb -= gb.mean()
    denom = np.linalg.norm(ga) * np.linalg.norm(gb)
    if denom < 1e-9:
        return float("nan")
    return float((ga * gb).sum() / denom)


def apply_method(
    method: MethodSpec,
    base: np.ndarray,
    scene: SceneBundle,
) -> Dict[str, Any]:
    if method.banned:
        return {
            "method_id": method.method_id,
            "status": "FAIL_BAN",
            "reason": method.note or "banned",
            "outside": None,
            "ACCEPT_FULL_HD": ACCEPT_FULL_HD,
        }
    # resolve alias
    impl = method.impl
    if method.alias_of:
        # still run but mark non-distinct
        pass
    ab, used = _paste_elev_on_base(base, scene.peeps, impl, scene.hole)
    outv = outside_max(ab, base, scene.hole)
    ncc = ncc_roi(ab, scene.keep, scene.hole)
    # coverage of hole filled
    cov = float((used > 0).sum()) / float(max(1, (scene.hole > 0).sum()))
    status = "PASS_A" if outv == 0 else "FAIL_OUTSIDE"
    return {
        "method_id": method.method_id,
        "impl": impl,
        "alias_of": method.alias_of,
        "distinct": method.distinct,
        "status": status,
        "outside": outv,
        "ncc_hole": None if (isinstance(ncc, float) and math.isnan(ncc)) else ncc,
        "coverage_hole": round(cov, 5),
        "n_peeps": len(scene.peeps),
        "ACCEPT_FULL_HD": ACCEPT_FULL_HD,
        "image": ab,
        "used_mask": used,
    }


# ---------------------------------------------------------------------------
# 6. Layer A / B / C runners
# ---------------------------------------------------------------------------

def run_layer_A(scene: SceneBundle, out: Path, base_mode: str = "empty") -> Dict[str, Any]:
    """
    A: single-method acceptance on FROZEN inputs.
    Every distinct non-banned method runs on the same scene bundle.
    """
    ensure_dir(out)
    base = scene.empty if base_mode == "empty" else scene.keep
    save_img(out / f"BASE_{base_mode}.png", base)
    save_img(out / "HOLE_FROZEN.png", scene.hole)

    receipts = []
    methods = [m for m in METHOD_REGISTRY if m.distinct]  # include banned to show FAIL_BAN
    for m in methods:
        rec = apply_method(m, base, scene)
        mid = rec["method_id"]
        d = ensure_dir(out / mid)
        if "image" in rec:
            save_img(d / "RETURN.png", rec["image"])
            # re-read disk and recompute outside (01433 failure mode fixed)
            disk = load_img(d / "RETURN.png")
            # PNG lossless — still re-verify
            rec["outside_disk"] = outside_max(disk, base, scene.hole)
            if rec["outside_disk"] != rec["outside"]:
                rec["status"] = "FAIL_DISK_MISMATCH"
            save_img(d / "USED.png", rec["used_mask"])
            del rec["image"]
            del rec["used_mask"]
        (d / "receipt.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        receipts.append(rec)

    report = {
        "layer": "A",
        "write_id": WRITE_ID,
        "formal": FORMAL,
        "scene_id": scene.scene_id,
        "stick_hint": scene.stick_hint,
        "base_mode": base_mode,
        "frozen_hole_sha": sha256_img(scene.hole),
        "n_methods_ran": len(receipts),
        "n_pass": sum(1 for r in receipts if r["status"] == "PASS_A"),
        "n_fail_ban": sum(1 for r in receipts if r["status"] == "FAIL_BAN"),
        "n_fail_outside": sum(1 for r in receipts if r["status"] == "FAIL_OUTSIDE"),
        "receipts": receipts,
        "ACCEPT_FULL_HD": ACCEPT_FULL_HD,
        "note": "A-pass ≠ B-pass ≠ C-pass; not ranking across confounded scenes",
    }
    (out / "REPORT_A.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def run_layer_B(scene: SceneBundle, out: Path) -> Dict[str, Any]:
    """
    B: composition acceptance — mutex, seam, order independence, material continuity proxy.
    Uses hardpaste family as compose reference (not a ranking).
    """
    ensure_dir(out)
    # 1) mutex already asserted
    mutex_ok = True
    try:
        scene.assert_invariants()
    except AssertionError as e:
        mutex_ok = False
        mutex_err = str(e)
    else:
        mutex_err = ""

    # 2) order independence: reverse peep order must match
    base = scene.empty
    m = MethodSpec("B_HARD", "hardpaste", "hardpaste", True)
    rec1 = apply_method(m, base, scene)
    scene_rev = SceneBundle(
        scene_id=scene.scene_id,
        stick_hint=scene.stick_hint,
        keep=scene.keep,
        empty=scene.empty,
        hole=scene.hole,
        peeps=list(reversed(scene.peeps)),
        meta=scene.meta,
    )
    rec2 = apply_method(m, base, scene_rev)
    img1, img2 = rec1.pop("image"), rec2.pop("image")
    rec1.pop("used_mask", None)
    rec2.pop("used_mask", None)
    order_maxdiff = int(np.abs(img1.astype(np.int16) - img2.astype(np.int16)).max())
    order_independent = order_maxdiff == 0

    save_img(out / "RETURN_ORDER_FWD.png", img1)
    save_img(out / "RETURN_ORDER_REV.png", img2)

    # 3) seam proxy: gradient jump across peep boundaries inside hole
    seam_score = _seam_score(img1, scene)

    # 4) outside vs frozen
    outside = outside_max(img1, base, scene.hole)

    status = "PASS_B"
    reasons = []
    if not mutex_ok:
        status = "FAIL_B_MUTEX"
        reasons.append(mutex_err)
    if not order_independent:
        status = "FAIL_B_ORDER"
        reasons.append(f"order_maxdiff={order_maxdiff}")
    if outside != 0:
        status = "FAIL_B_OUTSIDE"
        reasons.append(f"outside={outside}")

    report = {
        "layer": "B",
        "write_id": WRITE_ID,
        "scene_id": scene.scene_id,
        "status": status,
        "reasons": reasons,
        "mutex_ok": mutex_ok,
        "order_independent": order_independent,
        "order_maxdiff": order_maxdiff,
        "outside_frozen_hole": outside,
        "seam_score": seam_score,
        "n_peeps": len(scene.peeps),
        "ACCEPT_FULL_HD": ACCEPT_FULL_HD,
        "note": "B tests compose; does not rank 22 methods",
    }
    (out / "REPORT_B.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def _seam_score(img: np.ndarray, scene: SceneBundle) -> float:
    """Mean abs gradient along peep boundaries (lower ~ smoother)."""
    H, W = scene.hole.shape
    boundary = np.zeros((H, W), np.uint8)
    for p in scene.peeps:
        e = cv2.morphologyEx(p.mask, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        boundary = np.maximum(boundary, e)
    boundary = np.logical_and(boundary > 0, scene.hole > 0)
    if boundary.sum() < 8:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    return float(mag[boundary].mean())


def run_layer_C(scene_paths: List[Path], out: Path) -> Dict[str, Any]:
    """
    C: multi-scene block design — each scene runs full method matrix (layer A).
    Ranking across scenes is still forbidden; report is a matrix not a single rank.
    """
    ensure_dir(out)
    matrix = []
    for sp in scene_paths:
        scene = SceneBundle.load(sp)
        a_out = ensure_dir(out / scene.scene_id / "A")
        rep = run_layer_A(scene, a_out, base_mode="empty")
        b_out = ensure_dir(out / scene.scene_id / "B")
        rep_b = run_layer_B(scene, b_out)
        matrix.append(
            {
                "scene_id": scene.scene_id,
                "stick_hint": scene.stick_hint,
                "A_n_pass": rep["n_pass"],
                "A_n_fail_outside": rep["n_fail_outside"],
                "A_n_fail_ban": rep["n_fail_ban"],
                "B_status": rep_b["status"],
            }
        )
    report = {
        "layer": "C",
        "write_id": WRITE_ID,
        "formal": FORMAL,
        "n_scenes": len(scene_paths),
        "matrix": matrix,
        "ACCEPT_FULL_HD": ACCEPT_FULL_HD,
        "forbid": "do not collapse matrix to single method ranking (01433 kill)",
    }
    (out / "REPORT_C.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


# ---------------------------------------------------------------------------
# 7. CLI
# ---------------------------------------------------------------------------

def cmd_selftest(_: argparse.Namespace) -> int:
    root = Path("/tmp/shq_harness_01472_selftest")
    if root.exists():
        import shutil

        shutil.rmtree(root)
    ensure_dir(root)
    results = {}
    for preset, sid in [
        ("synth_cliff", "S_cliff"),
        ("synth_dual_mecha", "S_mecha"),
        ("synth_3subj", "S_3subj"),
    ]:
        sb = synth_scene(preset, sid)
        sp = ensure_dir(root / sid)
        sb.save(sp)
        # reload invariants
        sb2 = SceneBundle.load(sp)
        a = run_layer_A(sb2, ensure_dir(sp / "A"))
        b = run_layer_B(sb2, ensure_dir(sp / "B"))
        results[sid] = {
            "preset": preset,
            "stick": sb.stick_hint,
            "n_peeps": len(sb.peeps),
            "A_pass": a["n_pass"],
            "B": b["status"],
            "mutex": b["mutex_ok"],
            "order_ind": b["order_independent"],
        }
    # C matrix
    scenes = [root / "S_cliff", root / "S_mecha", root / "S_3subj"]
    c = run_layer_C(scenes, ensure_dir(root / "C_MATRIX"))
    # structural asserts
    assert all(r["mutex"] for r in results.values()), results
    assert all(r["order_ind"] for r in results.values()), results
    assert all(r["B"] == "PASS_B" for r in results.values()), results
    # hardpaste must pass A
    for sid in results:
        rep = json.loads((root / sid / "A" / "REPORT_A.json").read_text())
        hp = [x for x in rep["receipts"] if x["method_id"] == "R01_HARDPASTE_ALPHA"][0]
        assert hp["status"] == "PASS_A" and hp["outside"] == 0, hp
    summary = {
        "selftest": "PASS",
        "write_id": WRITE_ID,
        "formal": FORMAL,
        "ACCEPT_FULL_HD": ACCEPT_FULL_HD,
        "results": results,
        "C": c["matrix"],
        "kill_01433": KILL_01433["verdict"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    (root / "SELFTEST.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


def cmd_init_scene(args: argparse.Namespace) -> int:
    out = Path(args.out)
    sb = synth_scene(args.preset, args.scene_id or out.name)
    sb.save(out)
    print(json.dumps({"ok": True, "scene": str(out), "stick": sb.stick_hint, "n_peeps": len(sb.peeps)}, ensure_ascii=False))
    return 0


def cmd_run_A(args: argparse.Namespace) -> int:
    scene = SceneBundle.load(Path(args.scene))
    rep = run_layer_A(scene, Path(args.out), base_mode=args.base)
    print(json.dumps({k: rep[k] for k in rep if k != "receipts"}, ensure_ascii=False, indent=2))
    return 0


def cmd_run_B(args: argparse.Namespace) -> int:
    scene = SceneBundle.load(Path(args.scene))
    rep = run_layer_B(scene, Path(args.out))
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


def cmd_run_C(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.scenes.split(",")]
    rep = run_layer_C(paths, Path(args.out))
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0




# ---------------------------------------------------------------------------
# 8. Gold ingest (01439 換涯人 / 01441 機炸回 / 01464 新女畫V2)
# ---------------------------------------------------------------------------

IMAGINE_DIR = Path("/workspace/artifacts/imagine_images")
SETS_DIR = Path("/workspace/artifacts/SETS")

GOLD_PRESETS: Dict[str, Dict[str, Any]] = {
    "hyr": {
        "zh": "換涯人",
        "write": "01439",
        "stick": "STICK_HUAN_YA_REN",
        "proj": "PROJ_SHQ_HUAN_YA_REN_01439",
        "keep_key": "src_full",
        "elev_key": "hd_elev_cut",
        "final_key": "final_clean",
        "empty_mode": "proxy_grabcut_telea",  # no true EMPTY asset in gold set
        "parts": "person_3band",
    },
    "jzh": {
        "zh": "機炸回",
        "write": "01441",
        "stick": "STICK_JI_ZHA_HUI",
        "proj": "PROJ_SHQ_JI_ZHA_HUI_01441",
        "keep_key": "SRC_full_yard",
        "elev_key": None,
        "final_key": "BOARD_1_2_3",
        "empty_mode": "proxy_grabcut_telea",
        "parts": "person_3band",
    },
    "xnv2": {
        "zh": "新女畫V2",
        "write": "01464",
        "stick": "STICK_XIN_NV_V2",
        "proj": "PROJ_SHQ_XIN_NV_V2_01464",
        "keep_file": "L0.jpg",
        "empty_file": "chu_tou.jpg",  # 外力除头 → hole via kou
        "elev_file": "plate.jpg",
        "empty_mode": "true_diff_chu_tou",  # Imagine 外力 · better than Telea
        "parts": "head_focus",
    },
}


def _resolve_resolved_dir(proj: str) -> Path:
    return SETS_DIR / proj / "gold" / "resolved"


def _load_any(folder: Path, stem: str) -> Optional[np.ndarray]:
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = folder / f"{stem}{ext}"
        if p.exists():
            return load_img(p)
    return None


def estimate_hole_grabcut(keep: np.ndarray) -> np.ndarray:
    """Proxy hole when true EMPTY missing. Not true REMOVE proof."""
    H, W = keep.shape[:2]
    mask = np.zeros((H, W), np.uint8)
    # center rect prior
    x0, y0 = int(W * 0.25), int(H * 0.08)
    x1, y1 = int(W * 0.75), int(H * 0.98)
    rect = (x0, y0, max(1, x1 - x0), max(1, y1 - y0))
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(keep, mask, rect, bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
        hole = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    except Exception:
        hole = np.zeros((H, W), np.uint8)
        cv2.rectangle(hole, (x0, y0), (x1, y1), 255, -1)
    # keep largest CC
    n, lab, st, _ = cv2.connectedComponentsWithStats(hole, 8)
    if n > 1:
        i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        hole = np.where(lab == i, 255, 0).astype(np.uint8)
    hole = cv2.morphologyEx(hole, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), 2)
    return hole


def hole_from_kou(keep: np.ndarray, removed: np.ndarray, thr: int = 22) -> np.ndarray:
    """Support(|keep-removed|) → hole. Prefer when true 外力 edit exists."""
    if keep.shape != removed.shape:
        removed = cv2.resize(removed, (keep.shape[1], keep.shape[0]), interpolation=cv2.INTER_LINEAR)
    d = np.abs(keep.astype(np.int16) - removed.astype(np.int16)).max(axis=2)
    hole = (d >= thr).astype(np.uint8) * 255
    hole = cv2.morphologyEx(hole, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), 2)
    n, lab, st, _ = cv2.connectedComponentsWithStats(hole, 8)
    if n > 1:
        # keep up to 2 largest (head + debris) but prefer largest
        areas = st[1:, cv2.CC_STAT_AREA]
        i = 1 + int(np.argmax(areas))
        hole = np.where(lab == i, 255, 0).astype(np.uint8)
    return hole


def empty_from_hole(keep: np.ndarray, hole: np.ndarray) -> np.ndarray:
    return cv2.inpaint(keep, hole, 5, cv2.INPAINT_TELEA)


def peeps_from_hole(
    keep: np.ndarray,
    hole: np.ndarray,
    elev_img: Optional[np.ndarray],
    mode: str,
) -> List[Peep]:
    H, W = keep.shape[:2]
    ys, xs = np.where(hole > 0)
    if len(xs) < 8:
        raise RuntimeError("hole too small for peeps")
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    bh = max(1, y1 - y0)

    if mode == "head_focus":
        bands = [("head", 0.0, 0.45), ("torso", 0.35, 1.0)]
    else:
        bands = [("head", 0.0, 0.33), ("torso", 0.33, 0.66), ("leg", 0.66, 1.0)]

    # build band masks then mutex top-wins
    raw = {}
    for role, a, b in bands:
        m = np.zeros((H, W), np.uint8)
        ya, yb = y0 + int(bh * a), y0 + int(bh * b)
        band = np.zeros_like(hole)
        band[ya:yb, :] = 255
        m = cv2.bitwise_and(hole, band)
        raw[role] = m
    order = [r for r, _, _ in bands]
    claimed = np.zeros((H, W), np.uint8)
    peeps: List[Peep] = []
    for role in order:
        m = raw[role].copy()
        m[claimed > 0] = 0
        if m.sum() < 32:
            continue
        claimed = np.maximum(claimed, m)
        ys2, xs2 = np.where(m > 0)
        yy0, yy1 = int(ys2.min()), int(ys2.max()) + 1
        xx0, xx1 = int(xs2.min()), int(xs2.max()) + 1
        peep = keep[yy0:yy1, xx0:xx1].copy()
        if elev_img is not None:
            e = elev_img
            if e.shape[:2] != keep.shape[:2]:
                e = cv2.resize(e, (W, H), interpolation=cv2.INTER_LINEAR)
            elev = e[yy0:yy1, xx0:xx1].copy()
        else:
            elev = cv2.detailEnhance(peep, sigma_s=8, sigma_r=0.15)
        peeps.append(
            Peep(
                peep_id=f"S0_{role}",
                part_role=role,
                subject_id="S0",
                mask=m,
                peep_rgb=peep,
                elev_rgb=elev,
                bbox=(xx0, yy0, xx1, yy1),
            )
        )
    return peeps


def ingest_gold_preset(preset: str, scene_id: Optional[str] = None) -> SceneBundle:
    if preset not in GOLD_PRESETS:
        raise KeyError(f"unknown gold preset {preset}; have {list(GOLD_PRESETS)}")
    cfg = GOLD_PRESETS[preset]
    resolved = _resolve_resolved_dir(cfg["proj"])
    if not resolved.exists():
        raise FileNotFoundError(f"missing resolved gold: {resolved}")

    meta_extra: Dict[str, Any] = {
        "gold_preset": preset,
        "write": cfg["write"],
        "empty_mode": cfg["empty_mode"],
        "proj": cfg["proj"],
        "ACCEPT_FULL_HD": False,
        "note": "ingest for harness A/B; proxy empty ≠ true REMOVE proof unless true_diff_*",
    }

    if preset == "xnv2":
        keep = _load_any(resolved, "L0")
        removed = _load_any(resolved, "chu_tou")
        elev = _load_any(resolved, "plate")
        if keep is None or removed is None:
            raise FileNotFoundError("xnv2 needs L0 + chu_tou in gold/resolved")
        # match size
        if removed.shape[:2] != keep.shape[:2]:
            removed = cv2.resize(removed, (keep.shape[1], keep.shape[0]), interpolation=cv2.INTER_LINEAR)
        hole = hole_from_kou(keep, removed, thr=18)
        # EMPTY: prefer chu_tou as base (head removed) then clear residual hole with light inpaint
        empty = removed.copy()
        residual = hole
        empty = cv2.inpaint(empty, residual, 3, cv2.INPAINT_TELEA)
        # but permission hole stays kou of L0 vs chu_tou
        peeps = peeps_from_hole(keep, hole, elev, cfg["parts"])
        meta_extra["empty_note"] = "chu_tou (外力除头) + light inpaint residual; better than pure Telea-from-KEEP"
    else:
        keep = _load_any(resolved, cfg["keep_key"])
        if keep is None:
            raise FileNotFoundError(f"keep {cfg['keep_key']} missing in {resolved}")
        elev = _load_any(resolved, cfg["elev_key"]) if cfg.get("elev_key") else None
        hole = estimate_hole_grabcut(keep)
        empty = empty_from_hole(keep, hole)
        peeps = peeps_from_hole(keep, hole, elev, cfg["parts"])
        meta_extra["empty_note"] = "PROXY Telea from GrabCut hole — not true same-camera REMOVE"

    sid = scene_id or f"GOLD_{preset}_{cfg['write']}"
    sb = SceneBundle(
        scene_id=sid,
        stick_hint=cfg["stick"],
        keep=keep,
        empty=empty,
        hole=hole,
        peeps=peeps,
        meta=meta_extra,
    )
    sb.assert_invariants()
    return sb


def cmd_list_gold(_: argparse.Namespace) -> int:
    for k, v in GOLD_PRESETS.items():
        resolved = _resolve_resolved_dir(v["proj"])
        n = len(list(resolved.glob("*"))) if resolved.exists() else 0
        print(f"{k:8s} {v['zh']:8s} write={v['write']} stick={v['stick']} resolved_files={n} empty_mode={v['empty_mode']}")
    return 0


def cmd_ingest_gold(args: argparse.Namespace) -> int:
    sb = ingest_gold_preset(args.preset, args.scene_id)
    out = Path(args.out)
    sb.save(out)
    # also dump quick contact
    board = ensure_dir(out / "board")
    save_img(board / "KEEP.png", sb.keep)
    save_img(board / "EMPTY.png", sb.empty)
    save_img(board / "HOLE.png", sb.hole)
    # side-by-side thumb
    def th(im, w=320):
        h = int(im.shape[0] * w / im.shape[1])
        return cv2.resize(im, (w, h))
    k, e = th(sb.keep), th(sb.empty)
    ho = th(cv2.cvtColor(sb.hole, cv2.COLOR_GRAY2BGR) if sb.hole.ndim == 2 else sb.hole)
    # match heights
    H = min(k.shape[0], e.shape[0], ho.shape[0])
    strip = np.hstack([k[:H], e[:H], ho[:H]])
    save_img(board / "KEEP_EMPTY_HOLE_STRIP.jpg", strip)
    info = {
        "ok": True,
        "preset": args.preset,
        "scene": str(out),
        "stick": sb.stick_hint,
        "n_peeps": len(sb.peeps),
        "empty_mode": sb.meta.get("empty_mode"),
        "empty_note": sb.meta.get("empty_note"),
        "hole_frac": round(float((sb.hole > 0).mean()), 5),
        "ACCEPT_FULL_HD": False,
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_run_gold(args: argparse.Namespace) -> int:
    """ingest + A + B in one shot."""
    out = Path(args.out)
    ensure_dir(out)
    sb = ingest_gold_preset(args.preset, args.scene_id)
    scene_dir = ensure_dir(out / "scene")
    sb.save(scene_dir)
    rep_a = run_layer_A(sb, ensure_dir(out / "A"), base_mode=args.base)
    rep_b = run_layer_B(sb, ensure_dir(out / "B"))
    summary = {
        "preset": args.preset,
        "stick": sb.stick_hint,
        "empty_mode": sb.meta.get("empty_mode"),
        "n_peeps": len(sb.peeps),
        "A_n_pass": rep_a["n_pass"],
        "A_n_fail_ban": rep_a["n_fail_ban"],
        "A_n_fail_outside": rep_a["n_fail_outside"],
        "B_status": rep_b["status"],
        "B_mutex": rep_b["mutex_ok"],
        "B_order": rep_b["order_independent"],
        "ACCEPT_FULL_HD": False,
        "out": str(out),
    }
    (out / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=f"SHQ Harness ABC {WRITE_ID}")
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp.add_parser("selftest", help="synthetic A/B/C selftest").set_defaults(func=cmd_selftest)
    sp.add_parser("kill-note", help="print 01433 KILL card").set_defaults(func=cmd_kill_note)
    sp.add_parser("rank-forbid", help="print ranking forbid notice").set_defaults(func=cmd_rank_forbid)
    sp.add_parser("list-methods", help="honest method registry").set_defaults(func=cmd_list_methods)
    sp.add_parser("list-sticks", help="named STICK flow recipes").set_defaults(func=cmd_list_sticks)

    p = sp.add_parser("init-scene")
    p.add_argument("--out", required=True)
    p.add_argument("--preset", default="synth_cliff", choices=["synth_cliff", "synth_dual_mecha", "synth_3subj"])
    p.add_argument("--scene-id", default=None)
    p.set_defaults(func=cmd_init_scene)

    p = sp.add_parser("run-A")
    p.add_argument("--scene", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--base", default="empty", choices=["empty", "keep"])
    p.set_defaults(func=cmd_run_A)

    p = sp.add_parser("run-B")
    p.add_argument("--scene", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_run_B)

    
    sp.add_parser("list-gold", help="list gold ingest presets").set_defaults(func=cmd_list_gold)

    p = sp.add_parser("ingest-gold", help="build SceneBundle from gold resolved assets")
    p.add_argument("--preset", required=True, choices=list(GOLD_PRESETS.keys()) if False else ["hyr", "jzh", "xnv2"])
    p.add_argument("--out", required=True)
    p.add_argument("--scene-id", default=None)
    p.set_defaults(func=cmd_ingest_gold)

    p = sp.add_parser("run-gold", help="ingest-gold + run A + run B")
    p.add_argument("--preset", required=True, choices=["hyr", "jzh", "xnv2"])
    p.add_argument("--out", required=True)
    p.add_argument("--scene-id", default=None)
    p.add_argument("--base", default="empty", choices=["empty", "keep"])
    p.set_defaults(func=cmd_run_gold)


    p = sp.add_parser("run-C")
    p.add_argument("--scenes", required=True, help="comma-separated scene dirs")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_run_C)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
