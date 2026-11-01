#!/usr/bin/env python3
"""Register a new HERE→local package so CLI is not stuck on warrior_mud_hammer.

After you (or HERE) have a BASE image file:

  python tools/spm_here_pack.py create \\
    --package my_scene_v1 \\
    --image path/to/BASE.jpg \\
    --variant base

Then:

  python tools/spm_here_grab.py --package my_scene_v1 --variant base --run-siax --cell 256/16
  # or:  .\\tools\\spm_cli.ps1 run -Package my_scene_v1 -Cell 256/16

Does not train models. Does not claim quality PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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


def slug(s: str) -> str:
    s = s.strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_\-]+", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s or not re.match(r"^[a-z]", s):
        raise SystemExit("package id must start with a letter and be [a-z0-9_-]+")
    return s[:64]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    packages = root / "packages" / "spm_here"
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="create package from a local image file")
    c.add_argument("--package", required=True, help="id e.g. street_rain_v1")
    c.add_argument("--image", type=Path, required=True, help="BASE image on disk")
    c.add_argument("--variant", default="base", choices=("base", "master"))
    c.add_argument("--here-asset-id", default="", help="optional Imagine asset UUID")
    c.add_argument("--share-url", default="")
    c.add_argument("--note", default="")
    c.add_argument("--cell-default", default="256/16")

    l = sub.add_parser("list", help="list packages")
    args = ap.parse_args()

    if args.cmd == "list":
        rows = []
        if packages.is_dir():
            for d in sorted(packages.iterdir()):
                man = d / "manifest.json"
                if man.is_file():
                    m = json.loads(man.read_text(encoding="utf-8"))
                    rows.append(
                        {
                            "package_id": m.get("package_id"),
                            "variants": list((m.get("variants") or {}).keys()),
                            "cli_run": f"python tools/spm_here_grab.py --package {m.get('package_id')} --variant base --run-siax --cell 256/16",
                        }
                    )
        print(json.dumps({"packages": rows}, indent=2, ensure_ascii=False))
        return 0

    pkg_id = slug(args.package)
    img = Path(args.image)
    if not img.is_file():
        raise SystemExit(f"image not found: {img}")

    ext = img.suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise SystemExit("image must be jpg/png/webp")

    pkg_dir = packages / pkg_id
    pkg_dir.mkdir(parents=True, exist_ok=True)
    dest_name = f"{pkg_id}_{args.variant}{ext if ext != '.jpeg' else '.jpg'}"
    if ext == ".jpeg":
        dest_name = f"{pkg_id}_{args.variant}.jpg"
    # store canonical name inside package
    file_name = f"{'warrior_BASE' if False else args.variant.upper() if False else ''}"
    # simpler: base.jpg / master.jpg inside package
    file_name = f"{args.variant}{ext if ext != '.jpeg' else '.jpg'}"
    if ext == ".jpeg":
        file_name = f"{args.variant}.jpg"

    dest = pkg_dir / file_name
    shutil.copy2(img, dest)
    sha = file_sha256(dest)

    man_path = pkg_dir / "manifest.json"
    if man_path.is_file():
        man = json.loads(man_path.read_text(encoding="utf-8"))
    else:
        man = {
            "format": "ige.spm.here_grab_package",
            "format_version": "1.1",
            "package_id": pkg_id,
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "variants": {},
            "local_defaults": {
                "dest_dir": r"D:\s3_share\spm_in",
                "dest_name_rule": "{package_id}_{variant}{ext}",
                "handoff_root": r"D:\s3_share\spm_handoff",
                "output_png_rule": "{package_id}_{variant}_t{tile}p{pad}_{request_id}.png",
                "legacy_fixed_output_disabled": True,
            },
            "siax": {
                "tile_size": 256,
                "tile_pad": 16,
                "device": "auto",
                "scale": 4,
                "cell_default": args.cell_default,
            },
            "final_acceptance": False,
            "e3_speed_claim": False,
        }

    man["package_id"] = pkg_id
    man.setdefault("variants", {})
    man["variants"][args.variant] = {
        "file": file_name,
        "sha256": sha,
        "here_asset_id": args.here_asset_id or "",
        "share_url": args.share_url or "",
        "role": "SPM_INPUT_DEFAULT" if args.variant == "base" else "SPM_INPUT_OPTIONAL",
        "note": args.note or "",
    }
    man["grok_cli"] = {
        "list": "python tools/spm_here_grab.py --list",
        "grab": f"python tools/spm_here_grab.py --package {pkg_id} --variant {args.variant}",
        "run_commercial": f"python tools/spm_here_grab.py --package {pkg_id} --variant {args.variant} --run-siax --cell {args.cell_default}",
        "ps1": f".\\tools\\spm_cli.ps1 run -Package {pkg_id} -Variant {args.variant} -Cell {args.cell_default}",
    }
    man["updated_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    man_path.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    out = {
        "ok": True,
        "package_id": pkg_id,
        "variant": args.variant,
        "package_dir": str(pkg_dir),
        "file": file_name,
        "sha256": sha,
        "next": [
            f"python tools/spm_here_grab.py --package {pkg_id} --variant {args.variant}",
            f"python tools/spm_here_grab.py --package {pkg_id} --variant {args.variant} --run-siax --cell {args.cell_default}",
            f".\\tools\\spm_cli.ps1 run -Package {pkg_id} -Variant {args.variant} -Cell {args.cell_default}",
        ],
        "git_hint": "git add packages/spm_here/{id} && commit/push so other machines can grab".format(id=pkg_id),
        "final_acceptance": False,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
