"""HERE chat ↔ local .venv SPM handoff (no grok.com OAuth, no ComfyUI).

Flow:
  1) HERE writes a request JSON (or human saves one under inbox/).
  2) Local .venv runs: python tools/spm_here_pull.py --once | --watch
  3) Executor runs native Siax; writes result JSON + PNG under outbox/.
  4) Human pastes result JSON back to chat (or commits evidence).

Remote Grok cannot SSH into the PC; pull agent on the PC is required.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


REQUEST_FORMAT = "ige.spm.here_request"
RESULT_FORMAT = "ige.spm.here_result"


def new_request(
    *,
    input_path: str,
    output_path: str | None = None,
    device: str = "auto",
    tile_size: int = 128,
    tile_pad: int = 8,
    note: str = "",
    source_asset_hint: str = "",
) -> dict[str, Any]:
    rid = f"here_{uuid.uuid4().hex[:12]}"
    return {
        "format": REQUEST_FORMAT,
        "format_version": "1.0",
        "request_id": rid,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_path": input_path,
        "output_path": output_path,
        "device": device,
        "tile_size": tile_size,
        "tile_pad": tile_pad,
        "confirm_model_license_review": True,
        "checkpoint": "models/4x_NMKD-Siax_200k.pth",
        "note": note,
        "source_asset_hint": source_asset_hint,
        "cloud_imagine": "may_have_produced_input",
        "backend": "native_siax_local",
        "final_acceptance": False,
        "e3_speed_claim": False,
    }


def write_request(inbox: Path, req: dict[str, Any]) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"{req['request_id']}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(req, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def list_pending(inbox: Path) -> list[Path]:
    if not inbox.is_dir():
        return []
    return sorted(inbox.glob("here_*.json"))


def process_one(
    req_path: Path,
    *,
    outbox: Path,
    done_dir: Path,
    job_store: Path,
) -> dict[str, Any]:
    from ige.spm_local.executor import JobStore, spm_local_execute

    req = json.loads(req_path.read_text(encoding="utf-8"))
    if req.get("format") != REQUEST_FORMAT:
        raise ValueError(f"bad request format in {req_path}")
    outbox.mkdir(parents=True, exist_ok=True)
    done_dir.mkdir(parents=True, exist_ok=True)
    store = JobStore(job_store)

    out_path = req.get("output_path")
    if not out_path:
        out_path = str(outbox / f"{req['request_id']}_OUT.png")

    exec_result = spm_local_execute(
        input_path=req["input_path"],
        output_path=out_path,
        checkpoint=req.get("checkpoint") or "models/4x_NMKD-Siax_200k.pth",
        device=req.get("device") or "auto",
        tile_size=int(req.get("tile_size") or 128),
        tile_pad=int(req.get("tile_pad") or 8),
        confirm_model_license_review=bool(req.get("confirm_model_license_review")),
        job_store=store,
        job_id=req.get("request_id"),
    )

    result = {
        "format": RESULT_FORMAT,
        "format_version": "1.0",
        "request_id": req["request_id"],
        "ok": bool(exec_result.get("ok")),
        "completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_path": exec_result.get("input_path"),
        "input_sha256": exec_result.get("input_sha256"),
        "output_path": exec_result.get("output_path"),
        "output_sha256": exec_result.get("output_sha256"),
        "width": exec_result.get("width"),
        "height": exec_result.get("height"),
        "device_used": exec_result.get("device_used"),
        "device_requested": exec_result.get("device_requested"),
        "wall_s": exec_result.get("wall_s"),
        "model_id": exec_result.get("model_id"),
        "model_sha256": exec_result.get("model_sha256"),
        "job_id": exec_result.get("job_id"),
        "note": req.get("note"),
        "source_asset_hint": req.get("source_asset_hint"),
        "paste_this_json_to_grok_chat": True,
        "final_acceptance": False,
        "e3_speed_claim": False,
        "quality_qualified": False,
        "exec": exec_result,
    }
    out_json = outbox / f"{req['request_id']}_result.json"
    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # move request to done
    dest = done_dir / req_path.name
    if dest.exists():
        dest.unlink()
    req_path.replace(dest)
    return result
