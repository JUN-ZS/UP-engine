from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .siax import MODEL_ID, MODEL_SHA256, MODEL_URL, allocate_output_canvas, file_sha256


class DistributedSiaxError(RuntimeError):
    """Raised when a distributed Siax job is incomplete or inconsistent."""


def _json_bytes(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise DistributedSiaxError(f"job path escapes its root: {relative}")
    return candidate


def _worker_token(worker_id: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", worker_id).strip(".-")
    if not token:
        raise ValueError("worker_id must contain at least one safe character")
    return token[:80]


def prepare_siax_job(
    input_path: str | Path,
    job_dir: str | Path,
    *,
    tile_size: int = 128,
    tile_pad: int = 8,
) -> dict[str, Any]:
    """Create a deterministic, filesystem-backed queue of halo-padded Siax tile tasks."""
    source = Path(input_path)
    root = Path(job_dir)
    if not source.is_file():
        raise FileNotFoundError(source)
    if tile_size < 32 or tile_pad < 0 or tile_pad >= tile_size:
        raise ValueError("tile_size must be >=32 and tile_pad must be in [0, tile_size)")
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"job directory must be new or empty: {root}")

    for name in ("inputs", "pending", "in_progress", "completed", "results"):
        (root / name).mkdir(parents=True, exist_ok=True)

    with Image.open(source) as opened:
        base = ImageOps.exif_transpose(opened).convert("RGB")
    width, height = base.size
    base_path = root / "base_rgb.png"
    base.save(base_path, format="PNG", compress_level=1)
    base_sha = file_sha256(base_path)
    source_sha = file_sha256(source)

    grid_width = (width + tile_size - 1) // tile_size
    grid_height = (height + tile_size - 1) // tile_size
    tasks: list[dict[str, Any]] = []

    for row in range(grid_height):
        for column in range(grid_width):
            x0, y0 = column * tile_size, row * tile_size
            x1, y1 = min(x0 + tile_size, width), min(y0 + tile_size, height)
            ex0, ey0 = max(0, x0 - tile_pad), max(0, y0 - tile_pad)
            ex1, ey1 = min(width, x1 + tile_pad), min(height, y1 + tile_pad)
            task_id = f"r{row:05d}_c{column:05d}"
            input_relative = f"inputs/{task_id}.png"
            tile_path = _safe_child(root, input_relative)
            base.crop((ex0, ey0, ex1, ey1)).save(tile_path, format="PNG", compress_level=1)
            task = {
                "task_id": task_id,
                "row": row,
                "column": column,
                "core_box": [x0, y0, x1, y1],
                "input_box": [ex0, ey0, ex1, ey1],
                "input_path": input_relative,
                "input_sha256": file_sha256(tile_path),
                "output_path": f"results/{task_id}.png",
                "result_path": f"results/{task_id}.json",
                "expected_output_size": [(x1 - x0) * 4, (y1 - y0) * 4],
            }
            tasks.append(task)

    identity = {
        "base_rgb_sha256": base_sha,
        "checkpoint_sha256": MODEL_SHA256,
        "scale": 4,
        "tile_size": tile_size,
        "tile_pad": tile_pad,
    }
    job_id = hashlib.sha256(_json_bytes(identity).encode("utf-8")).hexdigest()[:24]
    manifest = {
        "format": "ige.siax.distributed-job",
        "format_version": "1.0",
        "job_id": job_id,
        "model_id": MODEL_ID,
        "model_url": MODEL_URL,
        "checkpoint_sha256": MODEL_SHA256,
        "scale": 4,
        "source": {
            "path": str(source.resolve()),
            "sha256": source_sha,
            "base_rgb_path": "base_rgb.png",
            "base_rgb_sha256": base_sha,
            "width": width,
            "height": height,
            "mode": "RGB",
        },
        "tiling": {
            "tile_size": tile_size,
            "tile_pad": tile_pad,
            "grid_width": grid_width,
            "grid_height": grid_height,
            "task_count": len(tasks),
            "context_policy": "halo_input_crop_then_keep_only_core_output",
        },
        "tasks": tasks,
        "execution": {
            "status": "planned",
            "workers": [],
            "completed_task_count": 0,
        },
        "acceptance": "candidate_only",
        "final_acceptance": False,
    }
    _write_json_atomic(root / "manifest.json", manifest)
    for task in tasks:
        _write_json_atomic(root / "pending" / f"{task['task_id']}.json", task)
    return manifest


def load_siax_job(job_dir: str | Path) -> dict[str, Any]:
    root = Path(job_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "ige.siax.distributed-job" or manifest.get("format_version") != "1.0":
        raise DistributedSiaxError("unsupported distributed Siax job format")
    if manifest.get("scale") != 4 or manifest.get("checkpoint_sha256") != MODEL_SHA256:
        raise DistributedSiaxError("job does not target the pinned Siax 4x checkpoint")
    task_ids = [task.get("task_id") for task in manifest.get("tasks", [])]
    if not task_ids or len(task_ids) != len(set(task_ids)):
        raise DistributedSiaxError("manifest task IDs are empty or duplicated")
    return manifest


def claim_next_task(job_dir: str | Path, worker_id: str) -> dict[str, Any] | None:
    """Atomically move one pending task into a worker-specific in-progress directory."""
    root = Path(job_dir)
    load_siax_job(root)
    token = _worker_token(worker_id)
    worker_dir = root / "in_progress" / token
    worker_dir.mkdir(parents=True, exist_ok=True)
    for pending in sorted((root / "pending").glob("*.json")):
        claimed = worker_dir / pending.name
        try:
            os.replace(pending, claimed)
        except FileNotFoundError:
            continue
        return json.loads(claimed.read_text(encoding="utf-8"))
    return None


def release_claim(job_dir: str | Path, worker_id: str, task_id: str) -> None:
    root = Path(job_dir)
    token = _worker_token(worker_id)
    claimed = root / "in_progress" / token / f"{task_id}.json"
    pending = root / "pending" / claimed.name
    if not claimed.is_file():
        raise FileNotFoundError(claimed)
    if pending.exists():
        raise DistributedSiaxError(f"cannot release {task_id}: pending task already exists")
    os.replace(claimed, pending)


def complete_claim(
    job_dir: str | Path,
    worker_id: str,
    task: dict[str, Any],
    output: Image.Image,
    *,
    device: str,
    runtime_seconds: float,
) -> dict[str, Any]:
    """Persist one core-only tile result and atomically mark its claim complete."""
    root = Path(job_dir)
    manifest = load_siax_job(root)
    task_id = str(task["task_id"])
    token = _worker_token(worker_id)
    claimed = root / "in_progress" / token / f"{task_id}.json"
    if not claimed.is_file():
        raise FileNotFoundError(f"worker {token} does not own task {task_id}")
    canonical_task = next((item for item in manifest["tasks"] if item["task_id"] == task_id), None)
    if canonical_task is None or canonical_task != task:
        raise DistributedSiaxError(f"task {task_id} does not match the job manifest")

    expected_size = tuple(task["expected_output_size"])
    patch = output.convert("RGB")
    if patch.size != expected_size:
        raise DistributedSiaxError(
            f"tile {task_id} has size {patch.size}, expected {expected_size}"
        )

    output_path = _safe_child(root, task["output_path"])
    temporary_output = output_path.with_name(output_path.stem + f".{os.getpid()}.tmp.png")
    patch.save(temporary_output, format="PNG", compress_level=1)
    os.replace(temporary_output, output_path)

    result = {
        "format": "ige.siax.tile-result",
        "format_version": "1.0",
        "job_id": manifest["job_id"],
        "task_id": task_id,
        "core_box": task["core_box"],
        "input_sha256": task["input_sha256"],
        "checkpoint_sha256": manifest["checkpoint_sha256"],
        "output_path": task["output_path"],
        "output_sha256": file_sha256(output_path),
        "output_size": list(patch.size),
        "worker_id": token,
        "device": device,
        "runtime_seconds": max(0.0, float(runtime_seconds)),
        "completed_unix": time.time(),
        "acceptance": "candidate_only",
    }
    result_path = _safe_child(root, task["result_path"])
    _write_json_atomic(result_path, result)
    completed = root / "completed" / claimed.name
    os.replace(claimed, completed)
    return result


def _load_runtime(checkpoint_path: str | Path, device: str) -> tuple[Any, Any, str, str]:
    checkpoint = Path(checkpoint_path)
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    actual_sha = file_sha256(checkpoint)
    if actual_sha != MODEL_SHA256:
        raise DistributedSiaxError(
            f"checkpoint hash mismatch: expected {MODEL_SHA256}, got {actual_sha}"
        )
    try:
        import numpy as np
        import torch
        from spandrel import ImageModelDescriptor, ModelLoader
    except ImportError as exc:
        raise RuntimeError("install the optional upscale extra to run Siax inference") from exc

    if device == "auto":
        selected_device = "cuda" if torch.cuda.is_available() else "cpu"
    elif device in {"cpu", "cuda"}:
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        selected_device = device
    else:
        raise ValueError("device must be auto, cpu or cuda")

    descriptor = ModelLoader(device=selected_device).load_from_file(str(checkpoint))
    if not isinstance(descriptor, ImageModelDescriptor):
        raise DistributedSiaxError("checkpoint is not a supported image-to-image model")
    architecture = str(getattr(descriptor.architecture, "name", descriptor.architecture))
    if "esrgan" not in architecture.lower() or int(descriptor.scale) != 4:
        raise DistributedSiaxError(
            f"expected ESRGAN architecture at 4x scale; got {architecture} at {descriptor.scale}x"
        )
    descriptor.eval()
    return np, torch, descriptor, selected_device


def run_siax_worker(
    job_dir: str | Path,
    checkpoint_path: str | Path,
    *,
    worker_id: str | None = None,
    device: str = "auto",
    max_tasks: int | None = None,
    confirm_model_license_review: bool = False,
) -> dict[str, Any]:
    """Run queued tasks, loading the checkpoint once per worker process."""
    if not confirm_model_license_review:
        raise PermissionError("review checkpoint provenance and license before enabling this model")
    root = Path(job_dir)
    manifest = load_siax_job(root)
    checkpoint_sha = file_sha256(checkpoint_path)
    if checkpoint_sha != manifest["checkpoint_sha256"]:
        raise DistributedSiaxError("worker checkpoint does not match the job manifest")
    worker = _worker_token(worker_id or f"{socket.gethostname()}-{os.getpid()}")

    if not any((root / "pending").glob("*.json")):
        return {"worker_id": worker, "device": device, "tasks_completed": 0, "status": "no_pending_tasks"}

    np, torch, descriptor, selected_device = _load_runtime(checkpoint_path, device)
    completed_results: list[dict[str, Any]] = []
    while max_tasks is None or len(completed_results) < max_tasks:
        task = claim_next_task(root, worker)
        if task is None:
            break
        started = time.perf_counter()
        try:
            input_path = _safe_child(root, task["input_path"])
            if file_sha256(input_path) != task["input_sha256"]:
                raise DistributedSiaxError(f"tile input hash mismatch: {task['task_id']}")
            with Image.open(input_path) as opened:
                tile_image = opened.convert("RGB")
            array = np.asarray(tile_image, dtype=np.float32).copy() / 255.0
            tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(selected_device)
            with torch.inference_mode():
                predicted = descriptor(tensor)
                predicted = predicted.float().cpu()
            input_box = task["input_box"]
            core_box = task["core_box"]
            scale = int(manifest["scale"])
            expected_shape = (1, 3, tile_image.height * scale, tile_image.width * scale)
            if tuple(predicted.shape) != expected_shape:
                raise DistributedSiaxError(
                    f"model returned {tuple(predicted.shape)} for {task['task_id']}; expected {expected_shape}"
                )
            left = (core_box[0] - input_box[0]) * scale
            top = (core_box[1] - input_box[1]) * scale
            right = left + (core_box[2] - core_box[0]) * scale
            bottom = top + (core_box[3] - core_box[1]) * scale
            core = predicted[0, :, top:bottom, left:right].permute(1, 2, 0).numpy()
            core = np.clip(core * 255.0 + 0.5, 0, 255).astype(np.uint8)
            patch = Image.fromarray(core, "RGB")
            elapsed = time.perf_counter() - started
            result = complete_claim(
                root, worker, task, patch, device=selected_device, runtime_seconds=elapsed
            )
            completed_results.append(result)
            del tensor, predicted, core, patch
        except Exception:
            release_claim(root, worker, task["task_id"])
            raise

    return {
        "worker_id": worker,
        "device": selected_device,
        "tasks_completed": len(completed_results),
        "task_ids": [item["task_id"] for item in completed_results],
        "runtime_seconds": sum(item["runtime_seconds"] for item in completed_results),
        "status": "completed" if completed_results else "no_pending_tasks",
        "final_acceptance": False,
    }


def stitch_siax_job(
    job_dir: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Verify every tile receipt and stitch the uint8 4x master; never auto-accept it."""
    root = Path(job_dir)
    manifest = load_siax_job(root)
    width = int(manifest["source"]["width"])
    height = int(manifest["source"]["height"])
    scale = int(manifest["scale"])
    canvas = allocate_output_canvas(width, height, scale)
    import numpy as np

    coverage = np.zeros((height, width), dtype=np.uint8)
    workers: set[str] = set()
    results: list[dict[str, Any]] = []

    for task in manifest["tasks"]:
        task_id = task["task_id"]
        completed_marker = root / "completed" / f"{task_id}.json"
        result_path = _safe_child(root, task["result_path"])
        output_tile_path = _safe_child(root, task["output_path"])
        if not completed_marker.is_file() or not result_path.is_file() or not output_tile_path.is_file():
            raise DistributedSiaxError(f"job incomplete: missing completed tile {task_id}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        expected_fields = {
            "job_id": manifest["job_id"],
            "task_id": task_id,
            "core_box": task["core_box"],
            "input_sha256": task["input_sha256"],
            "checkpoint_sha256": manifest["checkpoint_sha256"],
        }
        for key, expected in expected_fields.items():
            if result.get(key) != expected:
                raise DistributedSiaxError(f"tile {task_id} result mismatch for {key}")
        if file_sha256(output_tile_path) != result.get("output_sha256"):
            raise DistributedSiaxError(f"tile {task_id} output hash mismatch")
        if file_sha256(_safe_child(root, task["input_path"])) != task["input_sha256"]:
            raise DistributedSiaxError(f"tile {task_id} input changed after planning")

        x0, y0, x1, y1 = task["core_box"]
        if np.any(coverage[y0:y1, x0:x1]):
            raise DistributedSiaxError(f"overlapping output core detected at {task_id}")
        coverage[y0:y1, x0:x1] = 1
        with Image.open(output_tile_path) as opened:
            tile = np.asarray(opened.convert("RGB"), dtype=np.uint8)
        expected_width, expected_height = task["expected_output_size"]
        if tile.shape != (expected_height, expected_width, 3):
            raise DistributedSiaxError(f"tile {task_id} output dimensions are invalid")
        canvas[y0 * scale:y1 * scale, x0 * scale:x1 * scale] = tile
        workers.add(str(result["worker_id"]))
        results.append(result)

    if not np.all(coverage == 1):
        missing = int(coverage.size - np.count_nonzero(coverage))
        raise DistributedSiaxError(f"output has {missing} uncovered source pixels")

    output = Path(output_path)
    if output.suffix.lower() != ".png":
        raise ValueError("distributed Siax master output must be a lossless PNG")
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(canvas, "RGB").save(output, format="PNG", compress_level=3)

    vertical_seams: list[float] = []
    horizontal_seams: list[float] = []
    for column in range(1, int(manifest["tiling"]["grid_width"])):
        boundary = min(column * int(manifest["tiling"]["tile_size"]), width) * scale
        if 0 < boundary < width * scale:
            delta = np.abs(canvas[:, boundary - 1].astype(np.int16) - canvas[:, boundary].astype(np.int16))
            vertical_seams.append(float(delta.mean()))
    for row in range(1, int(manifest["tiling"]["grid_height"])):
        boundary = min(row * int(manifest["tiling"]["tile_size"]), height) * scale
        if 0 < boundary < height * scale:
            delta = np.abs(canvas[boundary - 1].astype(np.int16) - canvas[boundary].astype(np.int16))
            horizontal_seams.append(float(delta.mean()))

    elapsed = sum(float(item.get("runtime_seconds", 0.0)) for item in results)
    report = {
        "upscale_version": "1.0",
        "execution_mode": "distributed_filesystem_tile_queue",
        "job_id": manifest["job_id"],
        "model_id": manifest["model_id"],
        "checkpoint_sha256": manifest["checkpoint_sha256"],
        "checkpoint_source": manifest["model_url"],
        "source_sha256": manifest["source"]["sha256"],
        "base_rgb_sha256": manifest["source"]["base_rgb_sha256"],
        "input_dimensions": {"width": width, "height": height},
        "output_path": str(output.resolve()),
        "output_sha256": file_sha256(output),
        "output_dimensions": {"width": width * scale, "height": height * scale},
        "tiling": manifest["tiling"],
        "execution": {
            "completed_tiles": len(results),
            "worker_count": len(workers),
            "workers": sorted(workers),
            "sum_of_worker_inference_seconds": elapsed,
        },
        "seam_diagnostics": {
            "status": "diagnostic_only_not_an_acceptance_gate",
            "vertical_seam_count": len(vertical_seams),
            "horizontal_seam_count": len(horizontal_seams),
            "vertical_mean_absolute_boundary_delta": (
                sum(vertical_seams) / len(vertical_seams) if vertical_seams else None
            ),
            "horizontal_mean_absolute_boundary_delta": (
                sum(horizontal_seams) / len(horizontal_seams) if horizontal_seams else None
            ),
        },
        "acceptance": "candidate_only",
        "final_acceptance": False,
        "limitations": [
            "Tile boundary metrics are diagnostic and are not proof of seam-free output.",
            "All workers must use the same pinned checkpoint, scale, preprocessing and compatible numerical settings.",
            "A shared filesystem must provide atomic rename semantics for the pending-to-claimed queue.",
            "GitHub-hosted runners cannot directly access a private local work directory; use an explicit artifact/object-store bridge or a secured self-hosted runner.",
            "This output still requires independent identity, topology, geometry and perceptual review.",
        ],
    }
    sidecar = output.with_suffix(".upscale.json")
    _write_json_atomic(sidecar, report)
    return report | {"metadata_path": str(sidecar.resolve())}
