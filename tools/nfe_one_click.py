#!/usr/bin/env python3
"""NFE one-click: bolt-check → bootstrap → plan → STICK attach → optional procedural/verify/encode.

Examples:
  python tools/nfe_one_click.py --master path/F0.png --job-id nfe_e107 --out-dir runs/nfe/e107
  python tools/nfe_one_click.py --master F0.png --job-id x --out-dir runs/nfe/x --procedural-steps 3 --encode
  python tools/nfe_one_click.py --bolt-only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ige.nfe import FrameworkManifest, TemporalState, attach_stick, bolt_check  # noqa: E402


def run_py(script: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="NFE one-click orchestrator")
    ap.add_argument("--master", type=Path, default=None)
    ap.add_argument("--job-id", default="nfe_job")
    ap.add_argument("--out-dir", type=Path, default=Path("runs/nfe/default"))
    ap.add_argument("--asset-id", default=None)
    ap.add_argument("--max-side", type=int, default=1280)
    ap.add_argument("--phase", default=None)
    ap.add_argument("--procedural-steps", type=int, default=0, help="plumbing only; not product G")
    ap.add_argument("--encode", action="store_true", help="C1-C5 encode accepted/procedural frames if any")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--bolt-only", action="store_true")
    ap.add_argument("--verify-f2f", action="store_true", help="run siax_next_frame_f2f_verify on frames")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 0 bolt
    bc = bolt_check(ROOT)
    (out / "BOLT_CHECK.json").write_text(json.dumps(bc, indent=2), encoding="utf-8")
    FrameworkManifest().save(out / "FRAMEWORK_MANIFEST.json")
    FrameworkManifest().save(ROOT / "docs/evidence/NFE_FRAMEWORK_MANIFEST.json")

    if args.bolt_only:
        print(json.dumps({"ok": bc.get("core_ok"), "bolt": bc}, indent=2))
        return 0 if bc.get("core_ok") else 1

    if not args.master:
        print(json.dumps({"ok": False, "error": "--master required unless --bolt-only"}, indent=2))
        return 2

    pilot = ROOT / "tools/nfe_next_frame_pilot.py"
    # 1 bootstrap
    r = run_py(
        pilot,
        [
            "bootstrap",
            "--master",
            str(args.master),
            "--job-id",
            args.job_id,
            "--out-dir",
            str(out),
            "--max-side",
            str(args.max_side),
        ]
        + (["--asset-id", args.asset_id] if args.asset_id else []),
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        return r.returncode
    state_path = out / "state.json"

    # 2 plan + stick
    r2 = run_py(pilot, ["plan", "--state", str(state_path)] + (["--phase", args.phase] if args.phase else []))
    stick_path = attach_stick(state_path, out / "STICK_NEXT.json", phase=args.phase)
    # copy stick as STICK_EVOLVE permanent name
    (out / "STICK_EVOLVE.json").write_text(stick_path.read_text(encoding="utf-8"), encoding="utf-8")

    steps_report = None
    if args.procedural_steps > 0:
        r3 = run_py(
            pilot,
            [
                "step-procedural",
                "--state",
                str(state_path),
                "--out-dir",
                str(out / "frames"),
                "--steps",
                str(args.procedural_steps),
            ],
        )
        steps_report = {"rc": r3.returncode, "stdout_tail": (r3.stdout or "")[-500:]}

    encode_report = None
    if args.encode:
        frames_dir = out / "frames"
        if not frames_dir.exists():
            frames_dir = out / "accepted"
        kit = ROOT / "tools/still_sequence_f2f_kit.py"
        if kit.exists() and frames_dir.exists() and any(frames_dir.glob("*.png")):
            enc_out = out / "encode"
            enc_out.mkdir(parents=True, exist_ok=True)
            # still kit may need specific CLI — try common flags
            r4 = run_py(
                kit,
                [
                    "--frames-dir",
                    str(frames_dir),
                    "--glob",
                    "*.png",
                    "--fps",
                    str(args.fps),
                    "--out-dir",
                    str(enc_out),
                ],
            )
            encode_report = {"rc": r4.returncode, "stdout_tail": (r4.stdout or r4.stderr or "")[-400:]}
        else:
            encode_report = {"rc": None, "note": "no frames or kit missing"}

    verify_report = None
    if args.verify_f2f:
        v = ROOT / "tools/siax_next_frame_f2f_verify.py"
        frames_dir = out / "frames"
        if v.exists() and frames_dir.exists():
            r5 = run_py(
                v,
                [
                    "--frames-dir",
                    str(frames_dir),
                    "--pattern",
                    "*.png",
                    "--out-dir",
                    str(out / "f2f_verify"),
                    "--max-frames",
                    "12",
                ],
            )
            verify_report = {"rc": r5.returncode, "stdout_tail": (r5.stdout or r5.stderr or "")[-400:]}

    summary = {
        "format": "ige.nfe.one_click_result",
        "format_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "job_id": args.job_id,
        "out_dir": str(out),
        "bolt_core_ok": bc.get("core_ok"),
        "state": str(state_path),
        "stick": str(out / "STICK_EVOLVE.json"),
        "stick_prompt": str(out / "STICK_NEXT.prompt.txt") if (out / "STICK_NEXT.prompt.txt").exists() else str(stick_path.with_suffix(".prompt.txt")),
        "bootstrap_stdout": (r.stdout or "")[:400],
        "plan_rc": r2.returncode,
        "procedural": steps_report,
        "encode": encode_report,
        "verify_f2f": verify_report,
        "not_image_to_video": True,
        "note": "STICK attached for I2I evolve; procedural_steps is plumbing only if used",
        "quality_qualified": False,
        "final_acceptance": False,
        "cinematic_product": False,
    }
    (out / "ONE_CLICK_RESULT.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if bc.get("core_ok") and r.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
