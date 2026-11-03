#!/usr/bin/env python3
"""NFE-P0 pilot: bootstrap F0, emit I2I request packages, optional local generators.

Does NOT call I2V. Optical-flow morph is NOT a generator — only validators may use flow metrics.

Examples:
  # Bootstrap state from master still
  python tools/nfe_next_frame_pilot.py bootstrap \\
    --master path/to/F0.png --job-id nfe_e107 --out-dir runs/nfe/job1

  # Dry-run motion + prompt for next step (no generation)
  python tools/nfe_next_frame_pilot.py plan --state runs/nfe/job1/state.json

  # Register an externally produced next still (after I2I) and validate
  python tools/nfe_next_frame_pilot.py accept-candidate \\
    --state runs/nfe/job1/state.json --candidate path/to/F1.png \\
    --frame-origin i2i_next_still

  # Local procedural generator ONLY for plumbing tests (NOT product next-frame)
  python tools/nfe_next_frame_pilot.py step-procedural \\
    --state runs/nfe/job1/state.json --out-dir runs/nfe/job1/frames --steps 3
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ige.nfe import (  # noqa: E402
    FrameRef,
    MotionCompiler,
    NextFrameLoop,
    TemporalState,
    TemporalValidator,
)
from ige.nfe.state import sha256_file  # noqa: E402


def cmd_bootstrap(args: argparse.Namespace) -> int:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    master = Path(args.master)
    # copy/normalize pointer
    dest = out / "F0000_master.png"
    from PIL import Image
    im = Image.open(master).convert("RGB")
    if args.max_side and max(im.size) > args.max_side:
        s = args.max_side / max(im.size)
        im = im.resize((int(im.size[0] * s), int(im.size[1] * s)), Image.Resampling.LANCZOS)
    im.save(dest)
    st = TemporalState()
    st.bootstrap(dest, job_id=args.job_id, asset_id=args.asset_id)
    st.save(out / "state.json")
    req = {
        "format": "ige.nfe.i2i_request",
        "for_t": 1,
        "f_t": st.current_f.path if st.current_f else None,
        "k": st.master_k.path if st.master_k else None,
        "prompt": MotionCompiler().compile(1).scene_lock_prompt(),
        "forbidden": ["i2v", "optical_flow_as_generation"],
        "not_image_to_video": True,
    }
    (out / "NEXT_I2I_REQUEST.json").write_text(json.dumps(req, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "state": str(out / "state.json"), "f0": str(dest), "sha": st.current_f.sha256 if st.current_f else None}, indent=2))
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    st = TemporalState.load(Path(args.state))
    delta = MotionCompiler().compile(st.t_index + 1, args.phase)
    pack = {
        "format": "ige.nfe.i2i_request",
        "job_id": st.job_id,
        "for_t": st.t_index + 1,
        "f_t": st.current_f.path if st.current_f else None,
        "f_tm1": st.prev_f.path if st.prev_f else None,
        "k": st.master_k.path if st.master_k else None,
        "reanchor": st.should_reanchor() or ((st.t_index + 1) % st.reanchor_every == 0),
        "delta_s": delta.to_dict(),
        "prompt": delta.scene_lock_prompt(),
        "forbidden": ["i2v", "optical_flow_as_generation"],
        "not_image_to_video": True,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = Path(args.out) if args.out else Path(args.state).parent / f"I2I_REQUEST_t{st.t_index+1}.json"
    out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print(json.dumps(pack, indent=2))
    return 0


def cmd_accept(args: argparse.Namespace) -> int:
    st = TemporalState.load(Path(args.state))
    assert st.current_f and st.master_k
    cand_path = Path(args.candidate)
    next_t = st.t_index + 1
    # store into frames dir
    frames = Path(args.state).parent / "accepted"
    frames.mkdir(parents=True, exist_ok=True)
    dest = frames / f"F{next_t:04d}.png"
    from PIL import Image
    Image.open(cand_path).convert("RGB").save(dest)
    cand = FrameRef.from_path(dest, t_index=next_t, frame_origin=args.frame_origin)
    delta = MotionCompiler().compile(next_t, args.phase)
    val = TemporalValidator(
        mae_min=args.mae_min,
        mae_max=args.mae_max,
        flow_p50_max=args.flow_max,
    ).validate(st.current_f, cand, st.master_k, delta)
    report = {
        "format": "ige.nfe.step_result",
        "accepted": val.ok,
        "validation": val.to_dict(),
        "candidate": cand.__dict__,
        "not_image_to_video": True,
        "quality_qualified": False,
        "final_acceptance": False,
    }
    (Path(args.state).parent / f"STEP_t{next_t}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if val.ok:
        st.advance_accept(cand, delta.to_dict())
        st.save(Path(args.state))
        print(json.dumps({"ok": True, "accepted": True, "t_index": st.t_index, "mae": val.mae, "flow_p50": val.flow_p50}, indent=2))
        return 0
    print(json.dumps({"ok": True, "accepted": False, "reasons": val.reasons, "mae": val.mae, "flow_p50": val.flow_p50}, indent=2))
    return 2


def _procedural_generator(state: TemporalState, delta, out_path: Path) -> FrameRef:
    """Plumbing-only generator: tiny remap of current frame. NOT product next-frame."""
    import numpy as np
    from PIL import Image
    try:
        import cv2
    except ImportError as e:
        raise SystemExit(f"cv2 required for step-procedural: {e}")
    assert state.current_f
    im = np.asarray(Image.open(state.current_f.path).convert("RGB"), np.float32)
    h, w = im.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = (state.t_index + 1) * 0.15
    dx = 1.2 * np.sin(t + xx / 90.0)
    dy = 1.5 * np.cos(t * 1.3 + yy / 100.0)
    map_x = (xx + dx).astype(np.float32)
    map_y = (yy + dy).astype(np.float32)
    out = cv2.remap(im, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(out_path)
    return FrameRef.from_path(out_path, t_index=state.t_index + 1, frame_origin="procedural_cv")



def cmd_stick(args: argparse.Namespace) -> int:
    from ige.nfe import attach_stick
    out = attach_stick(Path(args.state), Path(args.out) if args.out else None, phase=args.phase)
    print(json.dumps({"ok": True, "stick": str(out), "prompt": str(out.with_suffix(".prompt.txt"))}, indent=2))
    return 0

def cmd_step_procedural(args: argparse.Namespace) -> int:
    st = TemporalState.load(Path(args.state))
    out_dir = Path(args.out_dir)
    loop = NextFrameLoop(
        st,
        generator=_procedural_generator,
        validator=TemporalValidator(mae_min=0.05, mae_max=40.0, flow_p50_max=15.0),
        max_retries=args.retries,
    )
    results = []
    for i in range(args.steps):
        r = loop.step(out_dir)
        results.append(r.to_dict())
        if not r.accepted:
            break
    st.save(Path(args.state))
    summary = {
        "format": "ige.nfe.pilot_procedural",
        "note": "procedural_cv generator is PLUMBING ONLY — not product next-frame",
        "not_image_to_video": True,
        "steps": results,
        "t_index": st.t_index,
        "quality_qualified": False,
        "final_acceptance": False,
    }
    (Path(args.state).parent / "PILOT_PROCEDURAL.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if all(x["accepted"] for x in results) else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="NFE next-frame pilot (still-unit, no I2V)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bootstrap")
    b.add_argument("--master", type=Path, required=True)
    b.add_argument("--job-id", required=True)
    b.add_argument("--out-dir", type=Path, required=True)
    b.add_argument("--asset-id", default=None)
    b.add_argument("--max-side", type=int, default=1280)
    b.set_defaults(func=cmd_bootstrap)

    p = sub.add_parser("plan")
    p.add_argument("--state", required=True)
    p.add_argument("--phase", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_plan)

    a = sub.add_parser("accept-candidate")
    a.add_argument("--state", required=True)
    a.add_argument("--candidate", required=True)
    a.add_argument("--frame-origin", default="i2i_next_still")
    a.add_argument("--phase", default=None)
    a.add_argument("--mae-min", type=float, default=0.3)
    a.add_argument("--mae-max", type=float, default=35.0)
    a.add_argument("--flow-max", type=float, default=8.0)
    a.set_defaults(func=cmd_accept)

    st = sub.add_parser("stick")
    st.add_argument("--state", required=True)
    st.add_argument("--phase", default=None)
    st.add_argument("--out", default=None)
    st.set_defaults(func=cmd_stick)

    s = sub.add_parser("step-procedural")
    s.add_argument("--state", required=True)
    s.add_argument("--out-dir", type=Path, required=True)
    s.add_argument("--steps", type=int, default=3)
    s.add_argument("--retries", type=int, default=2)
    s.set_defaults(func=cmd_step_procedural)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
