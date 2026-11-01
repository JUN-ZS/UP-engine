from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import time
import uuid
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local_pc_status() -> dict[str, Any]:
    """Tool: local_pc_status — CPU / RAM / GPU / VRAM snapshot."""
    cpu = os.cpu_count() or 1
    ram_total = ram_avail = None
    try:
        if Path("/proc/meminfo").is_file():
            info = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    info[k.strip()] = v.strip()

            def mib(key: str) -> float | None:
                parts = info.get(key, "").split()
                return float(parts[0]) / 1024.0 if parts else None

            ram_total = mib("MemTotal")
            ram_avail = mib("MemAvailable") or mib("MemFree")
        elif os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            ram_total = st.ullTotalPhys / (1024 * 1024)
            ram_avail = st.ullAvailPhys / (1024 * 1024)
    except Exception:
        pass

    gpu: list[dict[str, Any]] = []
    torch_cuda = False
    try:
        import torch

        torch_cuda = bool(torch.cuda.is_available())
        if torch_cuda:
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                free_b, total_b = torch.cuda.mem_get_info(i)
                gpu.append(
                    {
                        "index": i,
                        "name": props.name,
                        "vram_total_mib": round(total_b / (1024 * 1024), 1),
                        "vram_free_mib": round(free_b / (1024 * 1024), 1),
                    }
                )
    except Exception as exc:
        gpu.append({"error": str(exc)})

    return {
        "format": "ige.spm.local_pc_status",
        "format_version": "1.0",
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_threads": cpu,
        "ram_total_mib": ram_total,
        "ram_available_mib": ram_avail,
        "cuda_available": torch_cuda,
        "gpus": gpu,
        "backend": {
            "cloud_imagine": "not_here",
            "native_siax": "available_via_spm_local_execute",
            "comfyui_required": False,
            "s3_scheduler_required": False,
        },
        "final_acceptance": False,
        "e3_speed_claim": False,
    }


class JobStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = self.root / "jobs.jsonl"

    def _job_dir(self, job_id: str) -> Path:
        d = self.root / job_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_meta(self, job_id: str, meta: dict[str, Any]) -> Path:
        p = self._job_dir(job_id) / "result.json"
        p.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        with self.index.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"job_id": job_id, "at": time.time()}) + "\n")
        return p

    def read_meta(self, job_id: str) -> dict[str, Any] | None:
        p = self._job_dir(job_id) / "result.json"
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))


def spm_local_execute(
    *,
    input_path: str | Path,
    output_path: str | Path | None = None,
    checkpoint: str | Path = "models/4x_NMKD-Siax_200k.pth",
    device: str = "auto",
    tile_size: int = 128,
    tile_pad: int = 8,
    confirm_model_license_review: bool = False,
    job_store: JobStore | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Tool: spm_local_execute — run existing native Siax (run_siax_upscale).

    No ComfyUI. No SPM rewrite. No S3 scheduler.
    """
    if not confirm_model_license_review:
        raise PermissionError("confirm_model_license_review required")

    from ige.upscale.siax import MODEL_ID, MODEL_SHA256, run_siax_upscale

    src = Path(input_path)
    if not src.is_file():
        raise FileNotFoundError(f"input not found: {src}")
    ckpt = Path(checkpoint)
    jid = job_id or f"spm_{uuid.uuid4().hex[:12]}"
    store = job_store or JobStore(Path("runs/spm_local"))
    out = Path(output_path) if output_path else (store._job_dir(jid) / "OUT_SIAX4X.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    status_before = local_pc_status()
    report = run_siax_upscale(
        src,
        ckpt,
        out,
        tile_size=tile_size,
        tile_pad=tile_pad,
        confirm_model_license_review=True,
        device=device,
    )
    wall = time.perf_counter() - t0
    status_after = local_pc_status()
    sha = file_sha256(out)
    with __import__("PIL").Image.open(out) as im:
        w, h = im.size

    result = {
        "format": "ige.spm.local_execute_result",
        "format_version": "1.0",
        "job_id": jid,
        "ok": True,
        "input_path": str(src.resolve()),
        "input_sha256": file_sha256(src),
        "output_path": str(out.resolve()),
        "output_sha256": sha,
        "width": w,
        "height": h,
        "model_id": MODEL_ID,
        "model_sha256": MODEL_SHA256,
        "device_used": report.get("device") or report.get("selected_device") or device,
        "tile_size": tile_size,
        "tile_pad": tile_pad,
        "wall_s": round(wall, 3),
        "siax_report": report,
        "pc_status_before": {
            "ram_available_mib": status_before.get("ram_available_mib"),
            "cuda_available": status_before.get("cuda_available"),
            "gpus": status_before.get("gpus"),
        },
        "pc_status_after": {
            "ram_available_mib": status_after.get("ram_available_mib"),
            "cuda_available": status_after.get("cuda_available"),
            "gpus": status_after.get("gpus"),
        },
        "backend": "native_siax_local",
        "comfyui": False,
        "s3_scheduler": False,
        "cloud_imagine": False,
        "final_acceptance": False,
        "e3_speed_claim": False,
        "quality_qualified": False,
    }
    store.write_meta(jid, result)
    return result


def spm_local_result(job_id: str, *, job_store: JobStore | None = None) -> dict[str, Any]:
    """Tool: spm_local_result — fetch prior execute result + SHA."""
    store = job_store or JobStore(Path("runs/spm_local"))
    meta = store.read_meta(job_id)
    if meta is None:
        return {
            "format": "ige.spm.local_result",
            "ok": False,
            "job_id": job_id,
            "error": "job_not_found",
        }
    out = {
        "format": "ige.spm.local_result",
        "format_version": "1.0",
        "ok": True,
        "job_id": job_id,
        "output_path": meta.get("output_path"),
        "output_sha256": meta.get("output_sha256"),
        "width": meta.get("width"),
        "height": meta.get("height"),
        "device_used": meta.get("device_used"),
        "wall_s": meta.get("wall_s"),
        "model_id": meta.get("model_id"),
        "model_sha256": meta.get("model_sha256"),
        "final_acceptance": False,
        "e3_speed_claim": False,
        "result": meta,
    }
    return out
