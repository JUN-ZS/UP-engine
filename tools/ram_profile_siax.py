#!/usr/bin/env python3
"""Staged peak-RSS profile for pinned Siax 4x (P0 / S2.1.2).

Evidence grade:
  - Measured stages are OBSERVED
  - OOM stage labeled only when a subprocess dies with exit 137 / signal during that stage
  - final_acceptance always false
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


def rss_mb() -> float:
    """Current VmRSS in MiB (Linux)."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    except OSError:
        pass
    # fallback: ru_maxrss is peak of self in KB on Linux
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def maxrss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def snapshot(stage: str, extra: dict | None = None) -> dict:
    rec = {
        "stage": stage,
        "rss_mb": round(rss_mb(), 2),
        "maxrss_mb": round(maxrss_mb(), 2),
        "t_s": round(time.perf_counter(), 6),
    }
    if extra:
        rec.update(extra)
    return rec


def profile_inprocess(
    checkpoint: Path,
    sizes: list[tuple[int, int]],
    device: str = "cpu",
) -> dict:
    stages: list[dict] = []
    stages.append(snapshot("process_start"))

    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("TORCH_NUM_THREADS", "1")

    import numpy as np
    import torch
    from spandrel import ImageModelDescriptor, ModelLoader
    from ige.upscale.siax import MODEL_SHA256, file_sha256, allocate_output_canvas

    torch.set_num_threads(1)
    stages.append(snapshot("after_imports"))

    actual = file_sha256(checkpoint)
    if actual != MODEL_SHA256:
        raise SystemExit(f"checkpoint hash mismatch: {actual}")

    t0 = time.perf_counter()
    descriptor = ModelLoader(device=device).load_from_file(str(checkpoint))
    if not isinstance(descriptor, ImageModelDescriptor):
        raise SystemExit("not ImageModelDescriptor")
    if "esrgan" not in str(getattr(descriptor.architecture, "name", descriptor.architecture)).lower():
        raise SystemExit("not esrgan")
    if int(descriptor.scale) != 4:
        raise SystemExit("not 4x")
    descriptor.eval()
    stages.append(
        snapshot(
            "after_model_load",
            {"wall_s": round(time.perf_counter() - t0, 3), "device": device},
        )
    )
    model_baseline = stages[-1]["rss_mb"]

    forward_rows = []
    for h, w in sizes:
        gc.collect()
        before = snapshot(f"before_forward_{w}x{h}")
        stages.append(before)
        try:
            t1 = time.perf_counter()
            # synthetic RGB noise — measures activation peak, not quality
            arr = np.random.default_rng(0).random((h, w, 3), dtype=np.float32)
            tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
            with torch.inference_mode():
                out = descriptor(tensor)
                out_cpu = out.float().cpu()
            wall = time.perf_counter() - t1
            after = snapshot(
                f"after_forward_{w}x{h}",
                {
                    "wall_s": round(wall, 3),
                    "input_wh": [w, h],
                    "output_shape": list(out_cpu.shape),
                    "delta_rss_mb": round(rss_mb() - before["rss_mb"], 2),
                    "delta_from_model_mb": round(rss_mb() - model_baseline, 2),
                    "ok": True,
                },
            )
            stages.append(after)
            forward_rows.append(after)
            del tensor, out, out_cpu, arr
            gc.collect()
            stages.append(snapshot(f"after_free_{w}x{h}"))
        except Exception as exc:  # noqa: BLE001 — profile must record failure
            stages.append(
                snapshot(
                    f"forward_error_{w}x{h}",
                    {"ok": False, "error": repr(exc), "input_wh": [w, h]},
                )
            )
            forward_rows.append(stages[-1])

    # canvas allocation only (7168x4032 uint8)
    gc.collect()
    stages.append(snapshot("before_canvas_7168x4032"))
    canvas = allocate_output_canvas(1792, 1008, scale=4)
    stages.append(
        snapshot(
            "after_canvas_7168x4032",
            {
                "canvas_bytes": int(canvas.nbytes),
                "canvas_mib": round(canvas.nbytes / (1024 * 1024), 2),
                "delta_rss_mb": round(rss_mb() - stages[-2]["rss_mb"], 2),
            },
        )
    )
    del canvas
    gc.collect()
    stages.append(snapshot("after_canvas_free"))

    return {
        "mode": "inprocess",
        "model_baseline_rss_mb": model_baseline,
        "stages": stages,
        "forward_rows": forward_rows,
        "maxrss_mb": round(maxrss_mb(), 2),
        "final_acceptance": False,
    }


def profile_size_subprocess(
    checkpoint: Path,
    w: int,
    h: int,
    device: str = "cpu",
    timeout_s: int = 600,
) -> dict:
    """Run one forward size in a child so SIGKILL/OOM is observable by parent."""
    code = r"""
import gc, json, os, resource, sys, time
from pathlib import Path
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
os.environ['TORCH_NUM_THREADS']='1'

def rss():
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith('VmRSS:'):
            return int(line.split()[1])/1024.0
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0

def mx():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0

ckpt, w, h, device = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
stages=[]
stages.append({'stage':'child_start','rss_mb':round(rss(),2),'maxrss_mb':round(mx(),2)})
import numpy as np, torch
from spandrel import ImageModelDescriptor, ModelLoader
from ige.upscale.siax import MODEL_SHA256, file_sha256
torch.set_num_threads(1)
assert file_sha256(ckpt)==MODEL_SHA256
t0=time.perf_counter()
d=ModelLoader(device=device).load_from_file(ckpt)
assert isinstance(d, ImageModelDescriptor)
d.eval()
stages.append({'stage':'after_model_load','rss_mb':round(rss(),2),'maxrss_mb':round(mx(),2),'wall_s':round(time.perf_counter()-t0,3)})
baseline=stages[-1]['rss_mb']
arr=np.random.default_rng(0).random((h,w,3),dtype=np.float32)
tensor=torch.from_numpy(arr).permute(2,0,1).unsqueeze(0)
stages.append({'stage':'before_forward','rss_mb':round(rss(),2),'maxrss_mb':round(mx(),2),'input_wh':[w,h]})
t1=time.perf_counter()
with torch.inference_mode():
    out=d(tensor).float().cpu()
stages.append({'stage':'after_forward','rss_mb':round(rss(),2),'maxrss_mb':round(mx(),2),'wall_s':round(time.perf_counter()-t1,3),'delta_from_model_mb':round(rss()-baseline,2),'output_shape':list(out.shape),'ok':True})
print(json.dumps({'ok':True,'stages':stages,'maxrss_mb':round(mx(),2)}))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    env["TORCH_NUM_THREADS"] = "1"
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            [sys.executable, "-c", code, str(checkpoint), str(w), str(h), device],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "input_wh": [w, h],
            "status": "TIMEOUT",
            "wall_s": round(time.perf_counter() - t0, 3),
            "oom_stage_hypothesis": "unknown_timeout",
        }
    wall = round(time.perf_counter() - t0, 3)
    if p.returncode == 0:
        # last non-empty stdout line is JSON
        lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
        data = json.loads(lines[-1])
        data.update({"input_wh": [w, h], "returncode": 0, "wall_s": wall, "status": "OK"})
        return data
    # 137 = 128 + 9 SIGKILL often OOM
    status = "OOM_OR_SIGKILL" if p.returncode in (-9, 137, 35072) or p.returncode == 137 else f"EXIT_{p.returncode}"
    return {
        "ok": False,
        "input_wh": [w, h],
        "returncode": p.returncode,
        "status": status,
        "wall_s": wall,
        "stderr_tail": (p.stderr or "")[-500:],
        "stdout_tail": (p.stdout or "")[-500:],
        "oom_stage_label": "tile_forward" if status.startswith("OOM") else "unknown",
        "evidence_grade": "OBSERVED_exit" if status.startswith("OOM") else "OBSERVED_fail",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument(
        "--sizes",
        default="144x144,160x160,288x288,320x320",
        help="comma list WxH model input sizes (tile+2*pad)",
    )
    args = ap.parse_args()
    sizes = []
    for part in args.sizes.split(","):
        w, h = part.lower().split("x")
        sizes.append((int(h), int(w)))  # stored as (h,w) for array shape

    # Map for report labels
    label = {
        (144, 144): "128/8 input",
        (160, 160): "128/16 input",
        (288, 288): "256/16 input",
        (320, 320): "256/32 input",
    }

    report: dict = {
        "program": "SIAX_S2_1_P0_RAM_PROFILE",
        "final_acceptance": False,
        "device": args.device,
        "checkpoint": str(args.checkpoint),
        "sizes_requested": [f"{w}x{h}" for h, w in sizes],
        "size_labels": {f"{w}x{h}": label.get((w, h), "custom") for h, w in sizes},
        "method": {
            "rss": "Linux /proc/self/status VmRSS + ru_maxrss",
            "forward_input": "synthetic RNG float32 RGB — activation peak only, not quality",
            "oom_isolation": "each size also attempted in subprocess so parent survives SIGKILL",
        },
        "subprocess_by_size": {},
        "inprocess_summary": None,
        "conclusion": {},
    }

    # Prefer subprocess-per-size so 320 OOM does not kill the whole profile
    for h, w in sizes:
        key = f"{w}x{h}"
        print(f"=== subprocess profile {key} ===", flush=True)
        report["subprocess_by_size"][key] = profile_size_subprocess(
            args.checkpoint, w=w, h=h, device=args.device
        )
        print(json.dumps(report["subprocess_by_size"][key], indent=2)[:800], flush=True)

    # In-process cascade for sizes that succeeded alone (build activation table)
    ok_sizes = []
    for h, w in sizes:
        key = f"{w}x{h}"
        if report["subprocess_by_size"][key].get("ok"):
            ok_sizes.append((h, w))
    if ok_sizes:
        print("=== inprocess cascade on OK sizes ===", flush=True)
        report["inprocess_summary"] = profile_inprocess(args.checkpoint, ok_sizes, device=args.device)

    # conclusion
    peaks = {}
    oom = []
    for key, row in report["subprocess_by_size"].items():
        if row.get("ok"):
            # find after_forward maxrss
            mx = row.get("maxrss_mb")
            for st in row.get("stages") or []:
                if st.get("stage") == "after_forward":
                    mx = st.get("maxrss_mb", mx)
                    peaks[key] = {
                        "maxrss_mb": mx,
                        "rss_mb": st.get("rss_mb"),
                        "delta_from_model_mb": st.get("delta_from_model_mb"),
                        "wall_s": st.get("wall_s"),
                        "label": report["size_labels"].get(key),
                    }
        else:
            oom.append({"size": key, "status": row.get("status"), "label": report["size_labels"].get(key), "oom_stage_label": row.get("oom_stage_label")})

    report["conclusion"] = {
        "peaks_mb": peaks,
        "oom_sizes": oom,
        "hypothesis_tile_forward_peak": bool(oom),
        "evidence_grade": "OBSERVED" if (peaks or oom) else "NONE",
        "note": "Synthetic forward peak; real BASE tiles may differ slightly. Canvas stage measured only in inprocess cascade.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["conclusion"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
