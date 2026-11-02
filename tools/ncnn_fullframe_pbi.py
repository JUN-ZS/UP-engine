#!/usr/bin/env python3
"""Full-frame NCNN GENERAL_x4v3 + PBI (memory-safe default).

DEFAULT pipeline (do not invert):
  1) tile NCNN → write RAW PNG to disk (uint8; free float canvas)
  2) strip-wise PBI luma-only vs Lanczos LP → write PBI PNG
  3) optional half/preview JPEG

Never keep two full-res float32 canvases + LP + SR in RAM at once
(OOM risk at 7168×4032). First attempt that OOM'd warrior fullframe
is recorded in RESULT.limits if env lacked headroom.

Not Siax / not NMKD. quality_qualified=false by default.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import ncnn
import numpy as np

SCALE_DEFAULT = 4
TILE_DEFAULT = 64
PAD_DEFAULT = 8
GAIN_DEFAULT = 1.0
STRIP_DEFAULT = 256  # PBI row strips in BASE pixels


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def to_y_bgr(bgr: np.ndarray) -> np.ndarray:
    f = bgr.astype(np.float32)
    return 0.114 * f[..., 0] + 0.587 * f[..., 1] + 0.299 * f[..., 2]


def load_ncnn(param: Path, bin_path: Path, threads: int = 4) -> ncnn.Net:
    net = ncnn.Net()
    net.opt.num_threads = threads
    net.opt.use_vulkan_compute = False
    if net.load_param(str(param)) != 0:
        raise RuntimeError(f"load_param failed: {param}")
    if net.load_model(str(bin_path)) != 0:
        raise RuntimeError(f"load_model failed: {bin_path}")
    return net


def ncnn_4x_tile(net: ncnn.Net, bgr_u8: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(bgr_u8, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    inp = np.transpose(rgb, (2, 0, 1)).copy()
    ex = net.create_extractor()
    ex.input("in0", ncnn.Mat(inp))
    ret, mat_out = ex.extract("out0")
    if ret != 0:
        raise RuntimeError(f"ncnn extract failed: {ret}")
    out = np.array(mat_out)
    if out.ndim == 3:
        out = np.transpose(out, (1, 2, 0))
    out = np.clip(out * 255.0, 0, 255).astype(np.uint8)
    return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)


def _tile_grid(length: int, tile: int, step: int) -> list[int]:
    if length < tile:
        return [0]
    xs = list(range(0, length - tile + 1, step))
    if xs[-1] != length - tile:
        xs.append(length - tile)
    return xs


def upscale_write_raw(
    net: ncnn.Net,
    bgr: np.ndarray,
    raw_path: Path,
    *,
    scale: int,
    tile: int,
    pad: int,
) -> dict:
    """DEFAULT step 1: NCNN tiles → single RAW PNG. Free large float buffers ASAP."""
    h, w = bgr.shape[:2]
    oh, ow = h * scale, w * scale
    step = max(8, tile - pad * 2)
    xs = _tile_grid(w, tile, step)
    ys = _tile_grid(h, tile, step)
    total = len(xs) * len(ys)

    canvas = np.zeros((oh, ow, 3), dtype=np.float32)
    weight = np.zeros((oh, ow), dtype=np.float32)
    t0 = time.time()
    n = 0
    for y0 in ys:
        for x0 in xs:
            x1, y1 = min(x0 + tile, w), min(y0 + tile, h)
            crop = bgr[y0:y1, x0:x1]
            ch, cw = crop.shape[:2]
            if ch != tile or cw != tile:
                pad_c = np.zeros((tile, tile, 3), dtype=np.uint8)
                pad_c[:ch, :cw] = crop
                if ch < tile:
                    pad_c[ch:, :cw] = crop[-1:]
                if cw < tile:
                    pad_c[:, cw:] = pad_c[:, max(cw - 1, 0) : cw]
                crop_in = pad_c
            else:
                crop_in = crop
            sr = ncnn_4x_tile(net, crop_in)
            sh, sw = ch * scale, cw * scale
            ox0, oy0 = x0 * scale, y0 * scale
            wy = np.hanning(max(sh, 2))[:sh].astype(np.float32)
            wx = np.hanning(max(sw, 2))[:sw].astype(np.float32)
            if sh < 4:
                wy[:] = 1.0
            if sw < 4:
                wx[:] = 1.0
            ww = np.outer(wy, wx) + 1e-4
            canvas[oy0 : oy0 + sh, ox0 : ox0 + sw] += sr[:sh, :sw].astype(np.float32) * ww[
                ..., None
            ]
            weight[oy0 : oy0 + sh, ox0 : ox0 + sw] += ww
            n += 1
            if n % 100 == 0 or n == total:
                print(f"  raw tiles {n}/{total} {time.time() - t0:.1f}s", flush=True)

    weight = np.maximum(weight, 1e-4)
    out = (canvas / weight[..., None]).clip(0, 255).astype(np.uint8)
    del canvas, weight
    gc.collect()
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(raw_path), out):
        raise RuntimeError(f"failed to write RAW {raw_path}")
    del out
    gc.collect()
    return {
        "tile_count": total,
        "infer_s": round(time.time() - t0, 3),
        "step": "write_raw_first",
        "raw_path": str(raw_path),
    }


def pbi_strips_from_raw(
    bgr: np.ndarray,
    raw_path: Path,
    pbi_path: Path,
    *,
    scale: int,
    gain: float,
    strip_base_px: int,
) -> dict:
    """DEFAULT step 2: read RAW from disk; PBI by horizontal strips; write PBI."""
    h, w = bgr.shape[:2]
    oh, ow = h * scale, w * scale
    sr = cv2.imread(str(raw_path), cv2.IMREAD_COLOR)
    if sr is None:
        raise RuntimeError(f"cannot read RAW {raw_path}")
    if sr.shape[0] != oh or sr.shape[1] != ow:
        raise RuntimeError(f"RAW size {sr.shape[:2]} != expected {(oh, ow)}")

    out = np.empty((oh, ow, 3), dtype=np.uint8)
    t0 = time.time()
    strips = 0
    for y0 in range(0, h, strip_base_px):
        y1 = min(y0 + strip_base_px, h)
        src_s = bgr[y0:y1]
        lp = cv2.resize(
            src_s,
            (w * scale, (y1 - y0) * scale),
            interpolation=cv2.INTER_LANCZOS4,
        )
        oy0, oy1 = y0 * scale, y1 * scale
        sr_s = sr[oy0:oy1]
        y_lp = to_y_bgr(lp)
        y_sr = to_y_bgr(sr_s)
        dy = (y_sr - y_lp).astype(np.float32)
        mag = np.abs(dy)
        thr = max(1.0, float(np.percentile(mag, 40)))
        soft = np.tanh(mag / (thr + 1e-3)) * dy
        blur = cv2.GaussianBlur(soft, (0, 0), 1.2)
        dY = soft + 0.15 * (soft - blur)
        y_out = np.clip(y_lp + gain * dY, 0, 255)
        C = lp.astype(np.float32) / np.maximum(y_lp, 8.0)[..., None]
        out[oy0:oy1] = np.clip(C * y_out[..., None], 0, 255).astype(np.uint8)
        strips += 1
        print(f"  pbi strip {y0}:{y1}", flush=True)

    del sr
    gc.collect()
    pbi_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(pbi_path), out):
        raise RuntimeError(f"failed to write PBI {pbi_path}")
    return {
        "strips": strips,
        "strip_base_px": strip_base_px,
        "pbi_s": round(time.time() - t0, 3),
        "step": "pbi_after_raw_disk",
        "pbi_path": str(pbi_path),
        "pbi_wh": [int(out.shape[1]), int(out.shape[0])],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="NCNN full-frame ×4 + PBI. Default = RAW to disk first, then strip PBI."
    )
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--param", type=Path, required=True, help="*.ncnn.param")
    ap.add_argument("--bin", type=Path, required=True, help="*.ncnn.bin")
    ap.add_argument("--stem", default="OUT_NCNN_GENERAL_x4v3")
    ap.add_argument("--tile", type=int, default=TILE_DEFAULT)
    ap.add_argument("--pad", type=int, default=PAD_DEFAULT)
    ap.add_argument("--scale", type=int, default=SCALE_DEFAULT)
    ap.add_argument("--gain", type=float, default=GAIN_DEFAULT)
    ap.add_argument("--pbi-strip", type=int, default=STRIP_DEFAULT)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument(
        "--pbi-mode",
        choices=["luma_only", "raw_only"],
        default="luma_only",
        help="default luma_only; raw_only skips PBI after RAW",
    )
    ap.add_argument(
        "--unsafe-all-in-ram",
        action="store_true",
        help="FORBIDDEN default. Kept only as explicit opt-in (will refuse).",
    )
    args = ap.parse_args()

    if args.unsafe_all_in_ram:
        raise SystemExit(
            "refused: --unsafe-all-in-ram is disabled. "
            "Default is write RAW then strip PBI (memsafe)."
        )

    t_all = time.time()
    bgr = cv2.imread(str(args.input), cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit(f"cannot read input: {args.input}")
    h, w = bgr.shape[:2]
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"{args.stem}_RAW.png"
    pbi_path = out_dir / f"{args.stem}_PBI.png"
    prev_path = out_dir / f"{args.stem}_PBI_preview.jpg"
    half_path = out_dir / f"{args.stem}_PBI_half.jpg"

    print(
        f"DEFAULT memsafe: RAW→disk then strip PBI | in={w}x{h} tile={args.tile}",
        flush=True,
    )
    net = load_ncnn(args.param, args.bin, threads=args.threads)
    raw_meta = upscale_write_raw(
        net,
        bgr,
        raw_path,
        scale=args.scale,
        tile=args.tile,
        pad=args.pad,
    )
    print(f"RAW written {raw_path} ({raw_path.stat().st_size} bytes)", flush=True)

    pbi_meta: dict = {"skipped": True}
    if args.pbi_mode == "luma_only":
        pbi_meta = pbi_strips_from_raw(
            bgr,
            raw_path,
            pbi_path,
            scale=args.scale,
            gain=args.gain,
            strip_base_px=args.pbi_strip,
        )
        # previews from PBI on disk (reload strip of memory)
        hyb = cv2.imread(str(pbi_path), cv2.IMREAD_COLOR)
        if hyb is not None:
            prev = cv2.resize(hyb, (w, h), interpolation=cv2.INTER_AREA)
            half = cv2.resize(hyb, (w * 2, h * 2), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(prev_path), prev, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            cv2.imwrite(str(half_path), half, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            del hyb, prev, half
            gc.collect()

    doc = {
        "format": "ige.ncnn.fullframe_pbi",
        "format_version": "1.1",
        "default_pipeline": "write_raw_then_strip_pbi",
        "memsafe_default": True,
        "input": str(args.input),
        "input_sha256": sha256(args.input),
        "input_wh": [w, h],
        "engine": "NCNN_GENERAL_x4v3",
        "param": str(args.param),
        "bin": str(args.bin),
        "not_siax": True,
        "not_nmkd_siax": True,
        "pbi_mode": args.pbi_mode,
        "pbi_formula": "hyb = C(LP)×(Y_LP + ridge(dY)); LP=Lanczos4×4 strip"
        if args.pbi_mode == "luma_only"
        else None,
        "tile": args.tile,
        "pad": args.pad,
        "scale": args.scale,
        "pbi_strip_base_px": args.pbi_strip,
        "raw": {
            "path": str(raw_path),
            "sha256": sha256(raw_path),
            **raw_meta,
        },
        "pbi": (
            {
                "path": str(pbi_path),
                "sha256": sha256(pbi_path),
                **pbi_meta,
            }
            if args.pbi_mode == "luma_only"
            else pbi_meta
        ),
        "preview": str(prev_path) if prev_path.exists() else None,
        "half": str(half_path) if half_path.exists() else None,
        "output_wh": [w * args.scale, h * args.scale],
        "wall_s": round(time.time() - t_all, 3),
        "device": "cpu_pyncnn",
        "vulkan": False,
        "quality_qualified": False,
        "final_acceptance": False,
        "e3_speed_claim": False,
        "limits": [
            "Default refuses all-in-RAM PBI; OOM risk at 7k-class float canvases.",
            "NCNN model must match in0/out0 SRVGG compact export (pnnx).",
            "Not a quality PASS.",
        ],
        "asof": datetime.now(timezone.utc).isoformat(),
    }
    result_path = out_dir / f"{args.stem}_RESULT.json"
    result_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "result": str(result_path), "wall_s": doc["wall_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
