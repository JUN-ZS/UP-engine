#!/usr/bin/env python3
"""True 60fps NFE pilot helper: gate + bank encode. G (I2I) is external Imagine.

Usage after agent drops accepted F0000..F00NN.png:
  python tools/nfe_true_60fps_i2i_pilot.py gate --job-dir runs/nfe/true60_i2i_17373
  python tools/nfe_true_60fps_i2i_pilot.py encode --job-dir runs/nfe/true60_i2i_17373 --fps 60
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

def collect(job: Path):
    acc = job / "accepted"
    paths = sorted(acc.glob("F*.png"))
    if not paths and (job / "frames").exists():
        paths = sorted((job / "frames").glob("F*.png"))
    return paths

def cmd_gate(job: Path) -> int:
    from ige.nfe.validate import TemporalValidator
    from ige.nfe.state import FrameRef, sha256_file
    from ige.nfe.motion import MotionDelta
    paths = collect(job)
    if len(paths) < 2:
        print(json.dumps({"ok": False, "error": "need >=2 accepted frames"})); return 2
    stick = json.loads((job / "STICK_TRUE60.json").read_text()) if (job / "STICK_TRUE60.json").exists() else {}
    vcfg = stick.get("validator") or {}
    val = TemporalValidator(
        mae_min=float(vcfg.get("mae_min", 0.15)),
        mae_max=float(vcfg.get("mae_max", 22.0)),
        flow_p50_max=float(vcfg.get("flow_p50_max", 4.0)),
        enable_ddxx=bool(vcfg.get("enable_ddxx", True)),
        ddxx_hard=bool(vcfg.get("ddxx_hard", False)),
    )
    delta = MotionDelta(phase="true60_micro", dynamic_allow=["body_micro","hair_lag","mud_rain"], static_lock=["camera","identity_armor"])
    reports = []
    fails = 0
    for i in range(len(paths) - 1):
        a = FrameRef(path=str(paths[i]), sha256=sha256_file(paths[i]), t_index=i)
        b = FrameRef(path=str(paths[i + 1]), sha256=sha256_file(paths[i + 1]), t_index=i + 1)
        rep = val.validate(a, b, None, delta, size=(1280, 720))
        d = rep.to_dict()
        d["pair"] = f"F{i:04d}->F{i+1:04d}"
        reports.append(d)
        if not rep.ok:
            fails += 1
    out = {
        "format": "ige.nfe.true60_gate_report",
        "n_frames": len(paths),
        "n_pairs": len(reports),
        "n_fail": fails,
        "all_ok": fails == 0,
        "not_frameback": True,
        "not_optical_flow_as_generation": True,
        "not_image_to_video": True,
        "generator_G": "i2i_next_still_only",
        "pairs": reports,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quality_qualified": False,
        "final_acceptance": False,
    }
    (job / "GATE_REPORT.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"ok": out["all_ok"], "n_frames": len(paths), "n_fail": fails, "report": str(job / "GATE_REPORT.json")}, indent=2))
    return 0 if out["all_ok"] else 1

def cmd_encode(job: Path, fps: int) -> int:
    paths = collect(job)
    if len(paths) < 2:
        print(json.dumps({"ok": False, "error": "need frames"})); return 2
    seq = job / "encode_seq"
    seq.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(paths):
        dest = seq / f"F{i:04d}.png"
        if dest.resolve() != p.resolve():
            dest.write_bytes(p.read_bytes())
    mp4 = job / f"OUT_TRUE60_N{len(paths)}_fps{fps}.mp4"
    dur = len(paths) / float(fps)
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(fps), "-i", str(seq / "F%04d.png"),
        "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo",
        "-vf", f"scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1,fps={fps},format=yuv420p",
        "-af", "aresample=48000,aformat=channel_layouts=stereo",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "128k",
        "-shortest", str(mp4),
    ], check=True, capture_output=True)
    rep = {
        "format": "ige.nfe.true60_encode",
        "n_frames": len(paths),
        "fps": fps,
        "duration_s": dur,
        "mp4": str(mp4),
        "not_frameback": True,
        "not_image_to_video": True,
        "generator_G": "i2i_next_still_bank",
        "quality_qualified": False,
    }
    (job / "ENCODE_RESULT.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=2))
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gate", "encode"])
    ap.add_argument("--job-dir", type=Path, required=True)
    ap.add_argument("--fps", type=int, default=60)
    args = ap.parse_args()
    if args.cmd == "gate":
        return cmd_gate(args.job_dir)
    return cmd_encode(args.job_dir, args.fps)

if __name__ == "__main__":
    raise SystemExit(main())
