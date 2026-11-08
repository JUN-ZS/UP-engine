from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
from typing import Any


def _link_index(workflow: dict[str, Any]) -> tuple[dict[int, list[Any]], dict[int, dict[str, Any]]]:
    links = {int(item[0]): item for item in workflow.get("links", [])}
    nodes = {int(node["id"]): node for node in workflow.get("nodes", [])}
    return links, nodes


def _upstream_ids(start_id: int, links: dict[int, list[Any]], nodes: dict[int, dict[str, Any]]) -> set[int]:
    seen: set[int] = set()
    todo = [int(start_id)]
    while todo:
        current = todo.pop()
        if current in seen or current not in nodes:
            continue
        seen.add(current)
        for slot in nodes[current].get("inputs", []):
            link_id = slot.get("link")
            if link_id is None:
                continue
            link = links.get(int(link_id))
            if link:
                todo.append(int(link[1]))
    return seen


def analyze_workflow(workflow: dict[str, Any], max_sampler_batch: int = 1) -> dict[str, Any]:
    """Static graph inspection. Tile counts are explicitly configuration-derived."""
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise ValueError("Expected ComfyUI UI workflow JSON")
    links, nodes = _link_index(workflow)
    samplers = [n for n in nodes.values() if n.get("type") == "SamplerCustomAdvanced"]
    if not samplers:
        raise ValueError("No SamplerCustomAdvanced nodes found")

    sampler_reports = []
    for sampler in samplers:
        sampler_id = int(sampler["id"])
        latent_slots = [s for s in sampler.get("inputs", []) if s.get("name") == "latent_image"]
        if len(latent_slots) != 1:
            raise ValueError(f"Sampler {sampler_id} must have one latent_image input")
        link_id = latent_slots[0].get("link")
        if link_id is None or int(link_id) not in links:
            raise ValueError(f"Sampler {sampler_id} latent_image link is missing")
        link = links[int(link_id)]
        immediate_source = nodes.get(int(link[1]), {})
        ancestors = _upstream_ids(int(link[1]), links, nodes)
        ttp_nodes = [nodes[nid] for nid in ancestors if nodes[nid].get("type") == "TTP_Image_Tile_Batch"]
        ttp_reports = []
        for ttp in ttp_nodes:
            grid_node_ids = set()
            for input_slot in ttp.get("inputs", []):
                if input_slot.get("name") not in ("tile_width", "tile_height"):
                    continue
                tid = input_slot.get("link")
                if tid is not None and int(tid) in links:
                    grid_node_ids.add(int(links[int(tid)][1]))
            grid_nodes = [nodes[nid] for nid in grid_node_ids if nodes[nid].get("type") == "TTP_Tile_image_size"]
            grid = None
            count = None
            if grid_nodes:
                values = grid_nodes[0].get("widgets_values", [])
                if len(values) >= 2:
                    try:
                        grid = [int(values[0]), int(values[1])]
                        if grid[0] > 0 and grid[1] > 0:
                            count = grid[0] * grid[1]
                    except (TypeError, ValueError):
                        grid = None
            ttp_reports.append({
                "node_id": int(ttp["id"]),
                "configured_tile_grid": grid,
                "configuration_derived_tile_count": count,
                "count_is_runtime_observed": False,
            })
        sampler_reports.append({
            "sampler_id": sampler_id,
            "sampler_title": sampler.get("title"),
            "latent_source_node_id": int(link[1]),
            "latent_source_type": immediate_source.get("type"),
            "execution_gate_present": immediate_source.get("type") == "IGE_ExecutionAuthorizationGate",
            "upstream_ttp_batches": ttp_reports,
            "contains_ttp_image_batch_upstream": bool(ttp_nodes),
            "static_batch_warning": bool(ttp_nodes and any(x["configuration_derived_tile_count"] not in (None, 1) for x in ttp_reports)),
            "runtime_latent_batch_size": None,
        })

    return {
        "schema_version": "ige-comfy-resource-preflight/0.1",
        "sampler_count": len(sampler_reports),
        "max_sampler_batch_policy": int(max_sampler_batch),
        "samplers": sampler_reports,
        "non_claims": [
            "Tile count is inferred from node configuration; it is not observed runtime tensor metadata.",
            "Static graph inspection does not estimate peak VRAM/RAM for Flux, T5, VAE or custom nodes.",
            "A passing resource preflight is not proof of OOM-free execution.",
            "This tool never submits a ComfyUI prompt or starts inference.",
        ],
    }


def _probe_ram_available_mb() -> int | None:
    try:
        import psutil  # type: ignore
        return int(psutil.virtual_memory().available // (1024 * 1024))
    except Exception:
        pass
    if os.name == "nt":
        try:
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
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullAvailPhys // (1024 * 1024))
        except Exception:
            return None
    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int((pages * page_size) // (1024 * 1024))
    except Exception:
        return None


def probe_runtime_resources() -> dict[str, Any]:
    ram_available = _probe_ram_available_mb()
    vram_free = None
    vram_total = None
    cuda_available = False
    torch_version = None
    try:
        import torch  # type: ignore
        torch_version = str(torch.__version__)
        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            free_bytes, total_bytes = torch.cuda.mem_get_info()
            vram_free = int(free_bytes // (1024 * 1024))
            vram_total = int(total_bytes // (1024 * 1024))
    except Exception:
        pass
    return {
        "cuda_available": cuda_available,
        "torch_version": torch_version,
        "vram_free_mb": vram_free,
        "vram_total_mb": vram_total,
        "ram_available_mb": ram_available,
    }


def evaluate_preflight(
    graph_report: dict[str, Any],
    resources: dict[str, Any],
    *,
    min_free_vram_mb: int = 2048,
    min_free_ram_mb: int = 8192,
    max_sampler_batch: int = 1,
    execution_allowed: bool = False,
    operator_authorized: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not all(item.get("execution_gate_present") for item in graph_report.get("samplers", [])):
        reasons.append("SAMPLER_PATH_NOT_GEOMETRY_GATED")
    if any(item.get("static_batch_warning") for item in graph_report.get("samplers", [])):
        reasons.append("MULTI_TILE_BATCH_NOT_SERIALIZED")
    if graph_report.get("max_sampler_batch_policy") != int(max_sampler_batch):
        reasons.append("GRAPH_BATCH_POLICY_MISMATCH")

    vram = resources.get("vram_free_mb")
    ram = resources.get("ram_available_mb")
    if not resources.get("cuda_available") or vram is None:
        reasons.append("CUDA_VRAM_PROBE_UNAVAILABLE")
    elif int(vram) < int(min_free_vram_mb):
        reasons.append("FREE_VRAM_BELOW_RESERVE")
    if ram is None:
        reasons.append("SYSTEM_RAM_PROBE_UNAVAILABLE")
    elif int(ram) < int(min_free_ram_mb):
        reasons.append("FREE_RAM_BELOW_RESERVE")
    if not execution_allowed:
        reasons.append("EXECUTION_NOT_AUTHORIZED")
    if not operator_authorized:
        reasons.append("OPERATOR_NOT_AUTHORIZED")

    return {
        "schema_version": "ige-comfy-resource-decision/0.1",
        "status": "BLOCKED" if reasons else "PREFLIGHT_PASS_NOT_SUBMITTED",
        "reasons": reasons,
        "resources": resources,
        "thresholds": {
            "min_free_vram_mb": int(min_free_vram_mb),
            "min_free_ram_mb": int(min_free_ram_mb),
            "max_sampler_batch": int(max_sampler_batch),
        },
        "execution_allowed": bool(execution_allowed),
        "operator_authorized": bool(operator_authorized),
        "queue_submission": False,
        "policy_note": "VRAM/RAM values are admission reserves, not an empirically fitted peak-memory model.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only ComfyUI graph and resource preflight; never queues a prompt.")
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--min-free-vram-mb", type=int, default=2048)
    parser.add_argument("--min-free-ram-mb", type=int, default=8192)
    parser.add_argument("--max-sampler-batch", type=int, default=1)
    parser.add_argument("--execution-allowed", action="store_true", help="Explicit permission input; still does not submit")
    parser.add_argument("--operator-authorized", action="store_true", help="Explicit operator authorization input; still does not submit")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    workflow = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
    graph = analyze_workflow(workflow, max_sampler_batch=args.max_sampler_batch)
    resources = probe_runtime_resources()
    decision = evaluate_preflight(
        graph, resources,
        min_free_vram_mb=args.min_free_vram_mb,
        min_free_ram_mb=args.min_free_ram_mb,
        max_sampler_batch=args.max_sampler_batch,
        execution_allowed=args.execution_allowed,
        operator_authorized=args.operator_authorized,
    )
    report = {"graph": graph, "decision": decision}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    return 0 if decision["status"] != "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
