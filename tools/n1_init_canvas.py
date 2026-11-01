#!/usr/bin/env python3
"""N1: allocate target-res canvas PNG. Optional structure from BASE (fit) — NOT Siax 4x claim."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from ige.native4k.n1_canvas import CanvasPlan
    from PIL import Image

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("runs/n1/canvas.png"))
    ap.add_argument("--base", type=Path, default=None, help="optional structure image (Lanczos fit)")
    ap.add_argument("--fit", choices=("contain", "cover"), default="contain")
    ap.add_argument("--fill", default="#101010")
    args = ap.parse_args()

    plan = CanvasPlan.load(args.plan)
    w, h = plan.width, plan.height
    # parse fill
    fill = args.fill.lstrip("#")
    if len(fill) == 6:
        rgb = tuple(int(fill[i : i + 2], 16) for i in (0, 2, 4))
    else:
        rgb = (16, 16, 16)

    canvas = Image.new("RGB", (w, h), rgb)
    mode = "empty"
    if args.base and args.base.is_file():
        mode = f"structure_fit_{args.fit}"
        base = Image.open(args.base).convert("RGB")
        bw, bh = base.size
        if args.fit == "contain":
            scale = min(w / bw, h / bh)
        else:
            scale = max(w / bw, h / bh)
        nw, nh = max(1, int(bw * scale)), max(1, int(bh * scale))
        resized = base.resize((nw, nh), Image.Resampling.LANCZOS)
        x0 = (w - nw) // 2
        y0 = (h - nh) // 2
        canvas.paste(resized, (x0, y0))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out, format="PNG", compress_level=3)
    meta = {
        "format": "ige.native4k.n1_canvas",
        "path": "native_canvas_tiling",
        "not_siax_4x_upscale": True,
        "width": w,
        "height": h,
        "mode": mode,
        "base": str(args.base) if args.base else None,
        "output": str(args.out.resolve()),
        "output_sha256": sha256(args.out),
        "plan_tile_count": plan.tile_count,
        "native_4k_success": False,
        "final_acceptance": False,
        "note": "Structure fit uses Lanczos only; this is NOT Siax 4x and NOT native generative fill.",
    }
    sidecar = args.out.with_suffix(".n1.json")
    sidecar.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
