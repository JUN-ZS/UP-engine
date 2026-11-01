#!/usr/bin/env python3
"""N1 scaffold smoke: plan → synthetic tiles at native res → stitch. Not generative 4K product."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from ige.native4k.n1_canvas import build_plan
    from PIL import Image, ImageDraw

    # smaller smoke canvas for CI speed; still "native path" not 4x
    plan = build_plan(width=1024, height=576, tile=256, overlap=32)
    out_dir = root / "runs" / "n1_smoke"
    tiles_dir = out_dir / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    plan.write(out_dir / "plan.json")

    for t in plan.tiles:
        w, h = t["x1"] - t["x0"], t["y1"] - t["y0"]
        im = Image.new("RGB", (w, h), (40, 40, 50))
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, 0, w - 1, h - 1], outline=(0, 200, 255))
        dr.text((8, 8), t["tile_id"], fill=(255, 255, 0))
        im.save(tiles_dir / f"{t['tile_id']}.png")

    # stitch via same logic as tool
    import subprocess

    r = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "n1_stitch.py"),
            "--plan",
            str(out_dir / "plan.json"),
            "--tiles-dir",
            str(tiles_dir),
            "--out",
            str(out_dir / "OUT_NATIVE.png"),
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return r.returncode
    rep = json.loads((out_dir / "OUT_NATIVE.n1_stitch.json").read_text())
    evidence = {
        "format": "ige.native4k.n1_scaffold_smoke",
        "status": "N1_SCAFFOLD_OK" if rep.get("scaffold_roundtrip") else "N1_SCAFFOLD_PARTIAL",
        "smoke_canvas": [1024, 576],
        "production_default_canvas": [3840, 2160],
        "tile_count": plan.tile_count,
        "placed": rep.get("placed"),
        "output_sha256": rep.get("output_sha256"),
        "not_siax_4x_upscale": True,
        "native_4k_success": False,
        "note": "Synthetic colored tiles prove ledger+stitch only; no generative native fill.",
    }
    (root / "docs" / "evidence" / "N1_SCAFFOLD_SMOKE.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["status"] == "N1_SCAFFOLD_OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
