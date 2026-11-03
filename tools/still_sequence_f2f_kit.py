#!/usr/bin/env python3
"""Still-sequence F2F kit — NO image-to-video.

Components:
  C1 FrameBank  C2 Metrics  C3 Layout  C4 Encode  C5 Report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --- C1 ---
def c1_frame_bank(paths: List[Path]) -> dict:
    if not paths:
        raise SystemExit("C1 fail-closed: no frames")
    items = []
    wh0 = None
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB")
        wh = im.size
        if wh0 is None:
            wh0 = wh
        elif wh != wh0:
            raise SystemExit(f"C1 fail-closed: size mismatch {p} {wh} vs {wh0}")
        items.append(
            {
                "index": i,
                "path": str(p),
                "sha256": sha256_file(p),
                "width": wh[0],
                "height": wh[1],
            }
        )
    return {
        "component": "C1_FrameBank",
        "n_frames": len(items),
        "width": wh0[0],
        "height": wh0[1],
        "frames": items,
    }


# --- C2 ---
def c2_metrics(paths: List[Path], max_pairs: int | None = None) -> dict:
    try:
        import cv2  # type: ignore
    except Exception:
        cv2 = None
    pairs = []
    n = len(paths)
    lim = n - 1 if max_pairs is None else min(n - 1, max_pairs)
    for i in range(lim):
        a = np.asarray(Image.open(paths[i]).convert("RGB"), dtype=np.float32)
        b = np.asarray(Image.open(paths[i + 1]).convert("RGB"), dtype=np.float32)
        d = np.abs(a - b)
        mae = float(d.mean())
        p95 = float(np.percentile(d.reshape(-1), 95))
        flow_p50 = None
        if cv2 is not None:
            g0 = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2GRAY)
            g1 = cv2.cvtColor(b.astype(np.uint8), cv2.COLOR_RGB2GRAY)
            flow = cv2.calcOpticalFlowFarneback(g0, g1, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            flow_p50 = float(np.median(mag))
        pairs.append(
            {
                "pair": f"T{i:04d}->T{i+1:04d}",
                "mae": mae,
                "p95": p95,
                "flow_p50": flow_p50,
            }
        )
    maes = [p["mae"] for p in pairs] or [0.0]
    return {
        "component": "C2_Metrics",
        "sampling": "still_adjacent",
        "not_native_cinema_dt_unless_labeled": True,
        "n_pairs": len(pairs),
        "mae_mean": float(np.mean(maes)),
        "mae_p50": float(np.median(maes)),
        "pairs": pairs,
    }


# --- C3 ---
def c3_filmstrip(paths: List[Path], out: Path, thumb_h: int = 160, max_n: int = 24) -> Path:
    sel = paths if len(paths) <= max_n else [paths[i] for i in np.linspace(0, len(paths) - 1, max_n, dtype=int)]
    thumbs = []
    for p in sel:
        im = Image.open(p).convert("RGB")
        w = int(im.width * (thumb_h / im.height))
        thumbs.append(im.resize((w, thumb_h), Image.Resampling.LANCZOS))
    gap = 4
    W = sum(t.width for t in thumbs) + gap * (len(thumbs) + 1)
    H = thumb_h + 28
    canvas = Image.new("RGB", (W, H), (18, 18, 22))
    draw = ImageDraw.Draw(canvas)
    x = gap
    for i, t in enumerate(thumbs):
        canvas.paste(t, (x, 20))
        draw.text((x + 4, 2), f"{i}", fill=(220, 220, 220))
        x += t.width + gap
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def c3_grid(paths: List[Path], out: Path, cols: int = 6, cell: int = 200) -> Path:
    n = min(len(paths), cols * 4)
    rows = (n + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell, rows * cell), (12, 12, 16))
    for i in range(n):
        im = Image.open(paths[i]).convert("RGB")
        im.thumbnail((cell - 4, cell - 4), Image.Resampling.LANCZOS)
        r, c = divmod(i, cols)
        ox = c * cell + (cell - im.width) // 2
        oy = r * cell + (cell - im.height) // 2
        canvas.paste(im, (ox, oy))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


# --- C4 ---
def c4_encode_mp4(paths: List[Path], out_mp4: Path, fps: float, work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    # normalize names frame_0000.png ...
    for i, p in enumerate(paths):
        dst = work / f"frame_{i:04d}.png"
        if not dst.exists() or dst.resolve() != p.resolve():
            Image.open(p).convert("RGB").save(dst)
    dur = len(paths) / float(fps)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    # scale/crop optional: keep source size; force even dims
    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1,fps={},format=yuv420p".format(fps)
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(work / "frame_%04d.png"),
        "-f",
        "lavfi",
        "-t",
        f"{dur:.6f}",
        "-i",
        "anullsrc=r=48000:cl=stereo",
        "-vf",
        vf,
        "-af",
        "aresample=48000,aformat=channel_layouts=stereo",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        str(out_mp4),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"C4 ffmpeg fail: {r.stderr[-2000:]}")
    return {
        "component": "C4_Encode",
        "path": str(out_mp4),
        "fps_playback": fps,
        "duration_s": dur,
        "motion_source": "still_playback",
        "audio": "silence_anullsrc",
        "not_image_to_video": True,
    }


# --- C5 ---
def c5_report(out: Path, bank: dict, metrics: dict, layouts: dict, encode: dict | None) -> Path:
    rep = {
        "format": "ige.still_sequence_f2f",
        "format_version": "1.0",
        "mode": "still_sequence_f2f",
        "not_image_to_video": True,
        "forbidden_tools_for_this_mode": [
            "imagine_image_to_video",
            "imagine_text_to_video",
            "imagine_reference_to_video",
        ],
        "components": {
            "C1": bank,
            "C2": metrics,
            "C3": layouts,
            "C4": encode,
        },
        "quality_qualified": False,
        "final_acceptance": False,
        "e3_speed_claim": False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Still-sequence F2F kit (no I2V)")
    ap.add_argument("--frames-dir", type=Path, required=True)
    ap.add_argument("--glob", default="*.png")
    ap.add_argument("--fps", type=float, default=24.0)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-metric-pairs", type=int, default=None)
    ap.add_argument("--filmstrip", action="store_true")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--mp4", action="store_true")
    ap.add_argument("--metrics", action="store_true")
    args = ap.parse_args()

    paths = sorted(args.frames_dir.glob(args.glob))
    if not paths:
        # also try recursive common names
        paths = sorted(args.frames_dir.glob("**/n_*.png")) + sorted(args.frames_dir.glob("**/frame_*.png"))
        paths = sorted(set(paths))
    bank = c1_frame_bank(paths)
    metrics = c2_metrics(paths, args.max_metric_pairs) if args.metrics else {"component": "C2_Metrics", "skipped": True}
    layouts = {"component": "C3_Layout"}
    if args.filmstrip:
        p = c3_filmstrip(paths, args.out_dir / "FIG_filmstrip.png")
        layouts["filmstrip"] = str(p)
    if args.grid:
        p = c3_grid(paths, args.out_dir / "FIG_grid.png")
        layouts["grid"] = str(p)
    encode = None
    if args.mp4:
        encode = c4_encode_mp4(paths, args.out_dir / "STILL_SEQUENCE.mp4", args.fps, args.out_dir / "_seq")
    report = c5_report(args.out_dir / "REPORT_STILL_SEQUENCE_F2F.json", bank, metrics, layouts, encode)
    print(json.dumps({"ok": True, "report": str(report), "n_frames": bank["n_frames"], "not_image_to_video": True}, indent=2))


if __name__ == "__main__":
    main()
