#!/usr/bin/env python3
"""Build real multi-view holdout anchors from an N1 stitch run (operator geometry + optional SIFT).

Example:
  python tools/siax_build_n1_real_holdout_pack.py \\
    --stitch runs/n1/gen_v3_chain4/OUT_CHAIN_chain4.n1_stitch.json \\
    --out docs/evidence/siax_real_multiview_holdout_v03
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stitch", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tile-ids", nargs="*", default=None)
    ap.add_argument("--geom-step", type=int, default=28)
    ap.add_argument("--with-sift", action="store_true")
    args = ap.parse_args()

    stitch = json.loads(args.stitch.read_text())
    receipts = {r["tile_id"]: r for r in stitch["tile_receipts"]}
    tile_ids = args.tile_ids or [r["tile_id"] for r in stitch["tile_receipts"] if (receipts[r["tile_id"]]["box"][2] - receipts[r["tile_id"]]["box"][0]) >= 512][:4]
    if len(tile_ids) < 2:
        raise SystemExit("need at least 2 tiles")

    args.out.mkdir(parents=True, exist_ok=True)
    specs = []
    images = {}
    for tid in tile_ids:
        path = ROOT / receipts[tid]["path"]
        if not path.exists():
            path = args.stitch.parent / "tiles" / f"{tid}.png"
        im = cv2.imread(str(path))
        if im is None:
            raise SystemExit(f"missing tile {tid}: {path}")
        h, w = im.shape[:2]
        specs.append({
            "id": tid,
            "width": w,
            "height": h,
            "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "sha256": sha256_file(path),
            "canvas_box": receipts[tid]["box"],
            "canvas_core": receipts[tid]["core"],
        })
        images[tid] = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)

    def box_of(tid):
        return receipts[tid]["box"]

    def local_of(tid, cx, cy):
        x0, y0, _, _ = box_of(tid)
        return [float(cx - x0), float(cy - y0)]

    def in_box(tid, cx, cy):
        x0, y0, x1, y1 = box_of(tid)
        return x0 <= cx < x1 and y0 <= cy < y1

    def geom_edge(a, b):
        ax0, ay0, ax1, ay1 = box_of(a)
        bx0, by0, bx1, by1 = box_of(b)
        ox0, oy0 = max(ax0, bx0), max(ay0, by0)
        ox1, oy1 = min(ax1, bx1), min(ay1, by1)
        if ox1 - ox0 < 16 or oy1 - oy0 < 16:
            return None
        pad, step = 10, args.geom_step
        pts = set()
        for y in range(oy0 + pad, max(oy0 + pad + 1, oy1 - pad), step):
            for x in range(ox0 + pad, max(ox0 + pad + 1, ox1 - pad), step):
                pts.add((x, y))
        for c in [
            (ox0 + pad, oy0 + pad), (ox1 - pad - 1, oy0 + pad),
            (ox0 + pad, oy1 - pad - 1), (ox1 - pad - 1, oy1 - pad - 1),
            (int((ox0 + ox1) / 2), int((oy0 + oy1) / 2)),
        ]:
            pts.add(c)
        anchors = []
        dim = {s["id"]: (s["width"], s["height"]) for s in specs}
        for i, (cx, cy) in enumerate(sorted(pts)):
            if not (in_box(a, cx, cy) and in_box(b, cx, cy)):
                continue
            la, lb = local_of(a, cx, cy), local_of(b, cx, cy)
            wa, ha = dim[a]; wb, hb = dim[b]
            if not (0 <= la[0] < wa and 0 <= la[1] < ha and 0 <= lb[0] < wb and 0 <= lb[1] < hb):
                continue
            anchors.append({
                "name": f"geom_{i}",
                "xy_a": la,
                "xy_b": lb,
                "weight": 1.0,
                "confidence": 1.0,
                "source": "operator_n1_canvas_geometry",
                "canvas_xy": [float(cx), float(cy)],
            })
        if len(anchors) < 4:
            return None
        return {"edge_id": f"geom_{a}_to_{b}", "image_a": a, "image_b": b,
                "anchor_source": "operator_n1_canvas_geometry", "anchors": anchors}

    geom_edges = []
    for a, b in zip(tile_ids, tile_ids[1:]):
        e = geom_edge(a, b)
        if e:
            geom_edges.append(e)

    def write_pack(name, matches, provider):
        anchors_doc = {
            "schema_version": "siaux-multiview-anchors/1.0-manual",
            "pack_id": name,
            "correspondence_provider": provider,
            "source_stitch": str(args.stitch),
            "asof": datetime.now(timezone.utc).isoformat(),
            "quality_qualified": False,
            "final_acceptance": False,
            "matches": matches,
        }
        specs_doc = {
            "schema_version": "siaux-multiview-image-specs/0.1",
            "pack_id": name,
            "image_specs": specs,
            "canvas_plan": {"width": stitch.get("width"), "height": stitch.get("height"), "run_id": stitch.get("run_id")},
        }
        ap = args.out / f"{name}_anchors.json"
        sp = args.out / f"{name}_specs.json"
        ap.write_text(json.dumps(anchors_doc, indent=2) + "\n")
        sp.write_text(json.dumps(specs_doc, indent=2) + "\n")
        return ap, sp

    gap, gsp = write_pack("OPERATOR_GEOM", geom_edges, "operator_n1_canvas_geometry")
    print({"operator_geom_edges": len(geom_edges), "anchors": gap.as_posix(), "specs": gsp.as_posix()})

    if args.with_sift:
        from ige.registration import build_sift_match_graph
        payload = build_sift_match_graph(images, max_features=4000, ratio_threshold=0.72,
                                         ransac_reprojection_px=3.0, min_inliers=8, matcher_backend="brute_force")
        adj = set(zip(tile_ids, tile_ids[1:])) | set(zip(tile_ids[1:], tile_ids))
        sift_edges = []
        for edge in payload.get("matches", []):
            a, b = edge["image_a"], edge["image_b"]
            if (a, b) not in adj and (b, a) not in adj:
                continue
            fixed = []
            for i, anc in enumerate(edge.get("anchors") or []):
                xa, xb = anc.get("xy_a"), anc.get("xy_b")
                if xa is None or xb is None:
                    continue
                fixed.append({
                    "name": f"sift_{i}",
                    "xy_a": [float(xa[0]), float(xa[1])],
                    "xy_b": [float(xb[0]), float(xb[1])],
                    "weight": float(anc.get("weight", 1.0)),
                    "confidence": float(anc.get("confidence", 0.85)),
                    "source": "sift_ransac_candidate",
                })
            if len(fixed) >= 4:
                sift_edges.append({
                    "edge_id": f"sift_{a}_to_{b}", "image_a": a, "image_b": b,
                    "anchor_source": "sift_ransac_candidate", "anchors": fixed[:40],
                })
        sap, ssp = write_pack("SIFT_CANDIDATE", sift_edges, "sift_ransac_candidate")
        print({"sift_edges": len(sift_edges), "anchors": sap.as_posix(), "specs": ssp.as_posix()})


if __name__ == "__main__":
    main()
