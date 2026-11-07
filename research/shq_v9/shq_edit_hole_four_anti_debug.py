#!/usr/bin/env python3
"""SHQ_EDIT_HOLE_FOUR_ANTI_DEBUG_V1 (01386)

Glossary + wrong-path + four-state anti helpers + non-blocking DEBUG QA.
Questions are recorded as DIAG/WARN by default and do NOT block runtime.
Use --strict only for CI / pre-ACCEPT gates.

CLI:
  selftest | glossary | qa-template | check-size | anti-diff
  | scale-lock-map | run-diag
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

WRITE_ID = "01386"
FORMAL = "SHQ_EDIT_HOLE_FOUR_ANTI_DEBUG_V1"

GLOSSARY: Dict[str, Dict[str, str]] = {
    "SRC_L0": {
        "def": "原圖凍結；有背·有頭",
        "not": "升清後圖",
    },
    "除_REMOVE": {
        "def": "Imagine EDIT 去掉目標部件 → L1 有背無頭",
        "not": "手擦、假 empty",
    },
    "洞_HOLE": {
        "def": "目標在 SRC 上的剪影空位 M_hole（形狀）",
        "not": "peep 矩形 / BBox",
    },
    "反洞": {
        "def": "M_anti_hole = not M_hole；洞外 bit-exact",
        "not": "soft mask",
    },
    "扣_DIFF": {
        "def": "同源同機位 Support(|I_keep-I_remove|)",
        "not": "單圖 peep 猜邊",
    },
    "生_GEN": {
        "def": "只在洞內生成/升清 RGB；座標=SRC",
        "not": "freeframe 整頭特写",
    },
    "反_ANTI": {
        "def": "每態正/反對：有頭↔無頭、有背↔無背、洞↔反洞、生前↔生后",
        "not": "只生不反查",
    },
    "peep": {
        "def": "洞框 bbox 裁出的小圖；尺度契約載體",
        "not": "freeframe donor",
    },
    "freeframe": {
        "def": "生成器自定構圖/尺度/特写",
        "not": "洞內同構 INPAINT",
    },
    "scale_lock": {
        "def": "生後 content 面積 ≤ peep×1.15；wh 綁洞框",
        "not": "densify 可改構圖",
    },
    "偷步_STEAL": {
        "def": "扣洞與生斷開：另生 freeframe 再 map 塞洞",
        "not": "洞內 INPAINT / peep 鎖尺 HF",
    },
    "RESET_DONOR": {
        "def": "新鏈禁止舊 freeframe densify map 當 HD 位姿主權",
        "not": "禁止 HF 材質源（鎖尺後可用）",
    },
    "hardpaste": {
        "def": "out=SRC; out[M_hole]=HD[M_hole]；洞外 max_diff=0",
        "not": "alpha 混合糊邊",
    },
    "elev_remap": {
        "def": "必須 false；升清不改 corners/位姿",
        "not": "warp 救對位",
    },
    "DEBUG_QA": {
        "def": "逐步質問；默認 DIAG 不阻跑",
        "not": "ACCEPT 唯一門（除非 --strict）",
    },
}

WRONG_PATHS: List[Dict[str, str]] = [
    {"id": "W1", "wrong": "矩形 peep 當洞", "hurt": "無剪影", "fix": "扣/色相→M_hole"},
    {"id": "W2", "wrong": "外框 reverse 當鏤空", "hurt": "矩形非頭形", "fix": "剪影對剪影"},
    {"id": "W3", "wrong": "freeframe densify 當 donor", "hurt": "頭變大/姿漂", "fix": "鎖尺 HF→peep"},
    {"id": "W4", "wrong": "無背 peep 另裁放大", "hurt": "有背無背尺度分裂", "fix": "同 bbox peep"},
    {"id": "W5", "wrong": "扣完 freeframe map 塞洞", "hurt": "偷步錯位", "fix": "洞內生"},
    {"id": "W6", "wrong": "ROI 邊弱當生產", "hurt": "盔緣低清", "fix": "全洞 w=1（尺度穩後）"},
    {"id": "W7", "wrong": "A 閘 ACCEPT B", "hurt": "跨模型驗收", "fix": "同候選同閘"},
    {"id": "W8", "wrong": "舊 donor 不 RESET", "hurt": "失憶混鏈", "fix": "RESET_DONOR"},
    {"id": "W9", "wrong": "DEBUG 全 BLOCK", "hurt": "迭代死", "fix": "DIAG；strict 才阻"},
    {"id": "W10", "wrong": "手剪影主路徑", "hurt": "非 EDIT 認邊", "fix": "EDIT 除/色相"},
]

PY_MAP: Dict[str, str] = {
    "debug_orchestrator": "shq_edit_hole_four_anti_debug.py",
    "edit_pair_diff": "shq_edit_pair_differential_clip.py",
    "clip_elev_return": "shq_clip_mask_elev_return.py",
    "clip_pair_reverse": "shq_clip_mask_pair_reverse.py",
    "material_fill": "shq_material_fill.py",
    "native_alpha_audit": "shq_native_alpha_audit.py",
    "function_codes": "docs/GROK_IMAGINE_FUNCTION_CODES.md §19h–§19l",
    "constitution": "SHQ_EDIT_HOLE_FOUR_ANTI_DEBUG.md",
}


@dataclass
class QAItem:
    id: str
    question: str
    status: str  # PASS | WARN | FAIL | SKIP
    detail: str = ""
    e_code: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_bbox_frac(im: np.ndarray, thr: int = 18) -> Tuple[float, float, float]:
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(g > thr)
    if len(xs) < 10:
        return 0.0, 0.0, 0.0
    fw = (xs.max() - xs.min() + 1) / im.shape[1]
    fh = (ys.max() - ys.min() + 1) / im.shape[0]
    fa = len(xs) / float(im.shape[0] * im.shape[1])
    return float(fw), float(fh), float(fa)


def check_size_grow(
    peep: np.ndarray,
    densify: np.ndarray,
    max_grow: float = 1.15,
) -> Dict[str, Any]:
    """Compare content fraction densify vs peep; freeframe close-up fails."""
    pw, ph, pa = content_bbox_frac(peep)
    dw, dh, da = content_bbox_frac(densify)
    # freeframe often fills canvas; peep head also high fill in tight crop —
    # use absolute canvas size ratio + area ratio when densify is much larger canvas
    canvas_ratio = (densify.shape[0] * densify.shape[1]) / max(1, peep.shape[0] * peep.shape[1])
    # head-grow signal: densify canvas >> peep AND content fills most of densify
    grow_flag = bool(canvas_ratio > 4.0 and da > 0.35)
    # secondary: mapped size check if densify resized to peep
    dens_rs = cv2.resize(densify, (peep.shape[1], peep.shape[0]), interpolation=cv2.INTER_AREA)
    # lap ratio not for size
    return {
        "peep_hw": [int(peep.shape[0]), int(peep.shape[1])],
        "densify_hw": [int(densify.shape[0]), int(densify.shape[1])],
        "canvas_ratio": float(canvas_ratio),
        "peep_content_frac": pa,
        "densify_content_frac": da,
        "HEAD_SCALE_GROW_suspect": grow_flag,
        "size_ok": (not grow_flag) and canvas_ratio <= 4.0,
        "max_grow_policy": max_grow,
        "E-105": grow_flag,
        "E-106": bool(canvas_ratio > 8.0),
    }


def anti_diff(
    keep: np.ndarray,
    remove: np.ndarray,
    thr: int = 22,
    left_half_only: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    if keep.shape[:2] != remove.shape[:2]:
        remove = cv2.resize(remove, (keep.shape[1], keep.shape[0]), interpolation=cv2.INTER_AREA)
    d = cv2.absdiff(keep, remove)
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (5, 5), 0)
    m = (g > thr).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    if left_half_only:
        mask = np.zeros_like(m)
        mask[:, : m.shape[1] // 2] = 255
        m = cv2.bitwise_and(m, mask)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n > 1:
        i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        m = (lab == i).astype(np.uint8) * 255
    heat = cv2.applyColorMap(
        cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8),
        cv2.COLORMAP_INFERNO,
    )
    return m, heat


def scale_lock_map(
    peep: np.ndarray,
    densify: np.ndarray,
    alpha: Optional[np.ndarray] = None,
    hf: float = 1.45,
) -> np.ndarray:
    """Map densify HF into peep LF; peep owns scale/pose."""
    g = cv2.cvtColor(densify, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(g > 12)
    if len(xs) > 20:
        densify = densify[int(ys.min()) : int(ys.max()) + 1, int(xs.min()) : int(xs.max()) + 1]
    th, tw = peep.shape[:2]
    m = cv2.resize(densify, (tw, th), interpolation=cv2.INTER_LANCZOS4)
    g1 = cv2.cvtColor(peep, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY).astype(np.float32)
    (dx, dy), _ = cv2.phaseCorrelate(
        cv2.GaussianBlur(g1, (0, 0), 1), cv2.GaussianBlur(g2, (0, 0), 1)
    )
    dx, dy = float(np.clip(dx, -6, 6)), float(np.clip(dy, -6, 6))
    m = cv2.warpAffine(
        m,
        np.float32([[1, 0, dx], [0, 1, dy]]),
        (tw, th),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT,
    )
    pf, mf = peep.astype(np.float32), m.astype(np.float32)
    out = cv2.GaussianBlur(pf, (0, 0), 0.9) + (mf - cv2.GaussianBlur(mf, (0, 0), 0.9)) * hf
    out = np.clip(out * 0.35 + mf * 0.25 + pf * 0.40, 0, 255).astype(np.uint8)
    try:
        out = cv2.detailEnhance(out, sigma_s=8, sigma_r=0.15)
    except Exception:
        pass
    if alpha is not None:
        if alpha.shape[:2] != (th, tw):
            alpha = cv2.resize(alpha, (tw, th), interpolation=cv2.INTER_NEAREST)
        a = alpha > 0
        mix = peep.copy()
        mix[a] = out[a]
        return mix
    return out


def hardpaste_hole(
    src: np.ndarray, hd: np.ndarray, m_hole: np.ndarray
) -> Tuple[np.ndarray, int]:
    if hd.shape[:2] != src.shape[:2]:
        hd = cv2.resize(hd, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_AREA)
    if m_hole.shape[:2] != src.shape[:2]:
        m_hole = cv2.resize(m_hole, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_NEAREST)
    out = src.copy()
    out[m_hole > 0] = hd[m_hole > 0]
    leak = int(np.logical_and(np.any(out != src, axis=2), m_hole == 0).sum())
    return out, leak


def qa_template() -> List[QAItem]:
    return [
        QAItem("Q0", "RESET_DONOR 是否聲明？", "SKIP", "填 true/false"),
        QAItem("Q1", "是否有 L0 與 L1（除）？", "SKIP"),
        QAItem("Q2", "扣是否同源同機位？", "SKIP"),
        QAItem("Q3", "M_hole 是剪影非整框？", "SKIP"),
        QAItem("Q4", "有背/無背 peep 同 bbox？", "SKIP"),
        QAItem("Q5", "生是否鎖尺 grow≤1.15 / canvas_ratio？", "SKIP", e_code="E-105"),
        QAItem("Q6", "是否避免偷步 freeframe map？", "SKIP", e_code="E-100"),
        QAItem("Q7", "洞外 max_diff==0？", "SKIP"),
        QAItem("Q8", "elev_remap==false？", "SKIP"),
        QAItem("Q9", "反查板是否落盤？", "SKIP"),
    ]


def run_diag_from_run(run_dir: Path, strict: bool = False) -> Dict[str, Any]:
    """Non-blocking diagnostics: missing files → WARN/SKIP, not crash."""
    items: List[QAItem] = []
    run_dir = Path(run_dir)

    def add(i: QAItem) -> None:
        items.append(i)

    reset = run_dir / "RESET_DONOR.json"
    if reset.exists():
        try:
            j = json.loads(reset.read_text(encoding="utf-8"))
            ok = bool(j.get("RESET_DONOR", False))
            add(QAItem("Q0", "RESET_DONOR", "PASS" if ok else "WARN", str(j)[:200], "E-99"))
        except Exception as e:
            add(QAItem("Q0", "RESET_DONOR", "WARN", str(e), "E-99"))
    else:
        add(QAItem("Q0", "RESET_DONOR 缺失", "WARN", "不阻跑", "E-99"))

    # optional layers
    for qid, rel in [
        ("Q1a", "layers/L0_有背有頭.jpg"),
        ("Q1b", "layers/L1_有背無頭_除.jpg"),
        ("Q1c", "layers/L0_SRC.jpg"),
    ]:
        p = run_dir / rel
        if p.exists():
            add(QAItem(qid, f"存在 {rel}", "PASS", str(p)))
    if not any(i.id.startswith("Q1") and i.status == "PASS" for i in items):
        add(QAItem("Q1", "L0/L1 層", "WARN", "未找到 layers — 不阻跑"))

    hole = None
    for cand in ["masks/M_洞.png", "masks/M_hole.png", "masks/U0_M_hole.png"]:
        p = run_dir / cand
        if p.exists():
            hole = cv2.imread(str(p), 0)
            add(QAItem("Q3", f"M_hole {cand}", "PASS", f"area={(hole>0).sum() if hole is not None else 0}"))
            break
    if hole is None:
        add(QAItem("Q3", "M_hole", "WARN", "缺失 — 不阻跑", "E-107"))

    peep_p = None
    for cand in [
        "ref/peep_有背_洞框_LOCKED.jpg",
        "ref/U0_OLD_HEAD_PEEP_REF.jpg",
        "ref/peep_blackbg_LOCKED.jpg",
    ]:
        if (run_dir / cand).exists():
            peep_p = run_dir / cand
            break
    dens_p = None
    for cand in list(run_dir.glob("ref/*DENS*")) + list(run_dir.glob("**/56906835*.jpg")):
        dens_p = cand
        break
    # also search common densify asset copies
    if peep_p and dens_p:
        peep = cv2.imread(str(peep_p))
        dens = cv2.imread(str(dens_p))
        if peep is not None and dens is not None:
            sz = check_size_grow(peep, dens)
            st = "PASS" if sz["size_ok"] else "WARN"
            if strict and not sz["size_ok"]:
                st = "FAIL"
            add(QAItem("Q5", "鎖尺 check-size", st, json.dumps(sz), "E-105" if not sz["size_ok"] else ""))
    else:
        add(QAItem("Q5", "鎖尺", "SKIP", "無 peep/densify 對 — 不阻跑"))

    anti = list(run_dir.glob("anti/*")) + list(run_dir.glob("return/*ANTI*"))
    if anti:
        add(QAItem("Q9", "反查產物", "PASS", f"n={len(anti)}"))
    else:
        add(QAItem("Q9", "反查產物", "SKIP", "可後補"))

    add(QAItem("Q6", "偷步提醒", "WARN", "人工確認無 freeframe 主權 map", "E-100"))
    add(QAItem("Q8", "elev_remap", "WARN", "契約要求 false — 請在 SUMMARY 聲明"))

    fail_n = sum(1 for i in items if i.status == "FAIL")
    warn_n = sum(1 for i in items if i.status == "WARN")
    report = {
        "write_id": WRITE_ID,
        "formal": FORMAL,
        "strict": strict,
        "blocks_runtime": False if not strict else fail_n > 0,
        "fail_n": fail_n,
        "warn_n": warn_n,
        "items": [asdict(i) for i in items],
        "glossary_keys": list(GLOSSARY.keys()),
        "wrong_paths": WRONG_PATHS,
        "py_map": PY_MAP,
        "asof": _now(),
        "note": "默認不阻運行；--strict 時 FAIL→exit 2",
    }
    out = run_dir / "audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "DEBUG_QA_01386.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def cmd_selftest() -> int:
    # synthetic peep small vs freeframe large
    peep = np.zeros((154, 143, 3), np.uint8)
    cv2.ellipse(peep, (70, 80), (50, 60), 0, 0, 360, (200, 200, 200), -1)
    dens = np.zeros((1408, 1408, 3), np.uint8)
    cv2.ellipse(dens, (700, 700), (500, 600), 0, 0, 360, (200, 200, 200), -1)
    sz = check_size_grow(peep, dens)
    assert sz["HEAD_SCALE_GROW_suspect"] or not sz["size_ok"], sz

    elev = scale_lock_map(peep, dens)
    assert elev.shape[:2] == peep.shape[:2]

    keep = peep.copy()
    rem = peep.copy()
    rem[:] = 10
    m, heat = anti_diff(
        cv2.resize(keep, (200, 200)),
        cv2.resize(rem, (200, 200)),
        thr=5,
    )
    assert m is not None and heat is not None

    src = np.zeros((100, 100, 3), np.uint8)
    src[20:50, 20:50] = 100
    hd = src.copy()
    hd[20:50, 20:50] = 200
    mh = np.zeros((100, 100), np.uint8)
    mh[20:50, 20:50] = 255
    out, leak = hardpaste_hole(src, hd, mh)
    assert leak == 0
    assert GLOSSARY and WRONG_PATHS and PY_MAP
    print(json.dumps({"selftest": "PASS", "write_id": WRITE_ID, "formal": FORMAL}, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=FORMAL)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selftest")
    sub.add_parser("glossary")
    sub.add_parser("wrong-paths")
    sub.add_parser("py-map")

    t = sub.add_parser("qa-template")
    t.add_argument("--out", type=Path, default=None)

    c = sub.add_parser("check-size")
    c.add_argument("--peep", type=Path, required=True)
    c.add_argument("--densify", type=Path, required=True)
    c.add_argument("--json-out", type=Path, default=None)

    a = sub.add_parser("anti-diff")
    a.add_argument("--keep", type=Path, required=True)
    a.add_argument("--remove", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--thr", type=int, default=22)
    a.add_argument("--left-half", action="store_true")

    s = sub.add_parser("scale-lock-map")
    s.add_argument("--peep", type=Path, required=True)
    s.add_argument("--densify", type=Path, required=True)
    s.add_argument("--alpha", type=Path, default=None)
    s.add_argument("--out", type=Path, required=True)

    h = sub.add_parser("hardpaste")
    h.add_argument("--src", type=Path, required=True)
    h.add_argument("--hd", type=Path, required=True)
    h.add_argument("--hole", type=Path, required=True)
    h.add_argument("--out", type=Path, required=True)

    d = sub.add_parser("run-diag")
    d.add_argument("--run", type=Path, required=True)
    d.add_argument("--strict", action="store_true", help="FAIL → exit 2; default never blocks")

    args = p.parse_args(argv)

    if args.cmd == "selftest":
        return cmd_selftest()

    if args.cmd == "glossary":
        print(json.dumps(GLOSSARY, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "wrong-paths":
        print(json.dumps(WRONG_PATHS, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "py-map":
        print(json.dumps(PY_MAP, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "qa-template":
        data = {
            "write_id": WRITE_ID,
            "items": [asdict(x) for x in qa_template()],
            "blocks_runtime_default": False,
        }
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            args.out = Path(args.out)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        print(text)
        return 0

    if args.cmd == "check-size":
        peep = cv2.imread(str(args.peep))
        dens = cv2.imread(str(args.densify))
        if peep is None or dens is None:
            print(json.dumps({"error": "imread failed"}, indent=2))
            return 1
        r = check_size_grow(peep, dens)
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(r, indent=2))
        return 0

    if args.cmd == "anti-diff":
        keep = cv2.imread(str(args.keep))
        rem = cv2.imread(str(args.remove))
        if keep is None or rem is None:
            return 1
        m, heat = anti_diff(keep, rem, thr=args.thr, left_half_only=args.left_half)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out / "M_扣.png"), m)
        cv2.imwrite(str(out / "HEAT_扣.png"), heat)
        cv2.imwrite(str(out / "M_反洞.png"), cv2.bitwise_not(m))
        print(json.dumps({"area": int((m > 0).sum()), "out": str(out)}, indent=2))
        return 0

    if args.cmd == "scale-lock-map":
        peep = cv2.imread(str(args.peep))
        dens = cv2.imread(str(args.densify))
        alpha = cv2.imread(str(args.alpha), 0) if args.alpha else None
        if peep is None or dens is None:
            return 1
        elev = scale_lock_map(peep, dens, alpha)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.out), elev)
        print(json.dumps({"out": str(args.out), "hw": list(elev.shape[:2])}, indent=2))
        return 0

    if args.cmd == "hardpaste":
        src = cv2.imread(str(args.src))
        hd = cv2.imread(str(args.hd))
        hole = cv2.imread(str(args.hole), 0)
        if src is None or hd is None or hole is None:
            return 1
        out, leak = hardpaste_hole(src, hd, hole)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.out), out)
        print(json.dumps({"leak": leak, "out": str(args.out)}, indent=2))
        return 0

    if args.cmd == "run-diag":
        rep = run_diag_from_run(Path(args.run), strict=bool(args.strict))
        print(json.dumps({k: rep[k] for k in ("fail_n", "warn_n", "blocks_runtime", "strict", "asof")}, indent=2))
        if args.strict and rep["fail_n"] > 0:
            return 2
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
