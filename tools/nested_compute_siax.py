#!/usr/bin/env python3
"""Nested Compute Tile executor for logical parent (P1).

Keeps logical_core/logical_halo as experiment identity, but runs model on
compute_core + compute_context children, writes native child PNGs, then strip-finalizes.

Isolation modes:
  - subprocess: one OS process per child (memory-safe on 1.9Gi hosts)
  - inprocess: single process with aggressive gc (faster; use only if RSS profiled)

NEW cell id — never claims silent equivalence to single-forward logical tile.
Supports --resume for long full-frame jobs.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


def rss_mb() -> float:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    except OSError:
        return 0.0
    return 0.0


def maxrss_mb() -> float:
    # Linux: ru_maxrss is KiB
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


CHILD_WORKER = r'''
import gc, json, os, sys, resource
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_THREADS", "1")
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
import torch
from spandrel import ImageModelDescriptor, ModelLoader
from ige.upscale.siax import MODEL_SHA256, file_sha256

spec = json.loads(sys.argv[1])
ckpt = spec["checkpoint"]
base_path = spec["base"]
ex0, ey0, ex1, ey1 = spec["input_box_base"]
cx, cy, cx1, cy1 = spec["core_box_base"]
out_uri = Path(spec["uri"])
scale = int(spec.get("scale", 4))

torch.set_num_threads(1)
assert file_sha256(ckpt) == MODEL_SHA256
with Image.open(base_path) as im:
    base = np.asarray(ImageOps.exif_transpose(im).convert("RGB"), dtype=np.uint8)
crop = base[ey0:ey1, ex0:ex1].astype(np.float32) / 255.0
tensor = torch.from_numpy(crop).permute(2, 0, 1).unsqueeze(0)
desc = ModelLoader(device=spec.get("device", "cpu")).load_from_file(ckpt)
assert isinstance(desc, ImageModelDescriptor) and int(desc.scale) == 4
desc.eval()
with torch.inference_mode():
    out = desc(tensor).float().cpu()
pred = out[0].permute(1, 2, 0).numpy()
pred_u8 = np.clip(pred * 255.0 + 0.5, 0, 255).astype(np.uint8)
left = (cx - ex0) * scale
top = (cy - ey0) * scale
right = left + (cx1 - cx) * scale
bottom = top + (cy1 - cy) * scale
core = pred_u8[top:bottom, left:right]
out_uri.parent.mkdir(parents=True, exist_ok=True)
Image.fromarray(core, "RGB").save(out_uri, format="PNG", compress_level=1)
sha = file_sha256(out_uri)
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
print(json.dumps({
    "ok": True,
    "sha256": sha,
    "core_shape": list(core.shape),
    "maxrss_mb": round(rss, 2),
    "input_wh": [ex1 - ex0, ey1 - ey0],
}))
'''


def plan_children(W: int, H: int, parents: list[dict], CC: int, CX: int, LH: int) -> list[dict]:
    planned = []
    for p in parents:
        x0, y0, x1, y1 = p["core_box"]
        for cy in range(y0, y1, CC):
            for cx in range(x0, x1, CC):
                cx1, cy1 = min(cx + CC, x1), min(cy + CC, y1)
                ex0 = max(0, cx - CX)
                ey0 = max(0, cy - CX)
                ex1 = min(W, cx1 + CX)
                ey1 = min(H, cy1 + CX)
                if cx == x0:
                    ex0 = max(0, x0 - LH)
                if cy == y0:
                    ey0 = max(0, y0 - LH)
                if cx1 == x1:
                    ex1 = min(W, x1 + LH)
                if cy1 == y1:
                    ey1 = min(H, y1 + LH)
                child_id = f"{p['parent_id']}_c{cy:04d}_{cx:04d}"
                planned.append(
                    {
                        "child_id": child_id,
                        "parent_id": p["parent_id"],
                        "core_box_base": [cx, cy, cx1, cy1],
                        "input_box_base": [ex0, ey0, ex1, ey1],
                        "output_box_hires": [cx * 4, cy * 4, cx1 * 4, cy1 * 4],
                        "role": "compute_native",
                    }
                )
    return planned


def run_child_subprocess(
    *,
    env: dict,
    checkpoint: Path,
    base: Path,
    planned: dict,
    uri: Path,
    device: str,
) -> dict:
    spec = {
        "checkpoint": str(checkpoint),
        "base": str(base),
        "input_box_base": planned["input_box_base"],
        "core_box_base": planned["core_box_base"],
        "uri": str(uri),
        "device": device,
        "scale": 4,
    }
    p = subprocess.run(
        [sys.executable, "-c", CHILD_WORKER, json.dumps(spec)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    if p.returncode != 0:
        return {
            "ok": False,
            "returncode": p.returncode,
            "stderr": (p.stderr or "")[-800:],
            "stdout": (p.stdout or "")[-400:],
        }
    lines = [ln for ln in (p.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return {"ok": False, "error": "empty worker stdout", "stderr": (p.stderr or "")[-400:]}
    meta = json.loads(lines[-1])
    meta["ok"] = True
    return meta


def main() -> int:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--job-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--logical-core", type=int, default=256)
    ap.add_argument("--logical-halo", type=int, default=32)
    ap.add_argument("--compute-core", type=int, default=64)
    ap.add_argument("--compute-context", type=int, default=32)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--max-parents", type=int, default=0, help="0=all parents; else limit for smoke")
    ap.add_argument("--min-fullframe-bytes", type=int, default=5_000_000)
    ap.add_argument(
        "--isolation",
        choices=["subprocess", "inprocess"],
        default="subprocess",
        help="subprocess = one process per child (memory-safe)",
    )
    ap.add_argument("--resume", action="store_true", help="reuse existing child PNGs in job-dir")
    ap.add_argument("--progress-every", type=int, default=10)
    args = ap.parse_args()

    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("TORCH_NUM_THREADS", "1")

    from ige.upscale.siax import MODEL_SHA256, file_sha256
    from ige.upscale.strip_finalize import finalize_from_child_tiles

    if file_sha256(args.checkpoint) != MODEL_SHA256:
        raise SystemExit("checkpoint hash mismatch")

    job = Path(args.job_dir)
    for sub in ("parents", "children", "manifests"):
        (job / sub).mkdir(parents=True, exist_ok=True)
    if not args.resume and any((job / "children").iterdir()):
        raise SystemExit(f"job-dir children not empty; pass --resume or use a fresh job-dir: {job}")

    with Image.open(args.base) as im:
        base_img = ImageOps.exif_transpose(im).convert("RGB")
    W, H = base_img.size
    base = np.asarray(base_img, dtype=np.uint8)
    base_sha = file_sha256(args.base)
    LC, LH = args.logical_core, args.logical_halo
    CC, CX = args.compute_core, args.compute_context
    scale = 4
    cell_id = f"nested_L{LC}/{LH}_C{CC}/ctx{CX}"

    grid_w = (W + LC - 1) // LC
    grid_h = (H + LC - 1) // LC
    parents = []
    for row in range(grid_h):
        for col in range(grid_w):
            x0, y0 = col * LC, row * LC
            x1, y1 = min(x0 + LC, W), min(y0 + LC, H)
            parents.append(
                {
                    "parent_id": f"P_r{row:03d}_c{col:03d}",
                    "core_box": [x0, y0, x1, y1],
                    "row": row,
                    "col": col,
                }
            )
    if args.max_parents:
        parents = parents[: args.max_parents]

    planned = plan_children(W, H, parents, CC, CX, LH)
    (job / "manifests" / "plan.json").write_text(
        json.dumps(
            {
                "cell_id": cell_id,
                "base_wh": [W, H],
                "parent_count": len(parents),
                "child_count_planned": len(planned),
                "isolation": args.isolation,
                "parents": parents,
            },
            indent=2,
        )
        + "\n"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env["OMP_NUM_THREADS"] = env["MKL_NUM_THREADS"] = env["TORCH_NUM_THREADS"] = "1"

    desc = None
    load_s = 0.0
    peak_after_load = 0.0
    if args.isolation == "inprocess":
        import torch
        from spandrel import ImageModelDescriptor, ModelLoader

        torch.set_num_threads(1)
        t0 = time.perf_counter()
        desc = ModelLoader(device=args.device).load_from_file(str(args.checkpoint))
        if not isinstance(desc, ImageModelDescriptor) or int(desc.scale) != 4:
            raise SystemExit("bad model")
        desc.eval()
        load_s = time.perf_counter() - t0
        peak_after_load = rss_mb()

    children_meta: list[dict] = []
    peak_forward = peak_after_load
    t_forward = 0.0
    n_done = 0
    n_resumed = 0
    n_failed = 0
    progress_path = job / "manifests" / "progress.jsonl"
    t_job0 = time.perf_counter()

    for i, pl in enumerate(planned):
        uri = job / "children" / f"{pl['child_id']}.png"
        meta = {
            **pl,
            "uri": str(uri.resolve()),
        }
        if args.resume and uri.is_file() and uri.stat().st_size > 100:
            from ige.upscale.siax import file_sha256 as fsha

            meta["sha256"] = fsha(uri)
            meta["resumed"] = True
            children_meta.append(meta)
            n_resumed += 1
            n_done += 1
            continue

        t1 = time.perf_counter()
        if args.isolation == "subprocess":
            result = run_child_subprocess(
                env=env,
                checkpoint=args.checkpoint,
                base=args.base,
                planned=pl,
                uri=uri,
                device=args.device,
            )
            if not result.get("ok"):
                n_failed += 1
                rec = {
                    "i": i,
                    "child_id": pl["child_id"],
                    "ok": False,
                    "error": result,
                    "elapsed_s": round(time.perf_counter() - t1, 3),
                }
                with progress_path.open("a") as fh:
                    fh.write(json.dumps(rec) + "\n")
                print(json.dumps(rec), flush=True)
                raise SystemExit(f"child failed: {pl['child_id']} -> {result}")
            meta["sha256"] = result["sha256"]
            meta["input_wh"] = result.get("input_wh")
            meta["worker_maxrss_mb"] = result.get("maxrss_mb")
            peak_forward = max(peak_forward, float(result.get("maxrss_mb") or 0))
        else:
            import torch

            cx, cy, cx1, cy1 = pl["core_box_base"]
            ex0, ey0, ex1, ey1 = pl["input_box_base"]
            crop = base[ey0:ey1, ex0:ex1]
            arr = crop.astype(np.float32) / 255.0
            tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
            assert desc is not None
            with torch.inference_mode():
                out = desc(tensor).float().cpu()
            pred = out[0].permute(1, 2, 0).numpy()
            pred_u8 = np.clip(pred * 255.0 + 0.5, 0, 255).astype(np.uint8)
            left = (cx - ex0) * scale
            top = (cy - ey0) * scale
            right = left + (cx1 - cx) * scale
            bottom = top + (cy1 - cy) * scale
            core = pred_u8[top:bottom, left:right]
            Image.fromarray(core, "RGB").save(uri, format="PNG", compress_level=1)
            meta["sha256"] = file_sha256(uri)
            meta["input_wh"] = [ex1 - ex0, ey1 - ey0]
            del tensor, out, pred, pred_u8, core, crop, arr
            gc.collect()
            peak_forward = max(peak_forward, rss_mb(), maxrss_mb())

        dt = time.perf_counter() - t1
        t_forward += dt
        children_meta.append(meta)
        n_done += 1
        rec = {
            "i": i,
            "child_id": pl["child_id"],
            "ok": True,
            "elapsed_s": round(dt, 3),
            "done": n_done,
            "planned": len(planned),
            "peak_rss_mb": round(peak_forward, 2),
            "eta_s": round((len(planned) - n_done) * (t_forward / max(1, n_done - n_resumed)), 1)
            if (n_done - n_resumed) > 0
            else None,
        }
        with progress_path.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        if n_done % args.progress_every == 0 or n_done == len(planned):
            print(json.dumps(rec), flush=True)

    full = args.max_parents == 0
    report = {
        "program": "SIAX_S2_1_P1_NESTED_COMPUTE",
        "cell_id": cell_id,
        "logical_core": LC,
        "logical_halo": LH,
        "compute_core": CC,
        "compute_context": CX,
        "base_wh": [W, H],
        "base_sha256": base_sha,
        "parent_count": len(parents),
        "child_count": len(children_meta),
        "child_count_planned": len(planned),
        "resumed_count": n_resumed,
        "isolation": args.isolation,
        "model_load_s": round(load_s, 3),
        "forward_sum_s": round(t_forward, 3),
        "wall_s": round(time.perf_counter() - t_job0, 3),
        "peak_rss_mb": round(peak_forward, 2),
        "model_rss_after_load_mb": round(peak_after_load, 2),
        "children": children_meta,
        "final_acceptance": False,
        "equivalence_to_single_forward_logical": "NOT_CLAIMED",
        "note": "New nested cell; RF-guided context; not labeled as original 256/32 success.",
        "rf_reference": "runs/siax_validation_r2/S2_1/p1/RF_MEASURE_c64.json recommended_compute_context=24; using ctx32 conservative",
    }

    # Virtual Master manifest (schema-aligned)
    vm = {
        "manifest_version": "0.1.0",
        "master_id": f"vm_{cell_id.replace('/', '_')}",
        "base_sha256": base_sha,
        "scale": 4,
        "output_dimensions": {"width": W * scale, "height": H * scale},
        "logical_grid": {
            "logical_core": LC,
            "logical_halo": LH,
            "compute_core": CC,
            "compute_context": CX,
        },
        "children": [
            {
                "child_id": c["child_id"],
                "parent_id": c["parent_id"],
                "uri": c["uri"],
                "sha256": c["sha256"],
                "role": c.get("role", "compute_native"),
                "core_box_base": c["core_box_base"],
                "output_box_hires": c["output_box_hires"],
                "acceptance": "candidate_only",
            }
            for c in children_meta
        ],
        "primary_policy": {
            "preview_never_primary": True,
            "min_fullframe_bytes": args.min_fullframe_bytes,
            "assert_dimensions": True,
        },
        "notes": [
            "Child native PNGs are first-class primary assets.",
            "Full lossless PNG is optional delivery via strip finalizer.",
            "final_acceptance remains false until S2 quality re-accept.",
            "NOT claimed equivalent to single-forward logical 256/32.",
        ],
    }
    (job / "manifests" / "virtual_master.json").write_text(
        json.dumps(vm, ensure_ascii=False, indent=2) + "\n"
    )
    report["virtual_master_path"] = str((job / "manifests" / "virtual_master.json").resolve())

    if full:
        fin = finalize_from_child_tiles(
            children=children_meta,
            output_path=args.out,
            output_width=W * scale,
            output_height=H * scale,
            base_width=W,
            base_height=H,
            min_fullframe_bytes=args.min_fullframe_bytes,
        )
        report["finalize"] = fin
        report["output_sha256"] = fin["output_sha256"]
    else:
        report["finalize"] = {"skipped": True, "reason": "max_parents smoke; incomplete coverage"}

    man = job / "manifests" / "nested_job.json"
    man.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    slim = {k: v for k, v in report.items() if k != "children"}
    slim["children_count"] = len(children_meta)
    (job / "manifests" / "nested_summary.json").write_text(json.dumps(slim, indent=2) + "\n")
    print(json.dumps(slim, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
