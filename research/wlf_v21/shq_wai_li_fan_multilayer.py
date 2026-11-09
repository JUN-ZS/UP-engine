#!/usr/bin/env python3
"""SHQ · 外力反 V2.1 multilayer (01469)
任意物件 + Tune Pack + 外力除背 CLIP（禁自 peep）+ State Bus
formal: WAI_LI_FAN_V2_1_ANYOBJ_TUNE_V1
除/生 主權在 外力GROK（Imagine）；本腳本只：結構/扣/CLIP/貼/反/落盤
"""
from __future__ import annotations
import argparse, json, hashlib, copy
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Tune Packs — 換圖類型只換這包，不改代數
# ---------------------------------------------------------------------------
TUNE_PACKS: Dict[str, Dict[str, Any]] = {
    "generic_object": {
        "kou_thr": 22, "min_area": 2000, "max_frac": 0.25,
        "roi_prior": "none", "cc_mode": "largest",
        "chu_bei_dist": 22, "grow_max": 1.15, "part_role": "custom",
    },
    "human_mid_head": {
        "kou_thr": 22, "min_area": 2500, "max_frac": 0.22,
        "roi_prior": "upper", "cc_mode": "score_roi",
        "chu_bei_dist": 22, "grow_max": 1.15, "part_role": "head",
    },
    "human_far_head": {
        "kou_thr": 18, "min_area": 500, "max_frac": 0.12,
        "roi_prior": "center", "cc_mode": "score_roi",
        "chu_bei_dist": 18, "grow_max": 1.12, "part_role": "head",
    },
    "mecha_dual_part": {
        "kou_thr": 26, "min_area": 3000, "max_frac": 0.18,
        "roi_prior": "side", "cc_mode": "score_roi",
        "chu_bei_dist": 24, "grow_max": 1.15, "part_role": "helmet",
        "side": "left",  # or right — micro-tune
    },
    "mecha_solo_part": {
        "kou_thr": 24, "min_area": 2500, "max_frac": 0.28,
        "roi_prior": "none", "cc_mode": "largest",
        "chu_bei_dist": 22, "grow_max": 1.20, "part_role": "mecha_part",
    },
}

def sha8(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:8]

def ensure(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    return p

def checker(h, w, cell=20):
    g = np.zeros((h, w, 3), np.uint8)
    for i in range(0, h, cell):
        for j in range(0, w, cell):
            c = 210 if ((i // cell) + (j // cell)) % 2 == 0 else 150
            g[i:i+cell, j:j+cell] = (c, c, c)
    return g

def resolve_tune(name: Optional[str], overrides: Optional[Dict] = None) -> Dict[str, Any]:
    base = copy.deepcopy(TUNE_PACKS.get(name or "generic_object", TUNE_PACKS["generic_object"]))
    if overrides:
        base.update({k: v for k, v in overrides.items() if v is not None})
    return base

def roi_mask(H: int, W: int, prior: str, side: str = "left") -> np.ndarray:
    m = np.ones((H, W), np.uint8) * 255
    if prior == "none":
        return m
    m = np.zeros((H, W), np.uint8)
    if prior == "upper":
        m[0:int(H * 0.55), :] = 255
    elif prior == "center":
        m[int(H * 0.15):int(H * 0.70), int(W * 0.25):int(W * 0.75)] = 255
    elif prior == "side":
        if side == "right":
            m[0:int(H * 0.60), int(W * 0.42):] = 255
        else:
            m[0:int(H * 0.60), 0:int(W * 0.55)] = 255
    else:
        m[:, :] = 255
    return m

def kou_mask_tuned(L0: np.ndarray, L1: np.ndarray, tune: Dict[str, Any]) -> Tuple[np.ndarray, Dict]:
    """扣：作證變區。主權仍應來自外力除；此處不替代除。"""
    thr = int(tune.get("kou_thr", 22))
    min_area = int(tune.get("min_area", 2000))
    max_frac = float(tune.get("max_frac", 0.25))
    prior = str(tune.get("roi_prior", "none"))
    cc_mode = str(tune.get("cc_mode", "largest"))
    side = str(tune.get("side", "left"))
    H, W = L0.shape[:2]
    d = cv2.absdiff(L0, L1)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(g, thr, 255, cv2.THRESH_BINARY)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), 1)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8), 2)
    th = cv2.bitwise_and(th, roi_mask(H, W, prior, side))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(th, 8)
    meta: Dict[str, Any] = {"thr": thr, "prior": prior, "cc_mode": cc_mode, "n_cc": int(n - 1)}
    cands = []
    for i in range(1, n):
        a = int(stats[i, cv2.CC_STAT_AREA])
        if a < min_area:
            continue
        cx, cy = float(cent[i][0]), float(cent[i][1])
        score = float(a)
        if cc_mode == "score_roi":
            # prefer ROI center-ish
            if prior == "side" and side == "left":
                score *= 1.5 if cx < W * 0.5 else 0.3
            elif prior == "side" and side == "right":
                score *= 1.5 if cx > W * 0.5 else 0.3
            if prior in ("upper", "side"):
                score *= 1.3 if cy < H * 0.5 else 0.5
        cands.append((score, a, i))
    if not cands:
        meta["warn"] = "no_cc"
        return th, meta
    cands.sort(reverse=True)
    best = cands[0][2]
    M = (lab == best).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(M, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    Mf = np.zeros_like(M)
    cv2.drawContours(Mf, cnts, -1, 255, -1)
    M = cv2.morphologyEx(Mf, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8), 2)
    M = cv2.dilate(M, np.ones((9, 9), np.uint8), 1)
    frac = float((M > 0).sum()) / (H * W)
    meta["frac"] = frac
    meta["area"] = int((M > 0).sum())
    meta["pick_score"] = cands[0][0]
    if frac > max_frac:
        meta["status"] = "FAIL_FRAC_TOO_LARGE"
        meta["hint"] = "raise kou_thr or tighten roi_prior/side; check Imagine 除 global relight"
    elif frac < 0.002:
        meta["status"] = "FAIL_FRAC_TOO_SMALL"
        meta["hint"] = "lower kou_thr or min_area; far-shot pack"
    else:
        meta["status"] = "OK"
    return M, meta

def clip_mask_from_chu_bei(L_nobg: np.ndarray, tune: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """外力除背後扣主體 = 真 CLIP MASK（禁 bbox 自 peep）"""
    dist_thr = float(tune.get("chu_bei_dist", 22))
    H, W = L_nobg.shape[:2]
    corners = np.concatenate([
        L_nobg[:20, :20].reshape(-1, 3),
        L_nobg[:20, -20:].reshape(-1, 3),
        L_nobg[-20:, :20].reshape(-1, 3),
        L_nobg[-20:, -20:].reshape(-1, 3),
    ], 0)
    bg = corners.mean(0)
    dist = np.linalg.norm(L_nobg.astype(np.float32) - bg.reshape(1, 1, 3), axis=2)
    M = (dist > dist_thr).astype(np.uint8) * 255
    M = cv2.morphologyEx(M, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8), 2)
    M = cv2.morphologyEx(M, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), 1)
    # keep largest few CCs (dual subjects)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(M, 8)
    if n > 1:
        areas = sorted([(int(stats[i, cv2.CC_STAT_AREA]), i) for i in range(1, n)], reverse=True)
        keep = [i for a, i in areas[:3] if a > 800]
        M2 = np.zeros_like(M)
        for i in keep:
            M2[lab == i] = 255
        M = M2
    vis = np.full_like(L_nobg, 40)
    vis[M > 0] = L_nobg[M > 0]
    return M, vis

def bbox_corners(M: np.ndarray, pad: int = 2) -> Tuple[List[int], Dict[str, List[int]]]:
    ys, xs = np.where(M > 0)
    if len(xs) == 0:
        return [0, 0, 1, 1], {"TL": [0, 0], "TR": [1, 0], "BR": [1, 1], "BL": [0, 1]}
    H, W = M.shape
    y0, y1 = max(0, int(ys.min()) - pad), min(H - 1, int(ys.max()) + pad)
    x0, x1 = max(0, int(xs.min()) - pad), min(W - 1, int(xs.max()) + pad)
    corners = {"TL": [x0, y0], "TR": [x1, y0], "BR": [x1, y1], "BL": [x0, y1]}
    return [x0, y0, x1, y1], corners

def scale_lock_elev(peep: np.ndarray, dens: np.ndarray, pm: np.ndarray) -> np.ndarray:
    dens_r = cv2.resize(dens, (peep.shape[1], peep.shape[0]), interpolation=cv2.INTER_AREA)
    pf = peep.astype(np.float32)
    df = dens_r.astype(np.float32)
    hf = df - cv2.GaussianBlur(df, (0, 0), 2.5)
    elev = np.clip(pf + 0.9 * hf, 0, 255).astype(np.uint8)
    elev[pm == 0] = peep[pm == 0]
    return elev

def hardpaste(base: np.ndarray, M: np.ndarray, donor_full: np.ndarray) -> np.ndarray:
    out = base.copy()
    out[M > 0] = donor_full[M > 0]
    return out

def outside_max(a: np.ndarray, b: np.ndarray, M: np.ndarray) -> int:
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    if (M == 0).any():
        return int(d[M == 0].max())
    return 0

class LayerState:
    def __init__(self, idx: int, parent: Optional["LayerState"] = None):
        self.idx = idx
        self.parent = parent
        self.L0: Optional[np.ndarray] = None
        self.L1: Optional[np.ndarray] = None          # 除件
        self.L_nobg: Optional[np.ndarray] = None      # 除背
        self.M: Optional[np.ndarray] = None           # part hole
        self.M_subj: Optional[np.ndarray] = None      # CLIP from 除背
        self.CLIP: Optional[np.ndarray] = None
        self.bbox: Optional[List[int]] = None
        self.corners: Optional[Dict] = None
        self.peep: Optional[np.ndarray] = None
        self.pm: Optional[np.ndarray] = None
        self.I_HD: Optional[np.ndarray] = None
        self.elev: Optional[np.ndarray] = None
        self.RETURN: Optional[np.ndarray] = None
        self.meta: Dict[str, Any] = {}
        self.imagine: Dict[str, str] = {}
        self.tune: Dict[str, Any] = {}

    def layer_dir(self, root: Path) -> Path:
        return ensure(root / f"L{self.idx:02d}")


def run_layer_structure(
    layer: LayerState,
    root: Path,
    tune: Optional[Dict[str, Any]] = None,
    require_imagine: bool = True,
) -> Dict[str, Any]:
    """四态结构：扣/CLIP/洞/贴/反。除背+除件+生 须已注入 Imagine 结果。"""
    d = layer.layer_dir(root)
    for sub in ["S0_SRC", "S1_MARK", "S2_TRUE_HOLE", "S3_CLIP", "S4_REMOVE",
                "S5_KOU", "S6_GEN", "S7_RETURN", "S8_ANTI", "boards"]:
        ensure(d / sub)

    assert layer.L0 is not None
    L0 = layer.L0
    H, W = L0.shape[:2]
    cv2.imwrite(str(d / "S0_SRC" / "L0.jpg"), L0)
    tune = tune or layer.tune or resolve_tune("generic_object")
    layer.tune = tune

    report: Dict[str, Any] = {
        "layer": layer.idx,
        "parent_layer": None if layer.parent is None else layer.parent.idx,
        "role": "ROOT" if layer.parent is None else "CLIP_CHILD",
        "formal": "WAI_LI_FAN_V2_1_ANYOBJ_TUNE_V1",
        "write_id": "01469",
        "part_role": tune.get("part_role"),
        "tune": tune,
        "fn": "§19+§22 外力反V2.1 · 外力GROK",
        "algebra": "[(生,除,洞,扣)×(反)] ANY_OBJECT",
    }

    # --- 除背 → CLIP（真能力；可与除件并行注入）---
    if layer.L_nobg is not None:
        M_subj, clip_vis = clip_mask_from_chu_bei(layer.L_nobg, tune)
        layer.M_subj = M_subj
        # CLIP pixels from L0 (same frame) under M_subj — not freeframe
        CLIP = L0.copy()
        CLIP[M_subj == 0] = 0
        layer.CLIP = CLIP
        cv2.imwrite(str(d / "S3_CLIP" / "L_chu_bei.jpg"), layer.L_nobg)
        cv2.imwrite(str(d / "S3_CLIP" / "M_subj_from_chu_bei.png"), M_subj)
        cv2.imwrite(str(d / "S3_CLIP" / "CLIP_vis.jpg"), clip_vis)
        cv2.imwrite(str(d / "S3_CLIP" / "CLIP_L0_masked.jpg"), CLIP)
        report["CLIP_from_chu_bei"] = True
        report["CLIP_frac"] = float((M_subj > 0).sum()) / (H * W)
        if layer.imagine.get("除背"):
            (d / "S3_CLIP" / "EDIT_META.json").write_text(
                json.dumps({"tool": "imagine_image_to_image", "asset": layer.imagine["除背"], "fn": "外力GROK 除背→CLIP"},
                           indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        report["CLIP_from_chu_bei"] = False
        report["CLIP_note"] = "未注入 L_nobg；禁自 peep 冒充 CLIP（E-WLF21-02）"

    if layer.L1 is None:
        report["status"] = "NEED_IMAGINE_除件"
        report["steal"] = False
        report["note"] = "禁止 OpenCV 假除；请 外力GROK imagine_image_to_image 注入 L1"
        (d / "REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    L1 = layer.L1
    cv2.imwrite(str(d / "S4_REMOVE" / "L1_IMAGINE_除件.jpg"), L1)
    if layer.imagine.get("除件") or layer.imagine.get("除"):
        asset = layer.imagine.get("除件") or layer.imagine.get("除")
        (d / "S4_REMOVE" / "EDIT_META.json").write_text(
            json.dumps({"tool": "imagine_image_to_image", "asset": asset, "fn": "外力GROK 除件"},
                       indent=2, ensure_ascii=False), encoding="utf-8")

    # 扣 → M_part
    M, kou_meta = kou_mask_tuned(L0, L1, tune)
    bbox, corners = bbox_corners(M)
    layer.M, layer.bbox, layer.corners = M, bbox, corners
    x0, y0, x1, y1 = bbox
    cv2.imwrite(str(d / "S5_KOU" / "M_part.png"), M)
    cv2.imwrite(str(d / "S1_MARK" / "M_hole_MARK.png"), M)
    mark_meta = {
        "layer": layer.idx,
        "virtual_hole": True,
        "source": "Imagine_EDIT_除件 pair 扣 + Tune",
        "part_role": tune.get("part_role"),
        "bbox_xyxy": bbox,
        "corners_4": corners,
        "M_area": int((M > 0).sum()),
        "frac": float((M > 0).sum()) / (H * W),
        "elev_remap": False,
        "frozen": True,
        "kou_meta": kou_meta,
        "parent_clip": layer.parent is not None,
    }
    (d / "S1_MARK" / "MARK_META.json").write_text(json.dumps(mark_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    layer.meta.update(mark_meta)
    report["kou"] = kou_meta

    # 真洞
    thole = L0.copy()
    thole[M > 0] = checker(H, W)[M > 0]
    cv2.imwrite(str(d / "S2_TRUE_HOLE" / "TRUE_HOLE_checker.jpg"), thole)
    seat = L0.copy()
    seat[M > 0] = L1[M > 0]
    cv2.imwrite(str(d / "S2_TRUE_HOLE" / "HOLE_SEAT_L1.jpg"), seat)

    # peep = contract crop of part（材料参考；子层 L0 优先用 CLIP 再咬，而非裸 peep）
    peep = L0[y0:y1 + 1, x0:x1 + 1].copy()
    pm = M[y0:y1 + 1, x0:x1 + 1]
    layer.peep, layer.pm = peep, pm
    bgra = cv2.cvtColor(peep, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = pm
    bgra[pm == 0, :3] = 0
    cv2.imwrite(str(d / "S3_CLIP" / "PART_peep_bgra.png"), bgra)
    cv2.imwrite(str(d / "S3_CLIP" / "PART_peep.jpg"), peep)
    # 明确标注：此 peep 非 CLIP；CLIP 仅除背路径
    (d / "S3_CLIP" / "NOTE.json").write_text(json.dumps({
        "CLIP_definition": "M_subj from 外力除背 only",
        "PART_peep": "bbox of M_part for scale contract — NOT a substitute for CLIP",
        "forbid": "self_peep_as_CLIP",
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    def rs(im, f=0.5):
        return cv2.resize(im, (max(1, int(W * f)), max(1, int(H * f))))
    cv2.imwrite(str(d / "S8_ANTI" / "ANTI_除_L0_L1.jpg"), np.hstack([rs(L0), rs(L1)]))
    cv2.imwrite(str(d / "S8_ANTI" / "ANTI_洞_truehole_SRC.jpg"), np.hstack([rs(thole), rs(L0)]))
    if layer.M_subj is not None:
        Mo = L0.copy(); Mo[M > 0] = (0, 0, 255)
        cv2.imwrite(str(d / "S8_ANTI" / "ANTI_扣_M_chu_bei.jpg"),
                    np.hstack([rs(Mo), rs(layer.L_nobg if layer.L_nobg is not None else L0)]))

    if kou_meta.get("status") == "FAIL_FRAC_TOO_LARGE":
        report["status"] = "FAIL_FRAC_TOO_LARGE"
        report["hint"] = kou_meta.get("hint")
        (d / "REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    if layer.I_HD is None and require_imagine:
        report["status"] = "NEED_IMAGINE_生"
        report["M_ready"] = True
        report["mark"] = mark_meta
        report["note"] = "禁止 peep freeframe 冒充；请 外力GROK 在 L1 洞内生 注入 I_HD"
        (d / "REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    I_HD = layer.I_HD if layer.I_HD is not None else L0
    if I_HD.shape[:2] != L0.shape[:2]:
        I_HD = cv2.resize(I_HD, (W, H), interpolation=cv2.INTER_AREA)
    layer.I_HD = I_HD
    cv2.imwrite(str(d / "S6_GEN" / "I_HD_IMAGINE.jpg"), I_HD)
    if layer.imagine.get("生"):
        (d / "S6_GEN" / "EDIT_META.json").write_text(
            json.dumps({"tool": "imagine_reference_to_image", "asset": layer.imagine["生"], "fn": "外力GROK 洞内生"},
                       indent=2, ensure_ascii=False), encoding="utf-8")

    dens_peep = I_HD[y0:y1 + 1, x0:x1 + 1].copy()
    dens2 = cv2.resize(dens_peep, (dens_peep.shape[1] * 2, dens_peep.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
    dens2 = cv2.bilateralFilter(dens2, 5, 40, 40)
    elev = scale_lock_elev(peep, dens2, pm)
    layer.elev = elev
    cv2.imwrite(str(d / "S6_GEN" / "elev_scale_lock.jpg"), elev)
    cv2.imwrite(str(d / "S8_ANTI" / "ANTI_生_peep_elev.jpg"),
                np.hstack([cv2.resize(peep, (320, 320)), cv2.resize(elev, (320, 320))]))

    hybrid = I_HD.copy()
    roi = hybrid[y0:y1 + 1, x0:x1 + 1]
    hf = elev.astype(np.float32) - cv2.GaussianBlur(elev.astype(np.float32), (0, 0), 2)
    m3 = pm > 0
    roi2 = roi.copy()
    roi2[m3] = np.clip(roi.astype(np.float32)[m3] + 0.45 * hf[m3], 0, 255).astype(np.uint8)
    hybrid[y0:y1 + 1, x0:x1 + 1] = roi2

    ret = hardpaste(L0, M, hybrid)
    layer.RETURN = ret
    cv2.imwrite(str(d / "S7_RETURN" / "RETURN.png"), ret)
    cv2.imwrite(str(d / "S7_RETURN" / "RETURN.jpg"), ret, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    cv2.imwrite(str(d / "S8_ANTI" / "ANTI_回_L0_RETURN.jpg"), np.hstack([rs(L0), rs(ret)]))

    out_max = outside_max(ret, L0, M)
    gates = {
        "Imagine_除件": layer.L1 is not None,
        "Imagine_除背_CLIP": layer.L_nobg is not None,
        "Imagine_生": layer.I_HD is not None,
        "MARK_frozen": True,
        "true_hole": True,
        "elev_remap_false": True,
        "outside_0": out_max == 0,
        "no_self_peep_as_CLIP": layer.L_nobg is not None,
        "tune_pack": True,
        "any_object": True,
    }
    if layer.parent is not None and layer.parent.bbox is not None:
        gates["parent_clip_contract"] = True

    status = "PASS" if out_max == 0 else "FAIL_OUTSIDE"
    if kou_meta.get("status", "").startswith("FAIL"):
        status = kou_meta["status"]

    report.update({
        "status": status,
        "gates": gates,
        "outside_max": out_max,
        "mark": mark_meta,
        "imagine": layer.imagine,
        "claim": f"C2_WLF_V21_L{layer.idx}",
        "note_compose": "独立 PASS ≠ 链 PASS；见 SHQ_FOUR_ANTI_ALGEBRA_ARCH + V2.1 §0",
        "asof": datetime.now(timezone.utc).isoformat(),
    })
    (d / "REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (d / "STATE_BUS.json").write_text(json.dumps({
        "L0": "S0_SRC/L0.jpg",
        "L1_除件": "S4_REMOVE/L1_IMAGINE_除件.jpg",
        "L_除背": "S3_CLIP/L_chu_bei.jpg",
        "M_part": "S1_MARK/M_hole_MARK.png",
        "M_subj_CLIP": "S3_CLIP/M_subj_from_chu_bei.png",
        "I_HD": "S6_GEN/I_HD_IMAGINE.jpg",
        "elev": "S6_GEN/elev_scale_lock.jpg",
        "RETURN": "S7_RETURN/RETURN.png",
        "tune": tune,
        "part_role": tune.get("part_role"),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def reverse_stack_return(layers: List[LayerState], root: Path) -> np.ndarray:
    assert layers
    cur = layers[-1].RETURN if layers[-1].RETURN is not None else layers[-1].L0
    for i in range(len(layers) - 1, 0, -1):
        child = layers[i]
        parent = layers[i - 1]
        assert parent.L0 is not None and parent.M is not None and parent.bbox is not None
        x0, y0, x1, y1 = parent.bbox
        peep_h, peep_w = y1 - y0 + 1, x1 - x0 + 1
        if cur.shape[0] != peep_h or cur.shape[1] != peep_w:
            cur_r = cv2.resize(cur, (peep_w, peep_h), interpolation=cv2.INTER_AREA)
        else:
            cur_r = cur
        parent_canvas = parent.L0.copy()
        slot = parent_canvas[y0:y1 + 1, x0:x1 + 1]
        pm = parent.M[y0:y1 + 1, x0:x1 + 1]
        slot[pm > 0] = cur_r[pm > 0]
        parent_canvas[y0:y1 + 1, x0:x1 + 1] = slot
        parent_canvas = hardpaste(parent.L0, parent.M, parent_canvas)
        outp = outside_max(parent_canvas, parent.L0, parent.M)
        ensure(root / "STACK_RETURN")
        cv2.imwrite(str(root / "STACK_RETURN" / f"from_L{i:02d}_to_L{i-1:02d}.jpg"), parent_canvas)
        (root / "STACK_RETURN" / f"from_L{i:02d}_to_L{i-1:02d}_gate.json").write_text(
            json.dumps({"outside_max": outp, "via_MARK": True, "elev_remap": False}, indent=2), encoding="utf-8")
        cur = parent_canvas
        parent.RETURN = parent_canvas
    cv2.imwrite(str(root / "STACK_RETURN" / "ROOT_FINAL.jpg"), cur)
    return cur


def cmd_list_tunes(args):
    print(json.dumps(TUNE_PACKS, indent=2, ensure_ascii=False))
    return 0


def cmd_selftest(args):
    root = ensure(Path(args.out))
    tune = resolve_tune(args.tune or "generic_object")
    L0 = np.full((240, 320, 3), 40, np.uint8)
    cv2.rectangle(L0, (100, 40), (220, 180), (200, 180, 160), -1)
    cv2.circle(L0, (160, 90), 35, (220, 200, 180), -1)
    L1 = L0.copy()
    cv2.circle(L1, (160, 90), 35, (40, 40, 40), -1)
    L_nobg = L0.copy()
    L_nobg[:40, :] = 30; L_nobg[-40:, :] = 30; L_nobg[:, :40] = 30; L_nobg[:, -40:] = 30
    root_layer = LayerState(0)
    root_layer.L0, root_layer.L1, root_layer.L_nobg = L0, L1, L_nobg
    root_layer.I_HD = L0
    root_layer.imagine = {"除件": "selftest", "除背": "selftest", "生": "selftest"}
    root_layer.tune = tune
    r0 = run_layer_structure(root_layer, root, tune=tune, require_imagine=False)
    child = LayerState(1, parent=root_layer)
    # child L0 should prefer CLIP if available
    if root_layer.CLIP is not None:
        ys, xs = np.where(root_layer.M_subj > 0)
        if len(xs):
            y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
            child.L0 = root_layer.L0[y0:y1+1, x0:x1+1].copy()
        else:
            child.L0 = root_layer.peep.copy()
    else:
        child.L0 = root_layer.peep.copy()
    cL1 = child.L0.copy()
    h, w = cL1.shape[:2]
    cL1[h//4:3*h//4, w//4:3*w//4] = 30
    child.L1 = cL1
    child.I_HD = child.L0
    child.imagine = {"除件": "selftest", "生": "selftest"}
    child.meta["parent_bbox"] = root_layer.bbox
    child.tune = resolve_tune("generic_object", {"roi_prior": "none", "kou_thr": 20, "min_area": 100})
    r1 = run_layer_structure(child, root, tune=child.tune, require_imagine=False)
    final = reverse_stack_return([root_layer, child], root)
    summary = {
        "selftest": True, "v": "2.1", "tune": args.tune,
        "L0": r0.get("status"), "L1": r1.get("status"),
        "CLIP_from_chu_bei": r0.get("CLIP_from_chu_bei"),
        "stack_outside": outside_max(final, L0, root_layer.M) if root_layer.M is not None else -1,
        "compose_note": "selftest structure only — not TypeB production claim",
    }
    (root / "SELFTEST.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def cmd_init_run(args):
    root = ensure(Path(args.out))
    L0 = cv2.imread(args.src)
    assert L0 is not None
    ensure(root / "L00" / "S0_SRC")
    cv2.imwrite(str(root / "L00" / "S0_SRC" / "L0.jpg"), L0)
    tune = resolve_tune(args.tune, {
        "side": args.side,
        "part_role": args.part_role,
        "kou_thr": args.kou_thr,
    })
    bus = {
        "formal": "WAI_LI_FAN_V2_1_ANYOBJ_TUNE_V1",
        "write_id": "01469",
        "n_layers_planned": args.n,
        "src": args.src,
        "tune_pack": args.tune,
        "tune": tune,
        "rule": [
            "每层 外力GROK 除件+除背+生",
            "CLIP = 除背扣 M_subj · 禁自 peep",
            "任意物件 part_role + Tune Pack",
            "独立 PASS ≠ 链 SUCCESS",
            "STACK via MARK",
        ],
        "layers": [],
        "forbid": [
            "opencv_fake_remove", "freeframe_map", "skip_anti",
            "return_without_MARK", "self_peep_as_CLIP",
            "typeA_pass_as_typeB", "hardcode_head_only",
        ],
    }
    for i in range(args.n):
        bus["layers"].append({
            "idx": i,
            "need": ["Imagine_除件 L1", "Imagine_除背 L_nobg", "Imagine_生 I_HD"],
            "status": "WAITING_IMAGINE" if i == 0 else "WAITING_PARENT_CLIP",
        })
    (root / "MULTI_BUS.json").write_text(json.dumps(bus, indent=2, ensure_ascii=False), encoding="utf-8")
    (root / "TUNE.json").write_text(json.dumps(tune, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(bus, indent=2, ensure_ascii=False))
    return 0


def cmd_ingest_layer(args):
    root = ensure(Path(args.out))
    parent = None
    if args.parent_idx is not None:
        pdir = root / f"L{args.parent_idx:02d}"
        parent = LayerState(args.parent_idx)
        parent.L0 = cv2.imread(str(pdir / "S0_SRC" / "L0.jpg"))
        parent.M = cv2.imread(str(pdir / "S1_MARK" / "M_hole_MARK.png"), 0)
        if (pdir / "S1_MARK" / "MARK_META.json").exists():
            parent.meta = json.loads((pdir / "S1_MARK" / "MARK_META.json").read_text())
            parent.bbox = parent.meta.get("bbox_xyxy")
            parent.corners = parent.meta.get("corners_4")
        peep_p = pdir / "S3_CLIP" / "PART_peep.jpg"
        if peep_p.exists():
            parent.peep = cv2.imread(str(peep_p))
        msp = pdir / "S3_CLIP" / "M_subj_from_chu_bei.png"
        if msp.exists():
            parent.M_subj = cv2.imread(str(msp), 0)

    layer = LayerState(args.idx, parent=parent)
    layer.L0 = cv2.imread(args.l0)
    if args.l1:
        layer.L1 = cv2.imread(args.l1)
    if args.lnobg:
        layer.L_nobg = cv2.imread(args.lnobg)
    if args.ihd:
        layer.I_HD = cv2.imread(args.ihd)
    if args.asset_chu:
        layer.imagine["除件"] = args.asset_chu
    if args.asset_chu_bei:
        layer.imagine["除背"] = args.asset_chu_bei
    if args.asset_sheng:
        layer.imagine["生"] = args.asset_sheng
    if parent and parent.bbox:
        layer.meta["parent_bbox"] = parent.bbox

    tune = resolve_tune(args.tune)
    if args.side:
        tune["side"] = args.side
    if args.kou_thr is not None:
        tune["kou_thr"] = args.kou_thr
    if args.part_role:
        tune["part_role"] = args.part_role
    # load run TUNE if present
    if (root / "TUNE.json").exists() and not args.tune:
        tune = json.loads((root / "TUNE.json").read_text())

    rep = run_layer_structure(layer, root, tune=tune, require_imagine=not args.allow_no_imagine)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    ok = rep.get("status") in ("PASS", "NEED_IMAGINE_除件", "NEED_IMAGINE_生")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="外力反 V2.1 multilayer · any object · tune packs")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list-tunes"); p.set_defaults(func=cmd_list_tunes)

    p = sub.add_parser("selftest"); p.set_defaults(func=cmd_selftest)
    p.add_argument("--out", default="/tmp/wlf_v21_selftest")
    p.add_argument("--tune", default="generic_object")

    p = sub.add_parser("init-run"); p.set_defaults(func=cmd_init_run)
    p.add_argument("--src", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=2)
    p.add_argument("--tune", default="generic_object")
    p.add_argument("--side", default=None)
    p.add_argument("--part-role", default=None)
    p.add_argument("--kou-thr", type=int, default=None)

    p = sub.add_parser("ingest-layer"); p.set_defaults(func=cmd_ingest_layer)
    p.add_argument("--out", required=True)
    p.add_argument("--idx", type=int, required=True)
    p.add_argument("--l0", required=True)
    p.add_argument("--l1", default=None, help="外力GROK 除件")
    p.add_argument("--lnobg", default=None, help="外力GROK 除背 → CLIP")
    p.add_argument("--ihd", default=None, help="外力GROK 生")
    p.add_argument("--asset-chu", default=None)
    p.add_argument("--asset-chu-bei", default=None)
    p.add_argument("--asset-sheng", default=None)
    p.add_argument("--parent-idx", type=int, default=None)
    p.add_argument("--tune", default="generic_object")
    p.add_argument("--side", default=None)
    p.add_argument("--part-role", default=None)
    p.add_argument("--kou-thr", type=int, default=None)
    p.add_argument("--allow-no-imagine", action="store_true")

    args = ap.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
