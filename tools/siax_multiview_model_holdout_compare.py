#!/usr/bin/env python3
"""Counterfactual compare similarity / homography / local_mesh on synthetic scenes + holdout.

Usage:
  python tools/siax_multiview_model_holdout_compare.py --out runs/geometry_holdout/report.json

Does NOT claim real SIAX acceptance. Synthetic only unless --anchors-json is provided.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ige.registration import (  # noqa: E402
    HomographyTransform,
    SimilarityTransform,
    register_multiview,
)


def _edge(image_a, image_b, world, pose_a, pose_b, edge_id):
    xa = pose_a.inverse().apply(world)
    xb = pose_b.inverse().apply(world)
    return {
        "edge_id": edge_id,
        "image_a": image_a,
        "image_b": image_b,
        "anchors": [
            {"name": f"{edge_id}_{i}", "xy_a": a.tolist(), "xy_b": b.tolist(), "weight": 1.0}
            for i, (a, b) in enumerate(zip(xa, xb))
        ],
    }


def scene_similarity():
    world = np.asarray(
        [[40, 40], [220, 40], [40, 220], [220, 220], [130, 130], [180, 90], [90, 170],
         [100, 60], [200, 160], [70, 120], [160, 200], [110, 100], [150, 140]],
        dtype=float,
    )
    poses = {
        "A": SimilarityTransform(1.0, 0.0, 0.0, 0.0),
        "B": SimilarityTransform(0.95, math.radians(6.0), 12.0, -8.0),
        "C": SimilarityTransform(1.06, math.radians(-7.0), -10.0, 14.0),
    }
    specs = [{"id": k, "width": 360, "height": 360} for k in poses]
    edges = [
        _edge("A", "B", world, poses["A"], poses["B"], "ab"),
        _edge("B", "C", world, poses["B"], poses["C"], "bc"),
        _edge("C", "A", world, poses["C"], poses["A"], "ca"),
    ]
    return "synthetic_similarity_triangle", specs, edges


def scene_homography():
    rng = np.random.default_rng(11)
    world = rng.uniform([30, 30], [340, 280], size=(36, 2))
    poses = {
        "A": HomographyTransform.identity(),
        "B": HomographyTransform(np.array([[1.0, 0.06, 18], [-0.02, 1.0, -9], [0.00025, 0.0, 1.0]])),
        "C": HomographyTransform(np.array([[0.98, -0.04, -14], [0.03, 1.02, 11], [0.0, 0.0002, 1.0]])),
    }
    specs = [{"id": k, "width": 400, "height": 340} for k in poses]
    edges = [
        _edge("A", "B", world, poses["A"], poses["B"], "ab"),
        _edge("B", "C", world, poses["B"], poses["C"], "bc"),
        _edge("C", "A", world, poses["C"], poses["A"], "ca"),
    ]
    return "synthetic_homography_triangle", specs, edges


def scene_multiplane_proxy():
    """Two depth planes: foreground and background with different similarities (proxy for parallax)."""
    rng = np.random.default_rng(21)
    bg = rng.uniform([20, 20], [300, 250], size=(20, 2))
    fg = rng.uniform([80, 80], [220, 200], size=(16, 2))
    # A identity; B: bg small shift, fg larger shift (simulate parallax)
    # We generate anchors in A and B image coords directly.
    anchors = []
    for i, p in enumerate(bg):
        anchors.append({
            "name": f"bg_{i}",
            "xy_a": p.tolist(),
            "xy_b": (p + np.array([8.0, -3.0])).tolist(),
            "weight": 1.0,
        })
    for i, p in enumerate(fg):
        anchors.append({
            "name": f"fg_{i}",
            "xy_a": p.tolist(),
            "xy_b": (p + np.array([22.0, -9.0])).tolist(),
            "weight": 1.0,
        })
    specs = [{"id": "A", "width": 360, "height": 300}, {"id": "B", "width": 360, "height": 300}]
    edges = [{"edge_id": "ab", "image_a": "A", "image_b": "B", "anchors": anchors}]
    return "synthetic_multiplane_parallax_proxy", specs, edges


def run_models(specs, edges, holdout_fraction, seed):
    rows = []
    for model in ("similarity", "homography", "local_mesh"):
        try:
            result = register_multiview(
                specs, edges, root_image_id=specs[0]["id"],
                geometry_model=model, huber_px=4.0,
                acceptance_threshold_px=None,
                holdout_fraction=holdout_fraction, holdout_seed=seed,
                local_mesh_grid=(2, 2),
                allow_unverified_bridge_edges=True,
            )
            train = result.get("global_residual") or {}
            hold = (result.get("holdout") or {}).get("holdout_global") or {}
            rows.append({
                "geometry_model": model,
                "algorithm_id": result.get("algorithm_id"),
                "geometry_gate": result.get("geometry_gate"),
                "train_p95_px": train.get("p95_residual_px"),
                "train_rmse_px": train.get("weighted_rmse_px"),
                "holdout_p95_px": hold.get("p95_residual_px"),
                "holdout_rmse_px": hold.get("weighted_rmse_px"),
                "holdout_anchor_count": hold.get("holdout_anchor_count"),
                "ok": True,
                "error": None,
            })
        except Exception as exc:  # noqa: BLE001 — report per model
            rows.append({
                "geometry_model": model,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
    return rows


def main():
    ap = argparse.ArgumentParser(description="SIAX multiview geometry model holdout compare")
    ap.add_argument("--out", type=Path, default=Path("runs/geometry_holdout/REPORT.json"))
    ap.add_argument("--holdout-fraction", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--anchors-json", type=Path, default=None,
                    help="Optional real anchors JSON (siaux-multiview-anchors/1.0). Specs via --specs-json.")
    ap.add_argument("--specs-json", type=Path, default=None)
    args = ap.parse_args()

    scenes = []
    if args.anchors_json:
        payload = json.loads(args.anchors_json.read_text())
        specs = json.loads(args.specs_json.read_text()) if args.specs_json else payload.get("image_specs")
        if not specs:
            raise SystemExit("real anchors require --specs-json or image_specs in the JSON")
        scenes.append(("user_provided", specs, payload["matches"]))
    else:
        scenes.extend([scene_similarity(), scene_homography(), scene_multiplane_proxy()])

    report = {
        "format": "ige.siax.multiview_model_holdout_compare",
        "format_version": "0.2",
        "asof": datetime.now(timezone.utc).isoformat(),
        "holdout_fraction": args.holdout_fraction,
        "seed": args.seed,
        "quality_qualified": False,
        "final_acceptance": False,
        "e3_speed_claim": False,
        "note": "Synthetic counterfactual unless user anchors provided. Not SIAX quality PASS.",
        "scenes": [],
    }
    for name, specs, edges in scenes:
        rows = run_models(specs, edges, args.holdout_fraction, args.seed)
        # pick best by holdout p95 among ok rows
        ok = [r for r in rows if r.get("ok") and r.get("holdout_p95_px") is not None]
        best = min(ok, key=lambda r: r["holdout_p95_px"]) if ok else None
        report["scenes"].append({
            "scene_id": name,
            "image_count": len(specs),
            "edge_count": len(edges),
            "models": rows,
            "best_by_holdout_p95": best["geometry_model"] if best else None,
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"ok": True, "out": str(args.out), "scenes": len(report["scenes"])}, indent=2))
    for sc in report["scenes"]:
        print(f"\n=== {sc['scene_id']} best={sc['best_by_holdout_p95']} ===")
        for r in sc["models"]:
            if not r.get("ok"):
                print(f"  {r['geometry_model']}: FAIL {r.get('error')}")
            else:
                print(
                    f"  {r['geometry_model']}: train_p95={r['train_p95_px']:.4f} "
                    f"holdout_p95={r['holdout_p95_px']:.4f} gate={r['geometry_gate']}"
                )


if __name__ == "__main__":
    main()
