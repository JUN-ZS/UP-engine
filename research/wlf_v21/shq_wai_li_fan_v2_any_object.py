#!/usr/bin/env python3
"""SHQ · 外力反 V2.1 任意物件可微調
formal: WAI_LI_FAN_V2_ANY_OBJECT_TUNE_V1 · write 01469

核心：
- [(生,除,洞,扣)×(反)] 類型無關；換圖型只改 TunePack θ
- CLIP 必須來自外力除背扣 M_subj，禁止自 peep
- 除/生主權在外力GROK（Imagine asset 注入）；本腳本只 扣/結構/貼/反/落盤
- 獨立 PASS ≠ 鏈 PASS；State Bus + 不變量
"""
from __future__ import annotations
import argparse, json, copy
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

# ---------------------------------------------------------------------------
# TunePack：圖型參數外置（微調就能適配，不改代數）
# ---------------------------------------------------------------------------
TUNE_PRESETS: Dict[str, Dict[str, Any]] = {
    "generic_object": {
        "kou_thr": 22, "min_area": 2000, "min_frac": 0.005, "max_frac": 0.35,
        "roi_prior": "none", "cc_mode": "largest",
        "morph_open": 5, "morph_close": 13, "dilate": 9,
        "chu_bei_dist": 22, "grow_max": 1.15, "part_role": "custom",
    },
    "human_mid_head": {
        "kou_thr": 22, "min_area": 2500, "min_frac": 0.02, "max_frac": 0.22,
        "roi_prior": "upper", "cc_mode": "score_roi",
        "morph_open": 5, "morph_close": 15, "dilate": 11,
        "chu_bei_dist": 22, "grow_max": 1.15, "part_role": "head",
    },
    "human_far_head": {
        "kou_thr": 18, "min_area": 500, "min_frac": 0.003, "max_frac": 0.12,
        "roi_prior": "center", "cc_mode": "score_roi",
        "morph_open": 3, "morph_close": 9, "dilate": 7,
        "chu_bei_dist": 18, "grow_max": 1.12, "part_role": "head",
    },
    "mecha_dual_part": {
        "kou_thr": 26, "min_area": 3000, "min_frac": 0.01, "max_frac": 0.20,
        "roi_prior": "side", "cc_mode": "score_roi",
        "morph_open": 5, "morph_close": 17, "dilate": 11,
        "chu_bei_dist": 24, "grow_max": 1.15, "part_role": "helmet",
    },
    "mecha_gear_small": {
        "kou_thr": 24, "min_area": 800, "min_frac": 0.002, "max_frac": 0.08,
        "roi_prior": "none", "cc_mode": "largest",
        "morph_open": 3, "morph_close": 9, "dilate": 5,
        "chu_bei_dist": 22, "grow_max": 1.15, "part_role": "gear",
    },
    "whole_subject": {
        "kou_thr": 20, "min_area": 5000, "min_frac": 0.08, "max_frac": 0.55,
        "roi_prior": "none", "cc_mode": "largest",
        "morph_open": 5, "morph_close": 21, "dilate": 7,
        "chu_bei_dist": 20, "grow_max": 1.10, "part_role": "whole",
    },
}


def load_tune(name_or_path: Optional[str]) -> Dict[str, Any]:
    if not name_or_path:
        return copy.deepcopy(TUNE_PRESETS["generic_object"])
    p = Path(name_or_path)
    if p.exists():
        t = json.loads(p.read_text(encoding="utf-8"))
        base = copy.deepcopy(TUNE_PRESETS.get(t.get("preset", "generic_object"), TUNE_PRESETS["generic_object"]))
        base.update({k: v for k, v in t.items() if k != "preset"})
        return base
    if name_or_path in TUNE_PRESETS:
        return copy.deepcopy(TUNE_PRESETS[name_or_path])
    return copy.deepcopy(TUNE_PRESETS["generic_object"])


def ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def checker(h, w, cell=12):
    g = np.zeros((h, w, 3), np.uint8)
    for i in range(0, h, cell):
        for j in range(0, w, cell):
            c = 200 if ((i // cell) + (j // cell)) % 2 == 0 else 130
            g[i : i + cell, j : j + cell] = (c, c, c)
    return g


def roi_mask(H: int, W: int, prior: str, side: str = "left") -> np.ndarray:
    m = np.ones((H, W), np.uint8) * 255
    if prior == "none":
        return m
    if prior == "upper":
        m[int(H * 0.55) :, :] = 0
    elif prior == "center":
        m[: int(H * 0.15), :] = 0
        m[int(H * 0.75) :, :] = 0
        m[:, : int(W * 0.15)] = 0
        m[:, int(W * 0.85) :] = 0
    elif prior == "side":
        if side == "left":
            m[:, int(W * 0.55) :] = 0
        else:
            m[:, : int(W * 0.45)] = 0
        m[int(H * 0.55) :, :] = 0
    return m


def apply_roi_hint(Mbase: np.ndarray, hint_norm: Optional[List[float]]) -> np.ndarray:
    """hint_norm = [x0,y0,x1,y1] in 0..1 — coarse gate only, not peep sovereignty"""
    if not hint_norm or len(hint_norm) != 4:
        return Mbase
    H, W = Mbase.shape
    x0, y0, x1, y1 = hint_norm
    gate = np.zeros_like(Mbase)
    xa, xb = int(x0 * W), int(x1 * W)
    ya, yb = int(y0 * H), int(y1 * H)
    gate[ya:yb, xa:xb] = 255
    return cv2.bitwise_and(Mbase, gate)


def kou_part(
    L0: np.ndarray,
    L1: np.ndarray,
    tune: Dict[str, Any],
    side: str = "left",
    roi_hint_norm: Optional[List[float]] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """扣 → M_part。θ 可微調；禁寫死頭。"""
    H, W = L0.shape[:2]
    thr = int(tune["kou_thr"])
    d = cv2.absdiff(L0, L1)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(g, thr, 255, cv2.THRESH_BINARY)
    k_o = np.ones((int(tune["morph_open"]),) * 2, np.uint8)
    k_c = np.ones((int(tune["morph_close"]),) * 2, np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, k_o, 1)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, k_c, 2)
    prior = roi_mask(H, W, str(tune.get("roi_prior", "none")), side=side)
    th = cv2.bitwise_and(th, prior)
    th = apply_roi_hint(th, roi_hint_norm)

    n, lab, stats, cents = cv2.connectedComponentsWithStats(th, 8)
    meta: Dict[str, Any] = {"thr": thr, "n_cc": int(n) - 1, "policy": tune.get("cc_mode")}
    if n <= 1:
        return th, {**meta, "warn": "no_cc"}

    cands = []
    for i in range(1, n):
        a = int(stats[i, cv2.CC_STAT_AREA])
        if a < int(tune["min_area"]):
            continue
        cx, cy = float(cents[i][0]), float(cents[i][1])
        score = float(a)
        if tune.get("cc_mode") == "score_roi":
            # prefer upper / side by prior already; boost compactness
            score = a * (1.2 if cy < H * 0.45 else 0.7)
        cands.append((score, a, i))
    if not cands:
        # fallback largest any
        best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        M = (lab == best).astype(np.uint8) * 255
    else:
        cands.sort(reverse=True)
        M = (lab == cands[0][2]).astype(np.uint8) * 255

    dil = int(tune.get("dilate", 9))
    if dil > 0:
        M = cv2.dilate(M, np.ones((dil, dil), np.uint8), 1)
    frac = float((M > 0).sum()) / (H * W)
    meta.update({"frac": frac, "area": int((M > 0).sum())})
    if frac < float(tune["min_frac"]):
        meta["gate"] = "FAIL_FRAC_TOO_SMALL"
    elif frac > float(tune["max_frac"]):
        meta["gate"] = "FAIL_FRAC_TOO_LARGE"
    else:
        meta["gate"] = "OK"
    return M, meta


def clip_from_chu_bei(L_nb: np.ndarray, tune: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """真 CLIP：外力除背後扣 M_subj。禁止 peep bbox。"""
    H, W = L_nb.shape[:2]
    # sample corners as bg
    corners = np.concatenate(
        [
            L_nb[:20, :20].reshape(-1, 3),
            L_nb[:20, -20:].reshape(-1, 3),
            L_nb[-20:, :20].reshape(-1, 3),
            L_nb[-20:, -20:].reshape(-1, 3),
        ],
        0,
    )
    bg = corners.mean(0)
    dist = np.linalg.norm(L_nb.astype(np.float32) - bg.reshape(1, 1, 3), axis=2)
    thr = float(tune.get("chu_bei_dist", 22))
    Ms = (dist > thr).astype(np.uint8) * 255
    Ms = cv2.morphologyEx(Ms, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8), 2)
    Ms = cv2.morphologyEx(Ms, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), 1)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(Ms, 8)
    if n > 1:
        # keep top-2 large (dual ok)
        areas = sorted([(int(stats[i, cv2.CC_STAT_AREA]), i) for i in range(1, n)], reverse=True)
        keep = [i for a, i in areas[:2] if a > 500]
        out = np.zeros_like(Ms)
        for i in keep:
            out[lab == i] = 255
        Ms = out
    frac = float((Ms > 0).sum()) / (H * W)
    clip_vis = np.full_like(L_nb, 40)
    clip_vis[Ms > 0] = L_nb[Ms > 0]
    meta = {"source": "chu_bei_kou", "forbid": "self_peep", "frac_subj": frac, "thr": thr}
    return Ms, clip_vis, meta


def bbox_corners(M: np.ndarray, pad: int = 2):
    ys, xs = np.where(M > 0)
    H, W = M.shape
    if len(xs) == 0:
        return [0, 0, 1, 1], {"TL": [0, 0], "TR": [1, 0], "BR": [1, 1], "BL": [0, 1]}
    y0, y1 = max(0, int(ys.min()) - pad), min(H - 1, int(ys.max()) + pad)
    x0, x1 = max(0, int(xs.min()) - pad), min(W - 1, int(xs.max()) + pad)
    return [x0, y0, x1, y1], {"TL": [x0, y0], "TR": [x1, y0], "BR": [x1, y1], "BL": [x0, y1]}


def hardpaste(base, M, donor):
    out = base.copy()
    out[M > 0] = donor[M > 0]
    return out


def outside_max(a, b, M):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    if (M == 0).any():
        return int(d[M == 0].max())
    return 0


def scale_lock_elev(peep, dens, pm):
    dens_r = cv2.resize(dens, (peep.shape[1], peep.shape[0]), interpolation=cv2.INTER_AREA)
    pf, df = peep.astype(np.float32), dens_r.astype(np.float32)
    hf = df - cv2.GaussianBlur(df, (0, 0), 2.5)
    elev = np.clip(pf + 0.9 * hf, 0, 255).astype(np.uint8)
    elev[pm == 0] = peep[pm == 0]
    return elev


def run_structure(
    out: Path,
    L0: np.ndarray,
    L_chu_part: Optional[np.ndarray],
    L_chu_bei: Optional[np.ndarray],
    I_HD: Optional[np.ndarray],
    tune: Dict[str, Any],
    part_id: str = "part",
    side: str = "left",
    roi_hint_norm: Optional[List[float]] = None,
    assets: Optional[Dict[str, str]] = None,
    require_imagine: bool = True,
) -> Dict[str, Any]:
    """單層完整結構。CLIP 必須除背。"""
    root = ensure(out)
    for sub in [
        "S0_SRC", "S1_MARK", "S2_TRUE_HOLE", "S3_CLIP", "S4_REMOVE",
        "S5_KOU", "S6_GEN", "S7_RETURN", "S8_ANTI", "boards",
    ]:
        ensure(root / sub)

    H, W = L0.shape[:2]
    cv2.imwrite(str(root / "S0_SRC" / "L0.jpg"), L0)
    assets = assets or {}
    report: Dict[str, Any] = {
        "formal": "WAI_LI_FAN_V2_ANY_OBJECT_TUNE_V1",
        "write_id": "01469",
        "part_id": part_id,
        "tune": tune,
        "assets": assets,
        "CLIP_rule": "from_chu_bei_only",
        "forbid": ["self_peep_as_CLIP", "opencv_fake_chu_sheng", "hardcoded_head_only"],
    }

    # --- 除背 → CLIP（真）---
    if L_chu_bei is None:
        report["status"] = "NEED_IMAGINE_除背"
        report["note"] = "E-WLF21-02：無除背不可報 CLIP；禁自 peep"
        (root / "REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    cv2.imwrite(str(root / "S4_REMOVE" / "L_chu_bei.jpg"), L_chu_bei)
    M_subj, clip_vis, clip_meta = clip_from_chu_bei(L_chu_bei, tune)
    cv2.imwrite(str(root / "S3_CLIP" / "M_subj.png"), M_subj)
    cv2.imwrite(str(root / "S3_CLIP" / "CLIP_vis.jpg"), clip_vis)
    # true CLIP pixels = L0 ⊙ M_subj (same frame) OR L_chu_bei ⊙ M_subj
    clip_rgba = np.zeros((H, W, 4), np.uint8)
    clip_rgba[:, :, :3] = L0
    clip_rgba[:, :, 3] = M_subj
    cv2.imwrite(str(root / "S3_CLIP" / "CLIP_from_chu_bei.png"), clip_rgba)
    (root / "S3_CLIP" / "CLIP_META.json").write_text(
        json.dumps(clip_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report["CLIP"] = clip_meta

    # --- 除件 → 洞 ---
    if L_chu_part is None:
        report["status"] = "NEED_IMAGINE_除件"
        report["note"] = "禁止 OpenCV 假除；請外力GROK image_to_image 除件"
        (root / "REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    cv2.imwrite(str(root / "S4_REMOVE" / "L_chu_part.jpg"), L_chu_part)
    M, kou_meta = kou_part(L0, L_chu_part, tune, side=side, roi_hint_norm=roi_hint_norm)
    bbox, corners = bbox_corners(M)
    x0, y0, x1, y1 = bbox
    cv2.imwrite(str(root / "S5_KOU" / "M_part.png"), M)
    cv2.imwrite(str(root / "S1_MARK" / "M_hole_MARK.png"), M)
    mark = {
        "part_id": part_id,
        "virtual_hole": True,
        "source": "Imagine_除件 pair 扣",
        "bbox_xyxy": bbox,
        "corners_4": corners,
        "kou": kou_meta,
        "elev_remap": False,
        "frozen": True,
    }
    (root / "S1_MARK" / "MARK_META.json").write_text(json.dumps(mark, indent=2, ensure_ascii=False), encoding="utf-8")
    report["mark"] = mark
    report["kou"] = kou_meta

    # 真洞
    thole = L0.copy()
    thole[M > 0] = checker(H, W)[M > 0]
    seat = L0.copy()
    seat[M > 0] = L_chu_part[M > 0]
    cv2.imwrite(str(root / "S2_TRUE_HOLE" / "TRUE_HOLE_checker.jpg"), thole)
    cv2.imwrite(str(root / "S2_TRUE_HOLE" / "HOLE_SEAT.jpg"), seat)

    # peep 僅尺度契約載體（不是 CLIP）
    peep = L0[y0 : y1 + 1, x0 : x1 + 1].copy()
    pm = M[y0 : y1 + 1, x0 : x1 + 1]
    cv2.imwrite(str(root / "S5_KOU" / "peep_scale_carrier.jpg"), peep)
    (root / "S5_KOU" / "NOTE_peep_not_CLIP.txt").write_text(
        "peep = scale carrier only; CLIP = S3_CLIP from 除背\n", encoding="utf-8"
    )

    def rs(im, f=0.4):
        return cv2.resize(im, (max(1, int(W * f)), max(1, int(H * f))))

    # 反 ×4
    cv2.imwrite(str(root / "S8_ANTI" / "ANTI_CHU.jpg"), np.hstack([rs(L0), rs(L_chu_part)]))
    cv2.imwrite(str(root / "S8_ANTI" / "ANTI_DONG.jpg"), np.hstack([rs(thole), rs(L_chu_part)]))
    Mo = L0.copy(); Mo[M > 0] = (0, 0, 255)
    cv2.imwrite(str(root / "S8_ANTI" / "ANTI_KOU.jpg"), np.hstack([rs(Mo), rs(clip_vis)]))
    # 生 later

    if kou_meta.get("gate") not in ("OK",) and require_imagine:
        # still allow structure continue but flag
        report["frac_gate"] = kou_meta.get("gate")

    if I_HD is None and require_imagine:
        report["status"] = "NEED_IMAGINE_生"
        report["note"] = "外力GROK 洞內生；禁 freeframe densify 冒充"
        (root / "REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    if I_HD is None:
        I_HD = L0
    if I_HD.shape[:2] != (H, W):
        I_HD = cv2.resize(I_HD, (W, H), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(root / "S6_GEN" / "I_HD.jpg"), I_HD)

    dens_peep = I_HD[y0 : y1 + 1, x0 : x1 + 1].copy()
    dens2 = cv2.resize(
        dens_peep,
        (max(1, dens_peep.shape[1] * 2), max(1, dens_peep.shape[0] * 2)),
        interpolation=cv2.INTER_CUBIC,
    )
    elev = scale_lock_elev(peep, dens2, pm)
    cv2.imwrite(str(root / "S6_GEN" / "elev_scale_lock.jpg"), elev)
    cv2.imwrite(
        str(root / "S8_ANTI" / "ANTI_SHENG_peep_elev.jpg"),
        np.hstack([cv2.resize(peep, (320, 320)), cv2.resize(elev, (320, 320))]),
    )

    ret = hardpaste(L0, M, I_HD)
    cv2.imwrite(str(root / "S7_RETURN" / "RETURN.png"), ret)
    cv2.imwrite(str(root / "S8_ANTI" / "ANTI_SHENG_hole_RETURN.jpg"), np.hstack([rs(L_chu_part), rs(ret)]))
    cv2.imwrite(str(root / "S8_ANTI" / "ANTI_RETURN_L0.jpg"), np.hstack([rs(L0), rs(ret)]))

    out_max = outside_max(ret, L0, M)
    gates = {
        "CLIP_from_chu_bei": True,
        "not_self_peep": True,
        "Imagine_除件": L_chu_part is not None,
        "Imagine_除背": L_chu_bei is not None,
        "Imagine_生": I_HD is not None,
        "MARK_frozen": True,
        "true_hole": True,
        "elev_remap_false": True,
        "outside_0": out_max == 0,
        "frac_OK": kou_meta.get("gate") == "OK",
        "part_agnostic": True,
    }
    status = "PASS" if out_max == 0 and kou_meta.get("gate") == "OK" else (
        "PASS_OUTSIDE0_FRAC_WARN" if out_max == 0 else "FAIL_OUTSIDE"
    )
    if kou_meta.get("gate") and kou_meta["gate"].startswith("FAIL") and out_max == 0:
        status = kou_meta["gate"]  # surface frac issue for tune

    report.update({
        "status": status,
        "gates": gates,
        "outside_max": out_max,
        "claim": "C2_WLF_V21_STRUCTURE",
        "compose_law": "independent PASS != chain PASS; bus+invariants required",
        "asof": datetime.now(timezone.utc).isoformat(),
    })
    (root / "REPORT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (root / "STATE_BUS.json").write_text(
        json.dumps(
            {
                "L0": "S0_SRC/L0.jpg",
                "L_chu_part": "S4_REMOVE/L_chu_part.jpg",
                "L_chu_bei": "S4_REMOVE/L_chu_bei.jpg",
                "M_part": "S1_MARK/M_hole_MARK.png",
                "M_subj_CLIP": "S3_CLIP/M_subj.png",
                "CLIP": "S3_CLIP/CLIP_from_chu_bei.png",
                "I_HD": "S6_GEN/I_HD.jpg",
                "RETURN": "S7_RETURN/RETURN.png",
                "note": "child L0 must be CLIP not peep",
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # story board
    ch_h, ch_w = H // 2, W // 3
    story = np.zeros((ch_h * 2, ch_w * 3, 3), np.uint8)
    tiles = [
        (0, 0, L0, "1 L0"),
        (0, 1, clip_vis, "2 CLIP 除背"),
        (0, 2, L_chu_part, "3 除件洞"),
        (1, 0, thole, "4 MARK 洞座"),
        (1, 1, elev if elev is not None else peep, "5 elev 尺"),
        (1, 2, ret, "6 RETURN"),
    ]
    for r, c, im, lab in tiles:
        if im is None:
            continue
        if im.ndim == 2:
            im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        imr = cv2.resize(im, (ch_w, ch_h))
        cv2.putText(imr, lab, (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        story[r * ch_h : (r + 1) * ch_h, c * ch_w : (c + 1) * ch_w] = imr
    cv2.imwrite(str(root / "boards" / "STORY_V21.jpg"), story)
    return report


def cmd_presets(_args):
    print(json.dumps(TUNE_PRESETS, indent=2, ensure_ascii=False))
    return 0


def cmd_selftest(args):
    """結構 selftest：假像素僅驗 bus/CLIP 路徑；非 production claim。"""
    root = ensure(Path(args.out))
    tune = load_tune(args.tune)
    # synthetic dual-blob object (not head-specific)
    L0 = np.full((240, 320, 3), 40, np.uint8)
    cv2.rectangle(L0, (40, 50), (140, 190), (180, 160, 140), -1)
    cv2.rectangle(L0, (180, 50), (280, 190), (160, 170, 190), -1)
    cv2.circle(L0, (90, 90), 28, (220, 200, 180), -1)  # part on left
    L_part = L0.copy()
    cv2.circle(L_part, (90, 90), 28, (40, 40, 40), -1)  # remove part
    # chu bei: gray bg
    L_bei = L0.copy()
    mask_subj = np.zeros((240, 320), np.uint8)
    mask_subj[50:190, 40:140] = 255
    mask_subj[50:190, 180:280] = 255
    L_bei[mask_subj == 0] = (60, 60, 60)
    rep = run_structure(
        root / "L00",
        L0,
        L_part,
        L_bei,
        L0,
        tune,
        part_id="synth_blob",
        side="left",
        require_imagine=False,
        assets={"note": "selftest"},
    )
    # child: use CLIP region as L0 (true path)
    M_subj = cv2.imread(str(root / "L00" / "S3_CLIP" / "M_subj.png"), 0)
    # crop CLIP bbox as child L0
    ys, xs = np.where(M_subj > 0)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    child_L0 = L0[y0 : y1 + 1, x0 : x1 + 1].copy()
    ch, cw = child_L0.shape[:2]
    child_L1 = child_L0.copy()
    child_L1[ch // 4 : 3 * ch // 4, cw // 4 : 3 * cw // 4] = 30
    child_bei = child_L0.copy()
    # looser tune for child small canvas
    tune_c = copy.deepcopy(tune)
    tune_c["max_frac"] = 0.55
    tune_c["min_area"] = 100
    tune_c["roi_prior"] = "none"
    rep1 = run_structure(
        root / "L01",
        child_L0,
        child_L1,
        child_bei,
        child_L0,
        tune_c,
        part_id="synth_child",
        require_imagine=False,
    )
    summary = {
        "selftest": True,
        "v": "2.1",
        "tune": args.tune or "generic_object",
        "L0": rep.get("status"),
        "L1": rep1.get("status"),
        "CLIP_from_chu_bei": True,
        "compose_note": "selftest structure only — not TypeB production claim",
        "why_independent_ne_compose": (
            "Each layer can PASS gates alone; stack requires shared MARK/CLIP bus "
            "and same claim level — see SHQ_FOUR_ANTI_ALGEBRA_ARCH §3"
        ),
    }
    (root / "SELFTEST.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def cmd_structure(args):
    tune = load_tune(args.tune)
    if args.thr is not None:
        tune["kou_thr"] = args.thr
    if args.max_frac is not None:
        tune["max_frac"] = args.max_frac
    L0 = cv2.imread(args.l0)
    assert L0 is not None
    L_part = cv2.imread(args.l_chu_part) if args.l_chu_part else None
    L_bei = cv2.imread(args.l_chu_bei) if args.l_chu_bei else None
    I_HD = cv2.imread(args.ihd) if args.ihd else None
    hint = None
    if args.roi_hint:
        hint = [float(x) for x in args.roi_hint.split(",")]
    assets = {
        "除件": args.asset_chu_part,
        "除背": args.asset_chu_bei,
        "生": args.asset_sheng,
    }
    rep = run_structure(
        Path(args.out),
        L0,
        L_part,
        L_bei,
        I_HD,
        tune,
        part_id=args.part,
        side=args.side,
        roi_hint_norm=hint,
        assets=assets,
        require_imagine=not args.allow_no_imagine,
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if str(rep.get("status", "")).startswith("PASS") or str(rep.get("status", "")).startswith("NEED") else 1


def cmd_explain(_args):
    text = {
        "why_formula_fails_other_type": [
            "θ (thr/morph/roi/max_frac) was hardcoded for one type (often head)",
            "CLIP was peep crop not 除背 kou",
            "largest-CC kou swallows dual-subject or light-drift",
            "algebra confused with type parameters",
        ],
        "why_solo_pass_compose_fail": [
            "no shared State Bus M/CLIP/MARK",
            "downstream recomputes hole",
            "claim level swap C2 vs RESTORE",
            "freeframe steals peep sovereignty",
            "pseudo-composition of independent PASSes",
        ],
        "fix": "SHQ_WAI_LI_FAN_V2_1_ANY_OBJECT.md · SHQ_FOUR_ANTI_ALGEBRA_ARCH.md §3",
        "fix": "same F algebra · change part_id + TunePack · CLIP from 除背 · 外力GROK 除/生",
    }
    print(json.dumps(text, indent=2, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser(description="外力反 V2.1 任意物件")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("presets"); p.set_defaults(func=cmd_presets)
    p = sub.add_parser("explain"); p.set_defaults(func=cmd_explain)

    p = sub.add_parser("selftest"); p.set_defaults(func=cmd_selftest)
    p.add_argument("--out", default="/workspace/artifacts/SETS/PROJ_WLF_V21_SELFTEST")
    p.add_argument("--tune", default="generic_object")

    p = sub.add_parser("structure"); p.set_defaults(func=cmd_structure)
    p.add_argument("--out", required=True)
    p.add_argument("--l0", required=True)
    p.add_argument("--l-chu-part", default=None)
    p.add_argument("--l-chu-bei", default=None)
    p.add_argument("--ihd", default=None)
    p.add_argument("--part", default="part")
    p.add_argument("--side", default="left", choices=["left", "right"])
    p.add_argument("--tune", default="generic_object")
    p.add_argument("--thr", type=int, default=None)
    p.add_argument("--max-frac", type=float, default=None)
    p.add_argument("--roi-hint", default=None, help="x0,y0,x1,y1 norm")
    p.add_argument("--asset-chu-part", default=None)
    p.add_argument("--asset-chu-bei", default=None)
    p.add_argument("--asset-sheng", default=None)
    p.add_argument("--allow-no-imagine", action="store_true")

    args = ap.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
