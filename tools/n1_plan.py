#!/usr/bin/env python3
"""N1: write native canvas tile plan (default 3840x2160). Not Siax 4x."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from ige.native4k.n1_canvas import build_plan

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--width", type=int, default=3840)
    ap.add_argument("--height", type=int, default=2160)
    ap.add_argument("--tile", type=int, default=512)
    ap.add_argument("--overlap", type=int, default=64)
    ap.add_argument("--out", type=Path, default=Path("runs/n1/plan.json"))
    args = ap.parse_args()
    plan = build_plan(args.width, args.height, args.tile, args.overlap)
    plan.write(args.out)
    print(
        {
            "ok": True,
            "out": str(args.out),
            "width": plan.width,
            "height": plan.height,
            "tile_count": plan.tile_count,
            "step": plan.step,
            "path": plan.path,
            "not_siax_4x_upscale": True,
            "native_4k_success": False,
        }
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
