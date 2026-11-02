#!/usr/bin/env python3
"""Local pull agent: process HERE→PC SPM requests from inbox/.

Run inside repo .venv on the GPU PC:

  python tools/spm_here_pull.py --once
  python tools/spm_here_pull.py --watch --interval 2

Default roots (override with env SPM_HANDOFF_ROOT):
  D:\\s3_share\\spm_handoff\\inbox|outbox|done   (Windows typical)
  or ./runs/spm_handoff/...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("SPM_HANDOFF_ROOT") or r"D:\s3_share\spm_handoff"),
    )
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--job-store", type=Path, default=Path("runs/spm_local"))
    args = ap.parse_args()
    if not args.once and not args.watch:
        args.once = True

    from ige.spm_local.handoff import list_pending, process_one

    inbox = args.root / "inbox"
    outbox = args.root / "outbox"
    done = args.root / "done"
    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    done.mkdir(parents=True, exist_ok=True)

    def tick() -> int:
        n = 0
        for p in list_pending(inbox):
            print(f"processing {p.name}", flush=True)
            try:
                res = process_one(
                    p, outbox=outbox, done_dir=done, job_store=args.job_store
                )
                print(json.dumps({
                    "ok": res.get("ok"),
                    "request_id": res.get("request_id"),
                    "output_path": res.get("output_path"),
                    "output_sha256": res.get("output_sha256"),
                    "result_json": str(outbox / f"{res['request_id']}_result.json"),
                }, indent=2, ensure_ascii=False), flush=True)
                n += 1
            except Exception as exc:
                err = {
                    "ok": False,
                    "request_file": str(p),
                    "error": str(exc),
                }
                (outbox / f"{p.stem}_error.json").write_text(
                    json.dumps(err, indent=2) + "\n", encoding="utf-8"
                )
                print(json.dumps(err, indent=2), flush=True)
                # leave request in inbox for retry? move to done with error tag
                try:
                    p.replace(done / f"ERR_{p.name}")
                except Exception:
                    pass
        return n

    if args.once:
        tick()
        return 0
    print(f"watching {inbox} every {args.interval}s", flush=True)
    while True:
        tick()
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
