#!/usr/bin/env python3
"""Emit a HERE→local handoff request JSON (for chat to give user, or write inbox)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from ige.spm_local.handoff import new_request, write_request

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="path ON THE LOCAL PC")
    ap.add_argument("--output", default="")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--tile-size", type=int, default=128)
    ap.add_argument("--tile-pad", type=int, default=8)
    ap.add_argument("--note", default="")
    ap.add_argument("--source-asset-hint", default="")
    ap.add_argument(
        "--inbox",
        type=Path,
        default=None,
        help="if set, write into inbox; else print JSON only",
    )
    args = ap.parse_args()
    req = new_request(
        input_path=args.input,
        output_path=args.output or None,
        device=args.device,
        tile_size=args.tile_size,
        tile_pad=args.tile_pad,
        note=args.note,
        source_asset_hint=args.source_asset_hint,
    )
    if args.inbox:
        path = write_request(args.inbox, req)
        print(json.dumps({"wrote": str(path), "request": req}, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(req, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
