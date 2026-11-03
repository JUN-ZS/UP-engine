#!/usr/bin/env python3
"""NFE one-click MIX: bolt → bootstrap → plan → STICK → optional procedural/encode/verify/DDXX/frameback.

Examples:
  python tools/nfe_one_click.py --master F0.png --job-id x --out-dir runs/nfe/x
  python tools/nfe_one_click.py --master F0.png --job-id x --out-dir runs/nfe/x --mix-all --frameback 1
  python tools/nfe_one_click.py --job-dir runs/nfe/nfe_p0_c60_x30 --mix-only --frameback 1
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

from ige.nfe import FrameworkManifest, attach_stick, bolt_check  # noqa: E402


def run_py(script: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="NFE one-click orchestrator (MIX capable)")
    ap.add_argument("--master", type=Path, default=None)
    ap.add_argument("--job-id", default="nfe_job")
    ap.add_argument("--out-dir", type=Path, default=Path("runs/nfe/default"))
    ap.add_argument("--job-dir", type=Path, default=None, help="existing job for --mix-only")
    ap.add_argument("--asset-id", default=None)
    ap.add_argument("--max-side", type=int, default=1280)
    ap.add_argument("--phase", default=None)
    ap.add_argument("--procedural-steps", type=int, default=0)
    ap.add_argument("--encode", action="store_true")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--bolt-only", action="store_true")
    ap.add_argument("--verify-f2f", action="store_true")
    ap.add_argument("--ddxx-gate", action="store_true", help="run consecutive DDXX chain on accepted")
    ap.add_argument("--frameback", type=int, default=0, help="mids per gap after accepted (playback only)")
    ap.add_argument("--mix-all", action="store_true", help="enable encode+verify-f2f+ddxx+frameback(1)")
    ap.add_argument("--mix-only", action="store_true", help="skip bootstrap; mix on --job-dir or --out-dir")
    args = ap.parse_args()

    if args.mix_all:
        args.encode = True
        args.verify_f2f = True
        args.ddxx_gate = True
        if args.frameback <= 0:
            args.frameback = 1

    out = Path(args.job_dir) if (args.mix_only and args.job_dir) else Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    bc = bolt_check(ROOT)
    (out / "BOLT_CHECK.json").write_text(json.dumps(bc, indent=2), encoding="utf-8")
    FrameworkManifest().save(out / "FRAMEWORK_MANIFEST.json")
    FrameworkManifest().save(ROOT / "docs/evidence/NFE_FRAMEWORK_MANIFEST.json")

    if args.bolt_only:
        print(json.dumps({"ok": bc.get("core_ok"), "bolt": bc}, indent=2))
        return 0 if bc.get("core_ok") else 1

    pilot = ROOT / "tools/nfe_next_frame_pilot.py"
    r = type("R", (), {"returncode": 0, "stdout": ""})()
    r2 = type("R", (), {"returncode": 0})()
    stick_path = out / "STICK_EVOLVE.json"
    state_path = out / "state.json"

    if not args.mix_only:
        if not args.master:
            print(json.dumps({"ok": False, "error": "--master required unless --bolt-only/--mix-only"}, indent=2))
            return 2
        r = run_py(
            pilot,
            [
                "bootstrap", "--master", str(args.master), "--job-id", args.job_id,
                "--out-dir", str(out), "--max-side", str(args.max_side),
            ]
            + (["--asset-id", args.asset_id] if args.asset_id else []),
        )
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr)
            return r.returncode
        r2 = run_py(pilot, ["plan", "--state", str(state_path)] + (["--phase", args.phase] if args.phase else []))
        sp = attach_stick(state_path, out / "STICK_NEXT.json", phase=args.phase)
        stick_path.write_text(sp.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        if not state_path.exists():
            print(json.dumps({"ok": False, "error": f"no state.json in {out}"}, indent=2))
            return 2

    steps_report = None
    if args.procedural_steps > 0 and not args.mix_only:
        r3 = run_py(
            pilot,
            ["step-procedural", "--state", str(state_path), "--out-dir", str(out / "frames"), "--steps", str(args.procedural_steps)],
        )
        steps_report = {"rc": r3.returncode, "stdout_tail": (r3.stdout or "")[-500:]}

    encode_report = None
    if args.encode:
        frames_dir = out / "accepted" if (out / "accepted").exists() else out / "frames"
        kit = ROOT / "tools/still_sequence_f2f_kit.py"
        if kit.exists() and frames_dir.exists() and any(frames_dir.glob("*.png")):
            enc_out = out / "encode"
            enc_out.mkdir(parents=True, exist_ok=True)
            r4 = run_py(kit, ["--frames-dir", str(frames_dir), "--glob", "*.png", "--fps", str(args.fps), "--out-dir", str(enc_out)])
            encode_report = {"rc": r4.returncode, "stdout_tail": (r4.stdout or r4.stderr or "")[-400:]}
        else:
            encode_report = {"rc": None, "note": "no frames or kit missing"}

    verify_report = None
    if args.verify_f2f:
        v = ROOT / "tools/siax_next_frame_f2f_verify.py"
        frames_dir = out / "accepted" if (out / "accepted").exists() else out / "frames"
        if v.exists() and frames_dir.exists() and any(frames_dir.glob("*.png")):
            r5 = run_py(
                v,
                ["--frames-dir", str(frames_dir), "--pattern", "*.png", "--out-dir", str(out / "f2f_verify"), "--max-frames", "24"],
            )
            verify_report = {"rc": r5.returncode, "stdout_tail": (r5.stdout or r5.stderr or "")[-400:]}
        else:
            verify_report = {"rc": None, "note": "verify tool or frames missing"}

    mix_report = None
    if args.ddxx_gate or args.frameback > 0 or args.mix_all or args.mix_only:
        mix = ROOT / "tools/nfe_mix_verify.py"
        mix_args = ["--job-dir", str(out), "--out-dir", str(out / "mix"), "--fps", str(args.fps if args.fps else 20)]
        if args.frameback > 0:
            mix_args += ["--frameback", str(args.frameback), "--encode"]
        r6 = run_py(mix, mix_args)
        mix_report = {
            "rc": r6.returncode,
            "stdout_tail": (r6.stdout or "")[-800:],
            "result": str(out / "mix" / "MIX_VERIFY_RESULT.json"),
        }

    summary = {
        "format": "ige.nfe.one_click_result",
        "format_version": "1.1",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "job_id": args.job_id,
        "out_dir": str(out),
        "bolt_core_ok": bc.get("core_ok"),
        "state": str(state_path) if state_path.exists() else None,
        "stick": str(stick_path) if stick_path.exists() else None,
        "bootstrap_stdout": (getattr(r, "stdout", None) or "")[:400],
        "plan_rc": getattr(r2, "returncode", None),
        "procedural": steps_report,
        "encode": encode_report,
        "verify_f2f": verify_report,
        "mix": mix_report,
        "flags": {
            "mix_all": bool(args.mix_all),
            "mix_only": bool(args.mix_only),
            "ddxx_gate": bool(args.ddxx_gate),
            "frameback": int(args.frameback),
            "encode": bool(args.encode),
            "verify_f2f": bool(args.verify_f2f),
        },
        "mixed_components": [
            "NFE bootstrap/plan/STICK",
            "DDXX consecutive SIFT+sim/homo gate",
            "seam/frontier series",
            "F2F verify tool (if present)",
            "FRAMEBACK densify (playback only)",
            "C1-C5 encode (if frames)",
        ],
        "not_image_to_video": True,
        "note": "MIX wires DDXX/N1 figure methods + NFE + frameback; G remains i2i_next_still only",
        "quality_qualified": False,
        "final_acceptance": False,
        "cinematic_product": False,
    }
    (out / "ONE_CLICK_RESULT.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    ok = bool(bc.get("core_ok"))
    if not args.mix_only:
        ok = ok and r.returncode == 0
    if mix_report and mix_report.get("rc") not in (0, None):
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
