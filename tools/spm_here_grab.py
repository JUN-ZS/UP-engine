#!/usr/bin/env python3
"""Grok CLI / local: grab HERE package images from git package → local path → optional Siax.

Why: grok.com Custom MCP cannot pass Bearer; chat-save is manual.
This lets Grok CLI (or you) pull the image that was prepared in the HERE session
because it is versioned under packages/spm_here/<package_id>/.

Examples:
  python tools/spm_here_grab.py --list
  python tools/spm_here_grab.py --package warrior_mud_hammer --variant base
  python tools/spm_here_grab.py --package warrior_mud_hammer --variant base --run-siax

Does not call cloud Imagine. Does not require OAuth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    packages = root / "packages" / "spm_here"

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--package", default="warrior_mud_hammer")
    ap.add_argument("--variant", default="base", choices=("base", "master"))
    ap.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="default from manifest local_defaults or D:/s3_share/spm_in/warrior_BASE.jpg",
    )
    ap.add_argument("--run-siax", action="store_true", help="after grab, run handoff Siax once")
    ap.add_argument("--tile-size", type=int, default=0)
    ap.add_argument("--tile-pad", type=int, default=-1)
    ap.add_argument("--device", default="")
    args = ap.parse_args()

    if args.list:
        if not packages.is_dir():
            print(json.dumps({"packages": []}))
            return 0
        out = []
        for d in sorted(packages.iterdir()):
            man = d / "manifest.json"
            if man.is_file():
                m = json.loads(man.read_text(encoding="utf-8"))
                out.append({"package_id": m.get("package_id"), "path": str(d), "variants": list((m.get("variants") or {}).keys())})
        print(json.dumps({"packages": out}, indent=2, ensure_ascii=False))
        return 0

    pkg_dir = packages / args.package
    man_path = pkg_dir / "manifest.json"
    if not man_path.is_file():
        raise SystemExit(f"package not found: {pkg_dir} (git pull feat/upscale-s3-heterogeneous-runner-v0.1)")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    var = (man.get("variants") or {}).get(args.variant)
    if not var:
        raise SystemExit(f"variant {args.variant} missing")
    src = pkg_dir / var["file"]
    if not src.is_file():
        raise SystemExit(f"missing image file {src}")
    expect = var.get("sha256")
    actual = file_sha256(src)
    if expect and actual != expect:
        raise SystemExit(f"sha mismatch for {src}: {actual} != {expect}")

    loc = man.get("local_defaults") or {}
    dest = args.dest
    if dest is None:
        dest_dir = Path(loc.get("dest_dir") or r"D:\s3_share\spm_in")
        dest_name = loc.get("dest_name") or "warrior_BASE.jpg"
        if args.variant == "master":
            dest_name = "warrior_MASTER.jpg"
        dest = dest_dir / dest_name
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

    report = {
        "format": "ige.spm.here_grab_result",
        "ok": True,
        "package_id": man.get("package_id"),
        "variant": args.variant,
        "source_repo_file": str(src),
        "dest": str(dest.resolve()),
        "sha256": actual,
        "here_asset_id": var.get("here_asset_id"),
        "share_url": var.get("share_url"),
        "grok_cli_ready": True,
        "final_acceptance": False,
        "e3_speed_claim": False,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)

    if not args.run_siax:
        return 0

    # handoff request + pull once
    from ige.spm_local.handoff import new_request, write_request, process_one

    handoff = Path(loc.get("handoff_root") or r"D:\s3_share\spm_handoff")
    out_png = Path(loc.get("output_png") or (handoff / "outbox" / "warrior_SIAX4X.png"))
    siax = man.get("siax") or {}
    tile = args.tile_size or int(siax.get("tile_size") or 128)
    pad = args.tile_pad if args.tile_pad >= 0 else int(siax.get("tile_pad") or 8)
    device = args.device or siax.get("device") or "auto"

    req = new_request(
        input_path=str(dest),
        output_path=str(out_png),
        device=device,
        tile_size=tile,
        tile_pad=pad,
        note=f"grok_cli_grab {args.package}/{args.variant}",
        source_asset_hint=str(var.get("here_asset_id") or ""),
    )
    inbox = handoff / "inbox"
    outbox = handoff / "outbox"
    done = handoff / "done"
    write_request(inbox, req)
    result = process_one(
        inbox / f"{req['request_id']}.json",
        outbox=outbox,
        done_dir=done,
        job_store=root / "runs" / "spm_local",
    )
    print(json.dumps({
        "siax_ok": result.get("ok"),
        "request_id": result.get("request_id"),
        "output_path": result.get("output_path"),
        "output_sha256": result.get("output_sha256"),
        "device_used": result.get("device_used"),
        "result_json": str(outbox / f"{result['request_id']}_result.json"),
        "paste_result_json_to_chat": True,
    }, indent=2, ensure_ascii=False), flush=True)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
