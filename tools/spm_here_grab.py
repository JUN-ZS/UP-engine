#!/usr/bin/env python3
"""Grok CLI / local: grab HERE package images → safe local paths → optional Siax.

Naming rules (v1.1 — avoid Windows save/clobber errors):
  INPUT  dest:  {dest_dir}/{package_id}_{variant}{ext}   (stable; skip copy if SHA matches)
  OUTPUT png:   {outbox}/{package_id}_{variant}_t{tile}p{pad}_{request_id}.png  (always unique)
  Never overwrite a fixed warrior_SIAX4X.png by default (errno 22 / file lock on Windows).

Examples:
  python tools/spm_here_grab.py --list
  python tools/spm_here_grab.py --package warrior_mud_hammer --variant base
  python tools/spm_here_grab.py --package warrior_mud_hammer --variant base --run-siax
  python tools/spm_here_grab.py --package warrior_mud_hammer --variant base --run-siax --cell 256/16
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_cell(cell: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", cell or "")
    if not m:
        raise SystemExit(f"bad --cell {cell!r}; use e.g. 128/8, 256/16, 256/32")
    tile, pad = int(m.group(1)), int(m.group(2))
    if tile < 32 or pad < 0 or pad >= tile:
        raise SystemExit("tile must be >=32 and pad in [0, tile)")
    return tile, pad


def safe_copy(src: Path, dest: Path, *, force: bool) -> dict:
    """Copy with Windows-friendly behavior: skip if same SHA; atomic replace; no silent clobber without force when different."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_sha = file_sha256(src)
    if dest.is_file():
        try:
            dst_sha = file_sha256(dest)
        except OSError as exc:
            dst_sha = None
            if not force:
                # locked or unreadable — write sibling unique name
                alt = dest.with_name(f"{dest.stem}_{int(time.time())}{dest.suffix}")
                return safe_copy(src, alt, force=True) | {
                    "note": f"dest busy ({exc}); wrote alternate",
                    "requested_dest": str(dest),
                }
        if dst_sha == src_sha:
            return {
                "action": "skip_same_sha",
                "dest": str(dest.resolve()),
                "sha256": src_sha,
            }
        if not force:
            alt = dest.with_name(f"{dest.stem}_{src_sha[:8]}{dest.suffix}")
            if alt.is_file() and file_sha256(alt) == src_sha:
                return {
                    "action": "skip_same_sha_alt",
                    "dest": str(alt.resolve()),
                    "sha256": src_sha,
                    "note": "dest differed; reused content-addressed alt",
                }
            return safe_copy(src, alt, force=True) | {
                "note": "dest existed with different SHA; wrote content-addressed name (use --force-dest to replace)",
                "requested_dest": str(dest),
            }
    # atomic-ish: write temp then replace
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, dest)
    except OSError as exc:
        try:
            if tmp.is_file():
                tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
        except TypeError:
            if tmp.is_file():
                tmp.unlink()
        # last resort unique
        alt = dest.with_name(f"{dest.stem}_{int(time.time())}{dest.suffix}")
        shutil.copy2(src, alt)
        return {
            "action": "copy_fallback_unique",
            "dest": str(alt.resolve()),
            "sha256": src_sha,
            "error": f"{type(exc).__name__}: {exc}",
            "requested_dest": str(dest),
        }
    return {
        "action": "copied",
        "dest": str(dest.resolve()),
        "sha256": src_sha,
    }


def unique_out_png(
    outbox: Path,
    *,
    package_id: str,
    variant: str,
    tile: int,
    pad: int,
    request_id: str,
) -> Path:
    outbox.mkdir(parents=True, exist_ok=True)
    name = f"{package_id}_{variant}_t{tile}p{pad}_{request_id}.png"
    return outbox / name


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    packages = root / "packages" / "spm_here"

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--package", default="warrior_mud_hammer")
    ap.add_argument("--variant", default="base", choices=("base", "master"))
    ap.add_argument("--dest", type=Path, default=None, help="override input dest path")
    ap.add_argument(
        "--force-dest",
        action="store_true",
        help="replace existing input dest even if SHA differs",
    )
    ap.add_argument("--run-siax", action="store_true")
    ap.add_argument(
        "--cell",
        default="",
        help="tile/pad shorthand e.g. 256/16 (commercial default candidate). Overrides --tile-size/--tile-pad when set.",
    )
    ap.add_argument("--tile-size", type=int, default=0)
    ap.add_argument("--tile-pad", type=int, default=-1)
    ap.add_argument("--device", default="")
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="optional explicit output PNG; default is unique per request",
    )
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
                out.append(
                    {
                        "package_id": m.get("package_id"),
                        "path": str(d),
                        "variants": list((m.get("variants") or {}).keys()),
                        "cli": (m.get("grok_cli") or {}).get("grab_command"),
                    }
                )
        print(json.dumps({"packages": out, "how": "python tools/spm_here_grab.py --package ID --variant base [--run-siax] [--cell 256/16]"}, indent=2, ensure_ascii=False))
        return 0

    pkg_dir = packages / args.package
    man_path = pkg_dir / "manifest.json"
    if not man_path.is_file():
        raise SystemExit(
            f"package not found: {pkg_dir}\n"
            "git pull origin feat/upscale-s3-heterogeneous-runner-v0.1"
        )
    man = json.loads(man_path.read_text(encoding="utf-8"))
    package_id = str(man.get("package_id") or args.package)
    var = (man.get("variants") or {}).get(args.variant)
    if not var:
        raise SystemExit(f"variant {args.variant} missing in {man_path}")
    src = pkg_dir / var["file"]
    if not src.is_file():
        raise SystemExit(f"missing image file {src}")
    expect = var.get("sha256")
    actual = file_sha256(src)
    if expect and actual != expect:
        raise SystemExit(f"sha mismatch for {src}: {actual} != {expect}")

    loc = man.get("local_defaults") or {}
    dest_dir = Path(loc.get("dest_dir") or r"D:\s3_share\spm_in")
    # stable, package-scoped input name (avoids clobbering unrelated files)
    ext = Path(var["file"]).suffix or ".jpg"
    default_dest = dest_dir / f"{package_id}_{args.variant}{ext}"
    dest = Path(args.dest) if args.dest else default_dest

    copy_info = safe_copy(src, dest, force=bool(args.force_dest))
    dest_final = Path(copy_info["dest"])

    report = {
        "format": "ige.spm.here_grab_result",
        "format_version": "1.1",
        "ok": True,
        "package_id": package_id,
        "variant": args.variant,
        "source_repo_file": str(src),
        "dest": str(dest_final),
        "sha256": copy_info.get("sha256") or actual,
        "copy": copy_info,
        "here_asset_id": var.get("here_asset_id"),
        "share_url": var.get("share_url"),
        "naming": {
            "input_rule": "{dest_dir}/{package_id}_{variant}{ext}",
            "output_rule": "{outbox}/{package_id}_{variant}_t{tile}p{pad}_{request_id}.png",
            "no_fixed_warrior_SIAX4X_by_default": True,
        },
        "grok_cli_ready": True,
        "final_acceptance": False,
        "e3_speed_claim": False,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)

    if not args.run_siax:
        return 0

    from ige.spm_local.handoff import new_request, write_request, process_one

    handoff = Path(loc.get("handoff_root") or r"D:\s3_share\spm_handoff")
    siax = man.get("siax") or {}
    if args.cell:
        tile, pad = parse_cell(args.cell)
    else:
        tile = args.tile_size or int(siax.get("tile_size") or 128)
        pad = args.tile_pad if args.tile_pad >= 0 else int(siax.get("tile_pad") or 8)
    device = args.device or siax.get("device") or "auto"

    # allocate request id first so output path is unique before write
    req = new_request(
        input_path=str(dest_final),
        output_path=None,
        device=device,
        tile_size=tile,
        tile_pad=pad,
        note=f"grok_cli_grab {package_id}/{args.variant} t{tile}p{pad}",
        source_asset_hint=str(var.get("here_asset_id") or ""),
    )
    if args.output:
        out_png = Path(args.output)
        out_png.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_png = unique_out_png(
            handoff / "outbox",
            package_id=package_id,
            variant=args.variant,
            tile=tile,
            pad=pad,
            request_id=req["request_id"],
        )
    req["output_path"] = str(out_png)

    inbox = handoff / "inbox"
    outbox = handoff / "outbox"
    done = handoff / "done"
    write_request(inbox, req)
    try:
        result = process_one(
            inbox / f"{req['request_id']}.json",
            outbox=outbox,
            done_dir=done,
            job_store=root / "runs" / "spm_local",
        )
    except OSError as exc:
        err = {
            "siax_ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "hint": "output path locked or invalid; default uses unique names — avoid fixed warrior_SIAX4X.png; close viewers holding the PNG",
            "output_path": str(out_png),
            "request_id": req["request_id"],
        }
        print(json.dumps(err, indent=2, ensure_ascii=False), flush=True)
        return 3

    print(
        json.dumps(
            {
                "siax_ok": result.get("ok"),
                "request_id": result.get("request_id"),
                "output_path": result.get("output_path"),
                "output_sha256": result.get("output_sha256"),
                "device_used": result.get("device_used"),
                "tile_size": tile,
                "tile_pad": pad,
                "wall_s": result.get("wall_s"),
                "result_json": str(outbox / f"{result['request_id']}_result.json"),
                "paste_result_json_to_chat": True,
            },
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
