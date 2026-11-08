from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
from typing import Any


LIST_SPLITTER_TYPES = {
    "easy imageBatchToImageList",
    "ImageBatchToImageList",
}


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


def _input_source(node: dict[str, Any], input_name: str, links: dict[int, list[Any]]) -> int | None:
    slots = [slot for slot in node.get("inputs", []) if slot.get("name") == input_name]
    if len(slots) != 1 or slots[0].get("link") is None:
        return None
    link = links.get(int(slots[0]["link"]))
    return int(link[1]) if link else None


def _output_targets(node: dict[str, Any], output_name: str, links: dict[int, list[Any]]) -> list[int]:
    slots = [slot for slot in node.get("outputs", []) if slot.get("name") == output_name]
    if len(slots) != 1:
        return []
    targets = []
    for link_id in slots[0].get("links") or []:
        link = links.get(int(link_id))
        if link:
            targets.append(int(link[3]))
    return targets


def _tile_grid_report(ttp: dict[str, Any], links: dict[int, list[Any]], nodes: dict[int, dict[str, Any]]) -> dict[str, Any]:
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
    if len(grid_nodes) == 1:
        values = grid_nodes[0].get("widgets_values", [])
        if len(values) >= 2:
            try:
                grid = [int(values[0]), int(values[1])]
                if grid[0] > 0 and grid[1] > 0:
                    count = grid[0] * grid[1]
            except (TypeError, ValueError):
                grid = None
    return {
        "node_id": int(ttp["id"]),
        "configured_tile_grid": grid,
        "configuration_derived_tile_count": count,
        "count_is_runtime_observed": False,
    }


def _inspect_sampler_path(
    sampler: dict[str, Any],
    links: dict[int, list[Any]],
    nodes: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    sampler_id = int(sampler["id"])
    latent_source_id = _input_source(sampler, "latent_image", links)
    if latent_source_id is None:
        raise ValueError(f"Sampler {sampler_id} latent_image link is missing")

    latent_ancestors = _upstream_ids(latent_source_id, links, nodes)
    vae_nodes = [nodes[nid] for nid in latent_ancestors if nodes[nid].get("type") == "VAEEncode"]
    ttp_nodes = [nodes[nid] for nid in latent_ancestors if nodes[nid].get("type") == "TTP_Image_Tile_Batch"]

    vae_paths = []
    all_splitters = set()
    for vae in vae_nodes:
        pixel_source_id = _input_source(vae, "pixels", links)
        pixel_ancestors = _upstream_ids(pixel_source_id, links, nodes) if pixel_source_id is not None else set()
        splitters = [
            nodes[nid] for nid in pixel_ancestors
            if nodes[nid].get("type") in LIST_SPLITTER_TYPES
        ]
        ttp_before_vae = [
            nodes[nid] for nid in pixel_ancestors
            if nodes[nid].get("type") == "TTP_Image_Tile_Batch"
        ]
        all_splitters.update(int(n["id"]) for n in splitters)
        vae_paths.append({
            "vae_node_id": int(vae["id"]),
            "pixel_source_node_id": pixel_source_id,
            "list_splitter_nodes": [
                {"node_id": int(n["id"]), "type": n.get("type")}
                for n in splitters
            ],
            "upstream_ttp_nodes": [int(n["id"]) for n in ttp_before_vae],
            "split_before_vae": bool(splitters and ttp_before_vae),
            "split_semantics": (
                "ComfyUI per-item list mapping candidate"
                if splitters and ttp_before_vae else "not proven by static node types"
            ),
        })

    ttp_reports = [_tile_grid_report(node, links, nodes) for node in ttp_nodes]
    configured_counts = [
        row["configuration_derived_tile_count"]
        for row in ttp_reports
        if row["configuration_derived_tile_count"] is not None
    ]
    tile_count = max(configured_counts) if configured_counts else None
    split_before_vae = bool(vae_paths) and all(path["split_before_vae"] for path in vae_paths)

    barrier_targets = _output_targets(sampler, "output", links)
    barriers = [nodes[node_id] for node_id in barrier_targets if node_id in nodes and nodes[node_id].get("type") == "IGE_LatentMemoryBarrier"]
    barrier = barriers[0] if len(barriers) == 1 else None
    barrier_values = (barrier or {}).get("widgets_values") or []
    barrier_release_enabled = barrier_values[:3] == [True, True, True]
    barrier_decoder_targets = _output_targets(barrier, "LATENT", links) if barrier else []
    decoder_targets = [
        node_id for node_id in barrier_decoder_targets
        if node_id in nodes and nodes[node_id].get("type") == "VAEDecodeTiled"
    ]

    return {
        "sampler_id": sampler_id,
        "sampler_title": sampler.get("title"),
        "latent_source_node_id": latent_source_id,
        "latent_source_type": nodes.get(latent_source_id, {}).get("type"),
        "execution_gate_present": nodes.get(latent_source_id, {}).get("type") == "IGE_ExecutionAuthorizationGate",
        "upstream_vae_encode_nodes": [int(n["id"]) for n in vae_nodes],
        "vae_input_paths": vae_paths,
        "upstream_ttp_batches": ttp_reports,
        "contains_ttp_image_batch_upstream": bool(ttp_nodes),
        "configuration_derived_tile_count": tile_count,
        "list_split_before_vae": split_before_vae,
        "list_splitter_node_ids": sorted(all_splitters),
        "static_batch_warning": bool(tile_count and tile_count > 1 and not split_before_vae),
        "runtime_latent_batch_size": None,
        "execution_semantics_evidence": (
            "candidate_sequential_map"
            if tile_count and tile_count > 1 and split_before_vae
            else "not_established"
        ),
        "memory_barrier_present": barrier is not None,
        "memory_barrier_node_id": int(barrier["id"]) if barrier else None,
        "memory_barrier_releases_models_and_cache": bool(barrier and barrier_release_enabled),
        "vae_decode_node_ids": decoder_targets,
    }


def analyze_workflow(workflow: dict[str, Any], max_sampler_batch: int = 1) -> dict[str, Any]:
    """Static graph inspection, including explicit batch-to-list-before-VAE detection.

    The v03 workflow uses easy imageBatchToImageList before VAEEncode. That node
    declares OUTPUT_IS_LIST=(True,) in its upstream implementation, so ComfyUI's
    list scheduler is expected to map the downstream VAEEncode/Sampler calls per
    list item. This is a static candidate, not a measurement of runtime tensors.
    """
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise ValueError("Expected ComfyUI UI workflow JSON")
    links, nodes = _link_index(workflow)
    samplers = [n for n in nodes.values() if n.get("type") == "SamplerCustomAdvanced"]
    if not samplers:
        raise ValueError("No SamplerCustomAdvanced nodes found")

    sampler_reports = [_inspect_sampler_path(sampler, links, nodes) for sampler in samplers]
    return {
        "schema_version": "ige-comfy-resource-preflight/0.2",
        "sampler_count": len(sampler_reports),
        "max_sampler_batch_policy": int(max_sampler_batch),
        "samplers": sampler_reports,
        "non_claims": [
            "TTP tile counts are inferred from configured widgets; they are not runtime-observed counts.",
            "A recognized list splitter is a static sequential-map candidate, not a runtime proof of one-item latent batches.",
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
        reasons.append("TTP_BATCH_NOT_SPLIT_BEFORE_VAE")
    if any(not item.get("memory_barrier_present") for item in graph_report.get("samplers", [])):
        reasons.append("SAMPLER_MEMORY_BARRIER_MISSING")
    if any(not item.get("memory_barrier_releases_models_and_cache") for item in graph_report.get("samplers", [])):
        reasons.append("MEMORY_BARRIER_RELEASE_POLICY_DISABLED")
    if any(len(item.get("vae_decode_node_ids", [])) != 1 for item in graph_report.get("samplers", [])):
        reasons.append("MEMORY_BARRIER_NOT_CONNECTED_TO_SINGLE_VAE_DECODE")
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
        "schema_version": "ige-comfy-resource-decision/0.2",
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
