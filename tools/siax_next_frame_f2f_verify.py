#!/usr/bin/env python3
"""NEXT FRAME frame-to-frame verify (temporal), NOT spatial EXTEND.

Input: ordered video frames t0,t1,t2,...
  consecutive SIFT edges only (path graph)
  DDXX similarity / homography / local_mesh
  pair residual / identity MAE / step of motion magnitude
  filmstrip + pair residual heats + stitch optional

Flags always:
  mode=next_frame_f2f  (not spatial_extend)
  cinematic_product=false quality_qualified=false
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ige.registration import (  # noqa: E402
    build_sift_match_graph,
    register_multiview_v2,
    fit_weighted_similarity,
    fit_weighted_homography,
)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def font(sz=15):
    for n in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        try:
            return ImageFont.truetype(n, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def filmstrip(frames: list[tuple[str, Image.Image]], title: str, out: Path, tw=160):
    thumbs = []
    for name, im in frames:
        th = int(tw * im.size[1] / im.size[0])
        t = im.resize((tw, th), Image.Resampling.LANCZOS)
        d = ImageDraw.Draw(t)
        d.rectangle([0, 0, tw - 1, 20], fill=(0, 0, 0))
        d.text((3, 2), name, fill=(255, 220, 80), font=font(12))
        thumbs.append(t)
    gap = 6
    W = sum(t.size[0] for t in thumbs) + gap * (len(thumbs) + 1)
    H = max(t.size[1] for t in thumbs) + 40
    canvas = Image.new("RGB", (W, H), (12, 12, 16))
    d = ImageDraw.Draw(canvas)
    d.text((8, 6), title, fill=(230, 230, 235), font=font(15))
    x = gap
    for t in thumbs:
        canvas.paste(t, (x, 28))
        x += t.size[0] + gap
    canvas.save(out)


def residual_pair(a: Image.Image, b: Image.Image, out: Path, title: str) -> dict:
    aa = np.asarray(a.convert("RGB"), dtype=np.float32)
    bb = np.asarray(b.convert("RGB"), dtype=np.float32)
    if aa.shape != bb.shape:
        b2 = b.resize(a.size, Image.Resampling.LANCZOS)
        bb = np.asarray(b2, dtype=np.float32)
    diff = np.mean(np.abs(aa - bb), axis=2)
    mae = float(np.mean(diff))
    p50 = float(np.median(diff))
    p95 = float(np.percentile(diff, 95))
    heat = (np.clip(diff / max(p95, 1e-3), 0, 1) * 255).astype(np.uint8)
    rgb = np.stack([heat, (255 - heat) // 2, np.zeros_like(heat)], 2)
    im = Image.fromarray(rgb)
    # downscale for display if huge
    if im.size[0] > 960:
        im = im.resize((960, int(960 * im.size[1] / im.size[0])), Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.size[0], 22], fill=(0, 0, 0))
    d.text((4, 3), f"{title} MAE={mae:.1f} p95={p95:.1f}", fill=(255, 255, 255), font=font(13))
    im.save(out)
    return {"mae": mae, "p50": p50, "p95": p95, "heat": str(out)}


def optical_flow_magnitude(a: Image.Image, b: Image.Image) -> dict:
    import cv2
    g0 = cv2.cvtColor(np.asarray(a.convert("RGB")), cv2.COLOR_RGB2GRAY)
    g1 = cv2.cvtColor(np.asarray(b.convert("RGB")), cv2.COLOR_RGB2GRAY)
    if g0.shape != g1.shape:
        g1 = cv2.resize(g1, (g0.shape[1], g0.shape[0]))
    # Farneback dense flow
    flow = cv2.calcOpticalFlowFarneback(g0, g1, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return {
        "flow_mean_px": float(np.mean(mag)),
        "flow_p50_px": float(np.median(mag)),
        "flow_p95_px": float(np.percentile(mag, 95)),
        "flow_max_px": float(np.max(mag)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-dir", type=Path, required=True)
    ap.add_argument("--pattern", default="f_*.png")
    ap.add_argument("--max-frames", type=int, default=12)
    ap.add_argument("--stride", type=int, default=1, help="1=true consecutive next-frame")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "docs/evidence/siax_next_frame_f2f_v11")
    ap.add_argument("--acceptance-px", type=float, default=15.0)
    ap.add_argument("--dt-s", type=float, default=0.25, help="time between selected frames (for report)")
    args = ap.parse_args()

    out = args.out_dir
    fig = out / "figures"
    fr_out = out / "frames"
    fig.mkdir(parents=True, exist_ok=True)
    fr_out.mkdir(parents=True, exist_ok=True)

    paths = sorted(args.frames_dir.glob(args.pattern))
    if args.stride > 1:
        paths = paths[:: args.stride]
    paths = paths[: args.max_frames]
    if len(paths) < 2:
        raise SystemExit("need >=2 frames")

    frames = []
    meta = []
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB")
        # normalize size to first
        if i == 0:
            base_size = im.size
        elif im.size != base_size:
            im = im.resize(base_size, Image.Resampling.LANCZOS)
        name = f"T{i:02d}"
        dest = fr_out / f"{name}_{p.name}"
        im.save(dest)
        frames.append((name, im))
        meta.append({
            "id": name,
            "source": str(p),
            "t_index": i,
            "t_s": round(i * args.dt_s * args.stride, 4),
            "size": list(im.size),
            "sha256": sha256_file(dest),
        })

    filmstrip(frames, f"NEXT FRAME F2F chain · N={len(frames)} · Δt≈{args.dt_s * args.stride}s · NOT spatial EXTEND", fig / "FIG1_f2f_filmstrip.png")

    # consecutive pair metrics
    pair_rows = []
    for i in range(len(frames) - 1):
        na, ima = frames[i]
        nb, imb = frames[i + 1]
        heat_path = fig / f"FIG2_residual_{na}_{nb}.png"
        res = residual_pair(ima, imb, heat_path, f"{na}→{nb} NEXT")
        try:
            flow = optical_flow_magnitude(ima, imb)
        except Exception as exc:
            flow = {"error": str(exc)}
        pair_rows.append({
            "pair": f"{na}->{nb}",
            "t_from": meta[i]["t_s"],
            "t_to": meta[i + 1]["t_s"],
            **res,
            **flow,
        })

    # SIFT consecutive edges only
    imgs = {n: np.asarray(im) for n, im in frames}
    # build full graph then keep consecutive
    graph = build_sift_match_graph(
        imgs,
        max_features=3500,
        ratio_threshold=0.75,
        ransac_reprojection_px=4.0,
        min_inliers=15,
        max_anchors_per_edge=500,
    )
    all_matches = graph.get("matches") or []
    name_list = [n for n, _ in frames]
    consec_edges = []
    sift_diag = []
    for i in range(len(name_list) - 1):
        a, b = name_list[i], name_list[i + 1]
        found = None
        for e in all_matches:
            if {e["image_a"], e["image_b"]} == {a, b}:
                if e["image_a"] == a:
                    found = e
                else:
                    anchors = [{
                        "name": x.get("name", "s"),
                        "xy_a": x["xy_b"],
                        "xy_b": x["xy_a"],
                        "weight": x.get("weight", 1.0),
                        "confidence": x.get("confidence", 1.0),
                    } for x in e.get("anchors") or []]
                    found = {"edge_id": f"{a}__{b}", "image_a": a, "image_b": b, "anchors": anchors}
                break
        n_anc = len(found["anchors"]) if found else 0
        sift_diag.append({"pair": f"{a}->{b}", "n_anchors": n_anc, "status": "ok" if n_anc >= 3 else "insufficient"})
        if found and n_anc >= 3:
            consec_edges.append({
                "edge_id": f"{a}__{b}",
                "image_a": a,
                "image_b": b,
                "anchors": found["anchors"],
            })

    specs = [{"id": n, "width": frames[0][1].size[0], "height": frames[0][1].size[1]} for n, _ in frames]

    model_rows = []
    model_results = {}
    if len(consec_edges) >= 1 and all(len(e["anchors"]) >= 3 for e in consec_edges):
        # need connected path: if some missing, only use available connected component from T00
        for model in ("similarity", "homography", "local_mesh"):
            try:
                # filter edges with enough anchors for model
                min_n = 4 if model == "homography" else 3
                edges = [e for e in consec_edges if len(e["anchors"]) >= min_n]
                # only ids that appear
                ids = []
                for e in edges:
                    if e["image_a"] not in ids:
                        ids.append(e["image_a"])
                    if e["image_b"] not in ids:
                        ids.append(e["image_b"])
                specs_m = [s for s in specs if s["id"] in ids]
                res = register_multiview_v2(
                    specs_m,
                    edges,
                    root_image_id=ids[0],
                    huber_px=12.0,
                    acceptance_threshold_px=args.acceptance_px,
                    allow_unverified_bridge_edges=True,
                    geometry_model=model,
                    holdout_fraction=0.25,
                    holdout_seed=3,
                    local_mesh_grid=(2, 2),
                )
                train_p95 = (res.get("global_residual") or {}).get("p95_residual_px")
                hold_p95 = ((res.get("holdout") or {}).get("holdout_global") or {}).get("p95_residual_px")
                model_results[model] = res
                model_rows.append({
                    "model": model,
                    "train_p95": None if train_p95 is None else round(float(train_p95), 4),
                    "holdout_p95": None if hold_p95 is None else round(float(hold_p95), 4),
                    "gate": res.get("geometry_gate"),
                    "ok": res.get("geometry_gate") == "pass",
                    "n_edges": len(edges),
                    "algorithm_id": res.get("algorithm_id"),
                })
            except Exception as exc:
                model_rows.append({"model": model, "gate": "error", "ok": False, "note": str(exc)[:100]})
    else:
        model_rows.append({"model": "all", "gate": "insufficient_sift_edges", "ok": False, "note": "need consecutive SIFT anchors"})

    # pairwise similarity motion estimate for each consecutive pair
    motion_rows = []
    for e in consec_edges:
        src = np.asarray([a["xy_b"] for a in e["anchors"]], float)
        tgt = np.asarray([a["xy_a"] for a in e["anchors"]], float)
        try:
            fit = fit_weighted_similarity(src, tgt)
            motion_rows.append({
                "pair": e["edge_id"],
                "n_anchors": len(e["anchors"]),
                "scale": fit.transform.scale,
                "rotation_deg": math.degrees(fit.transform.rotation_rad),
                "tx": fit.transform.tx,
                "ty": fit.transform.ty,
                "p95_residual": fit.p95_residual_px,
                "median_residual": fit.median_residual_px,
            })
        except Exception as exc:
            motion_rows.append({"pair": e["edge_id"], "error": str(exc)})

    # verdict board
    H = 90 + 28 * (len(model_rows) + len(pair_rows) + 6)
    board = Image.new("RGB", (1000, min(H, 900)), (12, 14, 20))
    d = ImageDraw.Draw(board)
    d.text((14, 10), "NEXT FRAME · F2F (temporal) — NOT spatial EXTEND", fill=(240, 240, 245), font=font(17))
    y = 42
    d.text((14, y), "Pair pixel residual (identity MAE before warp)", fill=(140, 190, 255), font=font(13))
    y += 24
    for r in pair_rows:
        line = f"{r['pair']}: MAE={r['mae']:.1f} p95={r['p95']:.1f} flow_p50={r.get('flow_p50_px', '?')}"
        d.text((14, y), line[:110], fill=(220, 220, 200), font=font(12))
        y += 22
    y += 8
    d.text((14, y), "DDXX on consecutive SIFT edges", fill=(140, 190, 255), font=font(13))
    y += 24
    for r in model_rows:
        col = (120, 255, 160) if r.get("ok") else (255, 160, 100)
        d.text((14, y), f"{r.get('model')}: gate={r.get('gate')} train_p95={r.get('train_p95')} hold={r.get('holdout_p95')}", fill=col, font=font(12))
        y += 22
    y += 8
    d.text((14, y), "cinematic_product=false · quality_qualified=false · mode=next_frame_f2f", fill=(255, 110, 110), font=font(13))
    board.save(fig / "FIG3_verdict_f2f.png")

    # trend plot as simple image
    if pair_rows:
        W, Ht = 720, 280
        plot = Image.new("RGB", (W, Ht), (16, 18, 24))
        d = ImageDraw.Draw(plot)
        d.text((10, 8), "F2F chain: pair MAE / flow_p50 along time", fill=(230, 230, 230), font=font(14))
        maes = [r["mae"] for r in pair_rows]
        flows = [r.get("flow_p50_px") or 0 for r in pair_rows]
        mx = max(max(maes), max(flows), 1)
        pad_l, pad_b, pad_t, pad_r = 40, 40, 40, 20
        for i in range(len(maes) - 1):
            x0 = pad_l + int((W - pad_l - pad_r) * i / max(len(maes) - 1, 1))
            x1 = pad_l + int((W - pad_l - pad_r) * (i + 1) / max(len(maes) - 1, 1))
            y0 = Ht - pad_b - int((Ht - pad_t - pad_b) * maes[i] / mx)
            y1 = Ht - pad_b - int((Ht - pad_t - pad_b) * maes[i + 1] / mx)
            d.line([(x0, y0), (x1, y1)], fill=(255, 180, 80), width=2)
            f0 = Ht - pad_b - int((Ht - pad_t - pad_b) * flows[i] / mx)
            f1 = Ht - pad_b - int((Ht - pad_t - pad_b) * flows[i + 1] / mx)
            d.line([(x0, f0), (x1, f1)], fill=(80, 200, 255), width=2)
        d.text((pad_l, Ht - 28), "orange=MAE  cyan=flow_p50", fill=(180, 180, 180), font=font(12))
        plot.save(fig / "FIG4_f2f_trend.png")

    # contrast note vs EXTEND
    contrast = Image.new("RGB", (900, 200), (14, 16, 22))
    d = ImageDraw.Draw(contrast)
    lines = [
        "EXTEND (spatial peep / L-C-R pan re-gen)  ≠  NEXT FRAME (temporal t→t+1)",
        "This run: video frames from same shot, consecutive time indices",
        f"Frames={len(frames)}  consecutive SIFT edges={len(consec_edges)}  Δt≈{args.dt_s * args.stride}s",
        "PASS on DDXX only means geometric anchors align under similarity/homography,",
        "NOT that motion is cinematic-correct or identity is locked.",
    ]
    y = 16
    for line in lines:
        d.text((16, y), line, fill=(220, 220, 230) if y > 16 else (255, 200, 100), font=font(14))
        y += 28
    contrast.save(fig / "FIG0_extend_vs_f2f.png")

    art = Path("/workspace/artifacts/tmp/cinema_f2f_v11")
    art.mkdir(parents=True, exist_ok=True)
    for p in sorted(fig.glob("FIG*.png")):
        (art / p.name).write_bytes(p.read_bytes())

    report = {
        "format": "ige.siax.next_frame_f2f",
        "format_version": "1.1",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "next_frame_f2f",
        "not_spatial_extend": True,
        "source_video": "dfe82060-d1d7-4c7f-973f-d221d731509e",
        "dt_s_between_selected": args.dt_s * args.stride,
        "frames": meta,
        "pair_pixel_residual": pair_rows,
        "sift_consecutive": sift_diag,
        "motion_similarity_per_pair": motion_rows,
        "ddxx_models": model_rows,
        "formulas": {
            "similarity": "x' = s R(θ) x + t",
            "homography": "x~' ~ H [x y 1]^T",
            "sift": "mutual SIFT + ratio + RANSAC on consecutive frames only",
            "flow": "Farneback dense optical flow magnitude",
            "f2f_mae": "mean |I_t - I_{t+1}| (identity residual; motion raises this)",
        },
        "acceptance": {
            "next_frame_f2f_demo": True,
            "spatial_extend": False,
            "cinematic_product": False,
            "quality_qualified": False,
            "native_4k_success": False,
            "final_acceptance": False,
            "note": "Temporal F2F geometry/motion metrics only; not film-grade continuity pass.",
        },
        "paths": {"out_dir": str(out), "artifacts": str(art)},
    }
    rp = out / "REPORT_NEXT_FRAME_F2F_V11.json"
    rp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (art / rp.name).write_text(rp.read_text(encoding="utf-8"), encoding="utf-8")
    for m, res in model_results.items():
        slim = {
            "geometry_model": res.get("geometry_model"),
            "geometry_gate": res.get("geometry_gate"),
            "global_residual": res.get("global_residual"),
            "holdout": res.get("holdout"),
            "graph": res.get("graph"),
        }
        (out / f"RESULT_f2f_{m}.json").write_text(json.dumps(slim, indent=2), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "mode": "next_frame_f2f",
        "not_spatial_extend": True,
        "n_frames": len(frames),
        "n_consec_sift_edges": len(consec_edges),
        "pair_residual": [{"pair": r["pair"], "mae": r["mae"], "p95": r["p95"], "flow_p50": r.get("flow_p50_px")} for r in pair_rows],
        "sift": sift_diag,
        "motion": motion_rows,
        "ddxx": model_rows,
        "report": str(rp),
        "figures": [p.name for p in sorted(fig.glob("FIG*.png"))],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
