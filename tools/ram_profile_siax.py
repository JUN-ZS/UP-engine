#!/usr/bin/env python3
"""Guarded full-image Siax RSS/VRAM profile on the real run_siax_upscale path."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

MIB = 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def read_rss(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def available_memory() -> tuple[int | None, str]:
    candidates: list[tuple[int, str]] = []
    try:
        maximum = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        current = int(Path("/sys/fs/cgroup/memory.current").read_text().strip())
        if maximum != "max" and 0 < int(maximum) < (1 << 60):
            candidates.append((max(0, int(maximum) - current), "cgroup_v2_remaining"))
    except (OSError, ValueError):
        pass
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                candidates.append((int(line.split()[1]) * 1024, "host_memavailable"))
                break
    except (OSError, ValueError, IndexError):
        pass
    return min(candidates, key=lambda x: x[0]) if candidates else (None, "unavailable")


def oom_kill_count() -> int | None:
    try:
        for line in Path("/sys/fs/cgroup/memory.events").read_text().splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[0] == "oom_kill":
                return int(fields[1])
    except (OSError, ValueError):
        pass
    return None


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def child_main(config_path: Path) -> int:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sys.path.insert(0, str(SRC))
    events = Path(config["events"])
    stage_file = Path(config["stage"])
    result_file = Path(config["result"])
    atomic_json(stage_file, {"stage": "process_startup", "event": "start", "active": True})

    def on_stage(event: dict[str, Any]) -> None:
        record = dict(event)
        record["sampled_unix"] = time.time()
        atomic_json(stage_file, {
            "stage": record.get("stage", "unknown"),
            "event": record.get("event"),
            "active": record.get("event") == "start",
            "pid": os.getpid(),
            "rss_bytes": record.get("rss_bytes"),
            "maxrss_bytes": record.get("maxrss_bytes"),
            "cuda_peak_allocated_bytes": record.get("cuda_peak_allocated_bytes"),
        })
        with events.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()

    try:
        from ige.upscale.siax import run_siax_upscale
        data = run_siax_upscale(
            config["input"], config["checkpoint"], config["output"],
            tile_size=config["tile_size"], tile_pad=config["tile_pad"],
            confirm_model_license_review=config["license_review_confirmed"],
            device=config["device"], stage_callback=on_stage,
        )
        atomic_json(result_file, {
            "status": "completed",
            "output_sha256": data["output_sha256"],
            "output_dimensions": data["output_dimensions"],
            "runtime": data["runtime"],
            "metadata_path": data["metadata_path"],
        })
        return 0
    except BaseException as exc:
        atomic_json(result_file, {
            "status": "failed", "error_type": type(exc).__name__, "error": str(exc)
        })
        on_stage({
            "stage": "python_exception", "event": "failure",
            "error_type": type(exc).__name__, "error": str(exc),
        })
        return 1


def stop_child(proc: subprocess.Popen[Any], grace: float) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=max(0.1, grace))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def profile(args: argparse.Namespace) -> dict[str, Any]:
    if not Path("/proc/self/status").is_file():
        raise RuntimeError("guarded profile requires Linux /proc")
    source, checkpoint, report_path = (p.expanduser().resolve() for p in (args.input, args.checkpoint, args.out))
    output = (args.output or report_path.with_name(report_path.stem + ".SIAX4X.png")).expanduser().resolve()
    if not source.is_file() or not checkpoint.is_file():
        raise FileNotFoundError("input BASE image and checkpoint must exist")
    if output.suffix.lower() != ".png":
        raise ValueError("profile output must be a lossless .png")
    if len({source, checkpoint, report_path, output}) != 4:
        raise ValueError("input, checkpoint, report and output paths must be distinct")
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output exists: {output}; use --overwrite explicitly")
    if args.overwrite:
        output.unlink(missing_ok=True)
        output.with_suffix(".upscale.json").unlink(missing_ok=True)

    available, source_name = available_memory()
    if available is None:
        raise RuntimeError("available RAM is unknown; refusing unguarded real inference")
    budget = available - args.reserve_mib * MIB
    if budget < 256 * MIB:
        raise RuntimeError(f"only {budget / MIB:.0f} MiB remains after reserve; refusing run")
    limit = min(budget, args.max_rss_mib * MIB) if args.max_rss_mib else budget
    report_path.parent.mkdir(parents=True, exist_ok=True)
    before_oom = oom_kill_count()
    started = time.time()

    with tempfile.TemporaryDirectory(prefix="siax-full-profile-") as temp_dir:
        temp = Path(temp_dir)
        stage_file, events_file = temp / "stage.json", temp / "events.jsonl"
        result_file, config_file, log_file = temp / "result.json", temp / "config.json", temp / "child.log"
        config = {
            "input": str(source), "checkpoint": str(checkpoint), "output": str(output),
            "tile_size": args.tile_size, "tile_pad": args.tile_pad, "device": args.device,
            "license_review_confirmed": args.confirm_model_license_review,
            "stage": str(stage_file), "events": str(events_file), "result": str(result_file),
        }
        config_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
        for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "TORCH_NUM_THREADS"):
            env[variable] = str(args.threads)

        sampled_peak = 0
        per_stage_peak: dict[str, int] = {}
        per_stage_hwm: dict[str, int] = {}
        per_stage_cuda_peak: dict[str, int] = {}
        samples = 0
        last_stage = "process_startup"
        last_active_stage = "process_startup"
        stop_reason: str | None = None
        with log_file.open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--_child-config", str(config_file)],
                cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT, text=True,
            )
            run_started = time.monotonic()
            while proc.poll() is None:
                sample_stage = last_active_stage
                is_active = True
                try:
                    state = json.loads(stage_file.read_text(encoding="utf-8"))
                    last_stage = str(state.get("stage", last_stage))
                    is_active = bool(state.get("active", True))
                    if is_active:
                        last_active_stage = last_stage
                    sample_stage = last_stage if is_active else "between_stages"
                    hwm = state.get("maxrss_bytes")
                    if hwm is not None:
                        per_stage_hwm[last_stage] = max(per_stage_hwm.get(last_stage, 0), int(hwm))
                        # HWM is sampled at stage boundaries; stop before starting another tile
                        # when the previous completed stage has already crossed the configured budget.
                        if int(hwm) >= limit and is_active is False and proc.poll() is None:
                            stop_reason = "observed_hwm_budget_stop"
                            stop_child(proc, args.grace_seconds)
                            break
                    cuda_peak = state.get("cuda_peak_allocated_bytes")
                    if cuda_peak is not None:
                        per_stage_cuda_peak[last_stage] = max(per_stage_cuda_peak.get(last_stage, 0), int(cuda_peak))
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    pass

                current = read_rss(proc.pid)
                if current is not None:
                    samples += 1
                    sampled_peak = max(sampled_peak, current)
                    per_stage_peak[sample_stage] = max(per_stage_peak.get(sample_stage, 0), current)
                    if current >= limit:
                        stop_reason = "safety_guard_stopped"
                        stop_child(proc, args.grace_seconds)
                        break

                if args.timeout_seconds and time.monotonic() - run_started >= args.timeout_seconds:
                    stop_reason = "timeout_stopped"
                    stop_child(proc, args.grace_seconds)
                    break
                time.sleep(args.poll_ms / 1000.0)
            child_exit = proc.wait()

        after_oom = oom_kill_count()
        try:
            child_result = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            child_result = None
        try:
            stage_events = [json.loads(line) for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError):
            stage_events = []
        try:
            log_tail = log_file.read_text(encoding="utf-8", errors="replace")[-10000:]
        except OSError:
            log_tail = ""

    if stop_reason:
        status = stop_reason
    elif child_exit in (-signal.SIGKILL, 137) and before_oom is not None and after_oom is not None and after_oom > before_oom:
        status = "cgroup_oom_killed"
    elif child_exit in (-signal.SIGKILL, 137):
        status = "sigkill_cause_unknown"
    elif child_exit == 0:
        status = "completed"
    else:
        status = "failed"

    report = {
        "format": "ige.siax.full-job-ram-profile", "format_version": "1.0",
        "status": status, "evidence_grade": "OBSERVED",
        "cell": {"tile_size": args.tile_size, "tile_pad": args.tile_pad, "device": args.device, "threads": args.threads},
        "input": {"path": str(source), "sha256": sha256(source)},
        "checkpoint": {"path": str(checkpoint), "sha256": sha256(checkpoint)},
        "output": {
            "path": str(output), "exists": output.is_file(),
            "bytes": output.stat().st_size if output.is_file() else None,
            "sha256": sha256(output) if output.is_file() else None,
        },
        "memory": {
            "available_before_run_bytes": available, "available_source": source_name,
            "reserve_mib": args.reserve_mib, "effective_child_rss_limit_bytes": limit,
            "poll_ms": args.poll_ms, "samples": samples, "sampled_peak_rss_bytes": sampled_peak,
            "sampled_peak_rss_by_stage_bytes": per_stage_peak,
            "child_maxrss_at_stage_events_bytes": per_stage_hwm,
            "cuda_peak_allocated_bytes_by_stage": per_stage_cuda_peak,
            "oom_kill_counter_before": before_oom, "oom_kill_counter_after": after_oom,
        },
        "stage_events": stage_events, "last_active_stage": last_active_stage,
        "child_result": child_result, "child_exit_code": child_exit,
        "elapsed_seconds": round(time.time() - started, 3), "child_log_tail": log_tail,
        "interpretation": {
            "safety_guard_stopped": "intentional RSS safety stop, not an OOM",
        "observed_hwm_budget_stop": "stage-boundary process high-water exceeded budget; stopped before next tile, not an OOM label",
            "cgroup_oom_killed": "cgroup OOM counter increased and child was SIGKILLed",
            "sigkill_cause_unknown": "SIGKILL without corroborating cgroup OOM counter; cause unknown",
            "completed": "full run completed; review stage high-water values and visual output separately",
        },
        "limits": [
            "RSS polling can miss transient peaks; stage-boundary process HWM is recorded as a second measure. A boundary-triggered stop cannot prevent the first tile's transient peak.",
            "If a hard OOM occurs before a callback, last active stage is best-effort attribution.",
            "CUDA allocation stats are not equal to total system/driver VRAM use.",
            "A completed profile is not a quality acceptance.",
        ],
        "final_acceptance": False,
    }
    atomic_json(report_path, report)
    return report


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--_child-config":
        return child_main(Path(sys.argv[2]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    # Conservative default; larger cells must be requested explicitly after reviewing the budget.
    parser.add_argument("--tile-size", type=int, default=128)
    parser.add_argument("--tile-pad", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--reserve-mib", type=int, default=512)
    parser.add_argument("--max-rss-mib", type=int)
    parser.add_argument("--poll-ms", type=int, default=50)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--grace-seconds", type=float, default=3.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--confirm-model-license-review", action="store_true")
    args = parser.parse_args()
    if not args.confirm_model_license_review:
        parser.error("--confirm-model-license-review is required before running Siax")
    if args.tile_size < 32 or args.tile_pad < 0 or args.tile_pad >= args.tile_size:
        parser.error("tile-size must be >=32 and tile-pad in [0, tile-size)")
    if args.threads < 1 or args.poll_ms < 10 or args.reserve_mib < 0 or args.timeout_seconds < 0:
        parser.error("threads >=1, poll-ms >=10, reserve-mib >=0 and timeout >=0 required")
    if args.max_rss_mib is not None and args.max_rss_mib < 256:
        parser.error("--max-rss-mib must be >=256")
    report = profile(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
