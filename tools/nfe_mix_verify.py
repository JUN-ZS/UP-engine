#!/usr/bin/env python3
"""NFE MIX verify: DDXX consecutive chain + optional frameback on ordered stills.

Example:
  python tools/nfe_mix_verify.py --frames-dir runs/nfe/nfe_p0_c60_x30/accepted --out-dir runs/nfe/mix_c60
  python tools/nfe_mix_verify.py --job-dir runs/nfe/nfe_p0_c60_x30 --frameback 1 --encode
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ige.nfe.ddxx_gate import chain_ddxx_reports  # noqa: E402
from ige.nfe.frameback import densify_frameback  # noqa: E402


def collect_frames(job_dir: Path | None, frames_dir: Path | None) -> list[Path]:
    paths: list[Path] = []
    if job_dir:
        job_dir = Path(job_dir)
        master = job_dir / "F0000_master.png"
        if master.exists():
            paths.append(master)
        acc = job_dir / "accepted"
        if acc.exists():
            paths.extend(sorted(acc.glob("F*.png")))
        if not paths:
            fr = job_dir / "frames"
            if fr.exists():
                paths.extend(sorted(fr.glob("*.png")))
    if frames_dir:
        paths = sorted(Path(frames_dir).glob("*.png"))
    # unique preserve order
    seen = set()
    out = []
    for p in paths:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-dir", type=Path, default=None)
    ap.add_argument("--frames-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=Path("runs/nfe/mix_verify"))
    ap.add_argument("--frameback", type=int, default=0, help="mids per gap; 0=skip")
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--encode", action="store_true")
    ap.add_argument("--max-side", type=int, default=1280)
    args = ap.parse_args()

    frames = collect_frames(args.job_dir, args.frames_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if len(frames) < 2:
        print(json.dumps({"ok": False, "error": "need >=2 frames", "found": [str(p) for p in frames]}, indent=2))
        return 2

    size = (args.max_side, int(round(args.max_side * 9 / 16)))
    # keep 16:9 if max-side is width
    # probe first frame
    from PIL import Image

    w, h = Image.open(frames[0]).size
    if w >= h:
        size = (min(args.max_side, w), int(round(min(args.max_side, w) * h / w)))
    else:
        size = (int(round(min(args.max_side, h) * w / h)), min(args.max_side, h))

    ddxx = chain_ddxx_reports(frames, size=size, out_json=out / "DDXX_CHAIN.json")

    fb = None
    if args.frameback > 0:
        fb = densify_frameback(
            frames,
            out / f"frameback_m{args.frameback}",
            mids_per_gap=args.frameback,
            fps=args.fps,
            encode_mp4=args.encode or True,
        )

    # frontier trend (use sim_p95 / mae as series — same spirit as verify figures)
    frontier = []
    for p in ddxx.get("pairs") or []:
        frontier.append({
            "pair": p["pair"],
            "mae": p.get("mae_full"),
            "sim_p95": p.get("sim_p95"),
            "flow_p50": p.get("flow_p50"),
            "gate": p.get("gate"),
        })

    report = {
        "format": "ige.nfe.mix_verify_result",
        "format_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_frames": len(frames),
        "frames": [str(p) for p in frames],
        "ddxx_chain": str(out / "DDXX_CHAIN.json"),
        "ddxx_all_ok": ddxx.get("all_ok"),
        "frontier_series": frontier,
        "frameback": fb,
        "mixed_from": [
            "NFE C0 state/accept",
            "DDXX SIFT+Umeyama/Homography (figures GT anchors / residual)",
            "seam/frontier trend (continuous frame verify)",
            "FRAMEBACK flow densify (playback only)",
        ],
        "not_image_to_video": True,
        "optical_flow_as_generation": False,
        "quality_qualified": False,
        "final_acceptance": False,
        "cinematic_product": False,
    }
    (out / "MIX_VERIFY_RESULT.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False)[:2500])
    print("...")
    print(json.dumps({"ok": True, "out": str(out), "ddxx_all_ok": ddxx.get("all_ok"), "n_pairs": ddxx.get("n_pairs")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
