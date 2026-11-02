#!/usr/bin/env python3
"""DBSS 單白殺升 — NONHD WNK → PATH1E ECC paste → optional Lanczos.
Imagine light is external (Grok Imagine); this CLI covers WNK+PATH1E+Lanczos.
"""
from __future__ import annotations
import argparse, json, hashlib
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

def wnk(bgr: np.ndarray):
    f = bgr.astype(np.float32)
    Y = 0.114 * f[..., 0] + 0.587 * f[..., 1] + 0.299 * f[..., 2]
    mx, mn = f.max(2), f.min(2)
    sat = (mx - mn) / np.maximum(mx, 1.0)
    Ys, Y2 = cv2.blur(Y, (3, 3)), cv2.blur(Y * Y, (3, 3))
    var = np.maximum(Y2 - Ys * Ys, 0)
    lap = cv2.Laplacian(Y, cv2.CV_32F)
    noise = (Y > 210) & (sat < 0.18) & (np.abs(lap) > 12) & (var > 40)
    spec = (Y > 235) & (sat < 0.12) & (var < 80) & (np.abs(lap) < 8)
    kill = noise & (~spec)
    mask = cv2.dilate((kill.astype(np.uint8) * 255), np.ones((2, 2), np.uint8), 1)
    kill = mask > 0
    out = bgr.copy()
    if kill.any():
        med = cv2.medianBlur(bgr, 5)
        out[kill] = med[kill]
    st = {
        "kill_px": int(kill.sum()),
        "noise_px": int(noise.sum()),
        "spec_px": int(spec.sum()),
        "frac_kill": float(kill.mean()),
        "resolution": "NON_HD",
        "formula": "kill=NOISE_WHITE∩¬SPEC_LIGHT",
    }
    return out, (mask > 0).astype(np.uint8) * 255, st

def feather_paste(base, peep, box, feather=22):
    x0, y0, x1, y1 = box
    out = base.copy()
    peep = cv2.resize(peep, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LANCZOS4)
    ph, pw = peep.shape[:2]
    m = np.zeros((ph, pw), np.float32)
    f = min(feather, max(1, min(ph, pw) // 5))
    m[f : ph - f, f : pw - f] = 1.0
    m = cv2.GaussianBlur(m, (0, 0), max(f / 2, 1.0))
    region = out[y0:y1, x0:x1].astype(np.float32)
    out[y0:y1, x0:x1] = np.clip(region * (1 - m[..., None]) + peep.astype(np.float32) * m[..., None], 0, 255).astype(np.uint8)
    return out

def main():
    ap = argparse.ArgumentParser(description="DBSS 單白殺升 (WNK NONHD + paste + Lanczos; PATH1E dens optional external)")
    ap.add_argument("--mother", required=True)
    ap.add_argument("--face-box", default="800,30,1600,740", help="x0,y0,x1,y1")
    ap.add_argument("--dens", default="", help="optional PATH1E dens image; if empty, paste NONHD WNK only")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--lanczos", type=int, nargs="*", default=[2, 4])
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mother = cv2.imread(args.mother)
    assert mother is not None
    x0, y0, x1, y1 = map(int, args.face_box.split(","))
    face = mother[y0:y1, x0:x1].copy()
    face_wnk, mask, st = wnk(face)
    cv2.imwrite(str(out / "face_NONHD.jpg"), face)
    cv2.imwrite(str(out / "face_NONHD_WNK.jpg"), face_wnk)
    cv2.imwrite(str(out / "face_NONHD_WNK_MASK.png"), mask)
    base = mother.copy()
    base[y0:y1, x0:x1] = face_wnk
    if args.dens:
        dens = cv2.imread(args.dens)
        assert dens is not None
        peep = cv2.resize(dens, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
        # light ECC
        g0 = cv2.cvtColor(face_wnk, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
        g1 = cv2.cvtColor(peep, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
        W = np.eye(2, 3, dtype=np.float32)
        crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6)
        try:
            cc, W = cv2.findTransformECC(g0, g1, W, cv2.MOTION_AFFINE, crit, None, 1)
            peep = cv2.warpAffine(peep, W, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
            ecc_cc = float(cc)
        except cv2.error:
            ecc_cc = 0.0
    else:
        peep = face_wnk
        ecc_cc = 1.0
    pasted = feather_paste(base, peep, (x0, y0, x1, y1))
    assert pasted.shape == mother.shape
    cv2.imwrite(str(out / "OUT_MOTHER_DBSS.png"), pasted)
    lanczos_paths = {}
    H, Wd = mother.shape[:2]
    for s in args.lanczos:
        L = cv2.resize(pasted, (Wd * s, H * s), interpolation=cv2.INTER_LANCZOS4)
        p = out / f"OUT_LANCZOS_x{s}.png"
        cv2.imwrite(str(p), L)
        lanczos_paths[f"x{s}"] = {"path": str(p), "wh": [Wd * s, H * s], "sha256": sha256(p)}
    doc = {
        "format": "ige.skill.dbss_dan_bai_sha_sheng",
        "code": "DBSS",
        "skill_id": "01261",
        "title_zh": "單白殺升",
        "face_box": [x0, y0, x1, y1],
        "wnk_nonhd": st,
        "path1e": {"dens": args.dens or None, "ecc_cc": ecc_cc},
        "paste_fail": False,
        "mother_wh": [int(Wd), int(H)],
        "pixel_drop": False,
        "hd_face_wnk": False,
        "lanczos": lanczos_paths,
        "imagine_light": {"note": "run via Grok Imagine image_to_image; not in this CLI"},
        "quality_qualified": False,
        "final_acceptance": False,
        "output_mother": str(out / "OUT_MOTHER_DBSS.png"),
        "output_mother_sha256": sha256(out / "OUT_MOTHER_DBSS.png"),
        "asof": datetime.now(timezone.utc).isoformat(),
    }
    (out / "RESULT_DBSS.json").write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps(doc, indent=2))

if __name__ == "__main__":
    main()
