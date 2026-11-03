"""Playback-only optical-flow frameback densify between ordered stills.

FORBIDDEN as generator G. Provenance: frameback_flow_playback_only.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def warp_blend(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    import cv2

    g0 = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    g1 = cv2.cvtColor(b.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    fw = cv2.calcOpticalFlowFarneback(g0, g1, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    bw = cv2.calcOpticalFlowFarneback(g1, g0, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    h, w = g0.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    map_f = np.stack([xx + fw[..., 0] * t, yy + fw[..., 1] * t], -1)
    map_b = np.stack([xx + bw[..., 0] * (1 - t), yy + bw[..., 1] * (1 - t)], -1)
    A = cv2.remap(a, map_f, None, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    B = cv2.remap(b, map_b, None, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return (1 - t) * A + t * B


def densify_frameback(
    src_paths: list[Path],
    out_dir: Path,
    *,
    mids_per_gap: int = 1,
    fps: int = 20,
    encode_mp4: bool = True,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    src_paths = [Path(p) for p in src_paths]
    if len(src_paths) < 2:
        raise ValueError("need >=2 stills for frameback")
    if mids_per_gap < 1:
        raise ValueError("mids_per_gap >= 1")

    # unify size to first frame
    base = Image.open(src_paths[0]).convert("RGB")
    WH = base.size

    def load(p: Path) -> np.ndarray:
        im = Image.open(p).convert("RGB")
        if im.size != WH:
            im = im.resize(WH, Image.Resampling.LANCZOS)
        return np.asarray(im, np.float32)

    meta = []
    out_i = 0
    prev = load(src_paths[0])
    Image.fromarray(np.clip(prev, 0, 255).astype(np.uint8)).save(out_dir / f"F{out_i:04d}.png")
    meta.append({"i": out_i, "kind": "src", "src": src_paths[0].name})
    out_i += 1
    for k in range(1, len(src_paths)):
        cur = load(src_paths[k])
        for m in range(1, mids_per_gap + 1):
            t = m / (mids_per_gap + 1)
            mid = warp_blend(prev, cur, t)
            Image.fromarray(np.clip(mid, 0, 255).astype(np.uint8)).save(out_dir / f"F{out_i:04d}.png")
            meta.append({"i": out_i, "kind": f"frameback_t{t:.3f}", "between": [src_paths[k - 1].name, src_paths[k].name]})
            out_i += 1
        Image.fromarray(np.clip(cur, 0, 255).astype(np.uint8)).save(out_dir / f"F{out_i:04d}.png")
        meta.append({"i": out_i, "kind": "src", "src": src_paths[k].name})
        out_i += 1
        prev = cur

    n = out_i
    mp4 = None
    if encode_mp4:
        mp4 = out_dir.parent / f"OUT_FRAMEBACK_m{mids_per_gap}_n{n}.mp4"
        dur = n / float(fps)
        subprocess.run(
            [
                "ffmpeg", "-y", "-framerate", str(fps), "-i", str(out_dir / "F%04d.png"),
                "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo",
                "-vf", f"scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1,fps={fps},format=yuv420p",
                "-af", "aresample=48000,aformat=channel_layouts=stereo",
                "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "128k",
                "-shortest", str(mp4),
            ],
            check=True,
            capture_output=True,
        )
    report = {
        "format": "ige.nfe.frameback_result",
        "n_src": len(src_paths),
        "n_out": n,
        "mids_per_gap": mids_per_gap,
        "fps": fps,
        "mp4": str(mp4) if mp4 else None,
        "not_image_to_video": True,
        "optical_flow_as_generation": False,
        "frameback_is_playback_only": True,
        "meta": meta,
        "quality_qualified": False,
    }
    (out_dir / "FRAMEBACK_RESULT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
