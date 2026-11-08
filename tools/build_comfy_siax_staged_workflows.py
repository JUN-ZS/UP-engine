from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


SOURCE_NODE_ID = 34
SOURCE_SAVE_NODE_ID = 128
REMOVE_FOR_STAGE2 = {233, 244, 133, 134}
REMOVE_UNORDERED_PURGE_NODE_ID = 262


def _nodes(workflow: dict[str, Any]) -> dict[int, dict[str, Any]]:
    result = {int(node["id"]): node for node in workflow.get("nodes", [])}
    if len(result) != len(workflow.get("nodes", [])):
        raise ValueError("Duplicate node IDs in workflow")
    return result


def _links(workflow: dict[str, Any]) -> dict[int, list[Any]]:
    result = {int(link[0]): link for link in workflow.get("links", [])}
    if len(result) != len(workflow.get("links", [])):
        raise ValueError("Duplicate link IDs in workflow")
    return result


def _input_link(node: dict[str, Any], input_name: str) -> int | None:
    slots = [slot for slot in node.get("inputs", []) if slot.get("name") == input_name]
    if len(slots) != 1:
        raise ValueError(f"Node {node.get('id')} must have exactly one input named {input_name}")
    link_id = slots[0].get("link")
    return int(link_id) if link_id is not None else None


def _ancestors(node_id: int, node_map: dict[int, dict[str, Any]], link_map: dict[int, list[Any]]) -> set[int]:
    seen: set[int] = set()
    todo = [int(node_id)]
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        if current not in node_map:
            raise ValueError(f"Graph references missing node {current}")
        seen.add(current)
        for slot in node_map[current].get("inputs", []):
            link_id = slot.get("link")
            if link_id is not None:
                link = link_map.get(int(link_id))
                if link is None:
                    raise ValueError(f"Node {current} references missing link {link_id}")
                todo.append(int(link[1]))
    seen.remove(int(node_id))
    return seen


def _validate_links(workflow: dict[str, Any]) -> None:
    node_map = _nodes(workflow)
    link_map = _links(workflow)
    for link_id, link in link_map.items():
        _, source_id, source_slot, target_id, target_slot, _ = link
        if int(source_id) not in node_map or int(target_id) not in node_map:
            raise ValueError(f"Link {link_id} references a missing node")
        source = node_map[int(source_id)]
        target = node_map[int(target_id)]
        if not 0 <= int(source_slot) < len(source.get("outputs", [])):
            raise ValueError(f"Link {link_id} has invalid source slot")
        if not 0 <= int(target_slot) < len(target.get("inputs", [])):
            raise ValueError(f"Link {link_id} has invalid target slot")
        output_links = source["outputs"][int(source_slot)].get("links") or []
        if int(link_id) not in [int(x) for x in output_links]:
            raise ValueError(f"Link {link_id} missing reverse reference on source node")
        if target["inputs"][int(target_slot)].get("link") != int(link_id):
            raise ValueError(f"Link {link_id} missing reverse reference on target node")


def build_staged_workflows(workflow: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Split the existing v03 graph into a Siax-only export and a Flux/IGE candidate.

    Stage 1 contains only ancestors of ImageScaleToTotalPixels plus its SaveImage.
    Stage 2 replaces that scaler node in-place with a LoadImage node, preserving
    all existing downstream source links and the fail-closed sampler gates.
    """
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list) or not isinstance(workflow.get("links"), list):
        raise ValueError("Expected a ComfyUI UI workflow JSON with nodes[] and links[]")
    node_map = _nodes(workflow)
    link_map = _links(workflow)
    for node_id, expected_type in {
        34: "ImageScaleToTotalPixels",
        128: "SaveImage",
        233: "LoadImage",
        244: "ImageResizeKJ",
        133: "UpscaleModelLoader",
        134: "ImageUpscaleWithModel",
        300: "IGE_GlobalLogicCompiler",
        36: "TTP_Image_Tile_Batch",
        262: "LayerUtility: PurgeVRAM",
        262: "LayerUtility: PurgeVRAM",
    }.items():
        if node_id not in node_map or node_map[node_id].get("type") != expected_type:
            raise ValueError(f"Expected Node {node_id} type {expected_type}")

    # Stage 1: preserve only the original SIAX → 16MP canvas path and a new terminal save.
    ancestors = _ancestors(SOURCE_NODE_ID, node_map, link_map)
    keep_ids = ancestors | {SOURCE_NODE_ID, SOURCE_SAVE_NODE_ID}
    stage1 = copy.deepcopy(workflow)
    stage1["nodes"] = [copy.deepcopy(n) for n in workflow["nodes"] if int(n["id"]) in keep_ids]
    stage1["links"] = [
        copy.deepcopy(link) for link in workflow["links"]
        if int(link[1]) in keep_ids and int(link[3]) in keep_ids
    ]
    stage1_nodes = _nodes(stage1)
    stage1_links = _links(stage1)
    scaler = stage1_nodes[SOURCE_NODE_ID]
    saver = stage1_nodes[SOURCE_SAVE_NODE_ID]
    image_input = next((slot for slot in saver.get("inputs", []) if slot.get("name") == "images"), None)
    if image_input is None:
        raise ValueError("Existing SaveImage node has no images input")
    next_link_id = max(int(stage1.get("last_link_id", 0)), max(stage1_links, default=0)) + 1
    image_input["link"] = next_link_id
    scaler["outputs"][0]["links"] = [next_link_id]
    stage1["links"].append([next_link_id, SOURCE_NODE_ID, 0, SOURCE_SAVE_NODE_ID, 0, "IMAGE"])
    saver["widgets_values"] = ["IGE/SIAX_STAGE1_CANVAS"]
    if isinstance(saver.get("widgets_values_named"), dict):
        saver["widgets_values_named"]["filename_prefix"] = "IGE/SIAX_STAGE1_CANVAS"
    stage1["last_link_id"] = next_link_id
    stage1["extra"] = copy.deepcopy(stage1.get("extra") or {})
    stage1["extra"]["ige_siax_staging"] = {
        "schema_version": "ige-siax-staging/0.1",
        "stage": "STAGE_1_SIAX_CANVAS_EXPORT",
        "source_node_id": SOURCE_NODE_ID,
        "save_node_id": SOURCE_SAVE_NODE_ID,
        "retained_node_ids": sorted(keep_ids),
        "contains_flux_sampler": False,
        "contains_flux_unet_loader": False,
        "contains_flux_text_encoder": False,
        "execution_allowed": False,
        "note": "Siax-only stage. Inspect the saved image's actual dimensions and SHA before Stage 2.",
    }
    _validate_links(stage1)

    # Stage 2: keep the full IGE graph but change Node 34 into the LoadImage for Stage 1 output.
    stage2 = copy.deepcopy(workflow)
    stage2_nodes = _nodes(stage2)
    old_canvas_node = stage2_nodes[SOURCE_NODE_ID]
    prior_source_links = list(old_canvas_node.get("outputs", [{}])[0].get("links") or [])

    loader = copy.deepcopy(node_map[233])
    loader["id"] = SOURCE_NODE_ID
    loader["pos"] = copy.deepcopy(old_canvas_node.get("pos", loader.get("pos", [0, 0])))
    loader["title"] = "Stage 1 Siax Canvas · choose verified output"
    loader["widgets_values"] = ["COPY_STAGE1_CANVAS_TO_INPUT_AND_SELECT.png", "image"]
    if isinstance(loader.get("widgets_values_named"), dict):
        loader["widgets_values_named"]["image"] = "COPY_STAGE1_CANVAS_TO_INPUT_AND_SELECT.png"
    loader["outputs"][0]["links"] = prior_source_links
    stage2["nodes"] = [
        loader if int(node["id"]) == SOURCE_NODE_ID else copy.deepcopy(node)
        for node in stage2["nodes"]
        if int(node["id"]) not in (REMOVE_FOR_STAGE2 | {REMOVE_UNORDERED_PURGE_NODE_ID})
    ]
    stage2["links"] = [
        copy.deepcopy(link) for link in stage2["links"]
        if int(link[1]) not in (REMOVE_FOR_STAGE2 | {REMOVE_UNORDERED_PURGE_NODE_ID})
        and int(link[3]) not in (REMOVE_FOR_STAGE2 | {REMOVE_UNORDERED_PURGE_NODE_ID})
    ]

    # Replace the unsequenced terminal PurgeVRAM output with explicit post-sampler
    # model-release barriers. Keep each latent alive and pass it to its own VAE decode.
    stage2_node_map = _nodes(stage2)
    stage2_link_map = _links(stage2)
    barrier_specs = [
        (67, 96, 160, 344, "baseline_A"),
        (310, 311, 491, 345, "candidate_B"),
    ]
    next_link_id = max(int(stage2.get("last_link_id", 0)), max(stage2_link_map, default=0)) + 1
    next_order = max((int(n.get("order", 0)) for n in stage2["nodes"]), default=0) + 1
    barrier_ids = []

    for sampler_id, decoder_id, latent_link_id, barrier_id, branch_id in barrier_specs:
        sampler = stage2_node_map.get(sampler_id)
        decoder = stage2_node_map.get(decoder_id)
        old_link = stage2_link_map.get(latent_link_id)
        if not sampler or sampler.get("type") != "SamplerCustomAdvanced":
            raise ValueError(f"Missing sampler node {sampler_id}")
        if not decoder or decoder.get("type") != "VAEDecodeTiled":
            raise ValueError(f"Missing tiled VAE decoder node {decoder_id}")
        if old_link is None or int(old_link[1]) != sampler_id or int(old_link[3]) != decoder_id:
            raise ValueError(
                f"Expected sampler {sampler_id} to feed decoder {decoder_id} through link {latent_link_id}"
            )
        decoder_slots = [
            index for index, slot in enumerate(decoder.get("inputs", []))
            if slot.get("name") == "samples"
        ]
        if len(decoder_slots) != 1:
            raise ValueError(f"Decoder {decoder_id} must have exactly one samples input")
        decoder_slot = decoder_slots[0]
        if decoder["inputs"][decoder_slot].get("link") != latent_link_id:
            raise ValueError(f"Decoder {decoder_id} samples input is not linked by {latent_link_id}")

        new_link_id = next_link_id
        next_link_id += 1
        old_link[3] = barrier_id
        old_link[4] = 0
        old_link[5] = "LATENT"
        decoder["inputs"][decoder_slot]["link"] = new_link_id

        sampler_pos = sampler.get("pos", [0, 0])
        if isinstance(sampler_pos, dict):
            sx = float(sampler_pos.get("0", 0))
            sy = float(sampler_pos.get("1", 0))
        else:
            sx = float(sampler_pos[0])
            sy = float(sampler_pos[1])

        barrier = {
            "id": barrier_id,
            "type": "IGE_LatentMemoryBarrier",
            "pos": [sx + 410.0, sy + 30.0],
            "size": [330.0, 150.0],
            "flags": {},
            "order": next_order,
            "mode": 0,
            "inputs": [
                {"name": "latent", "type": "LATENT", "link": latent_link_id},
                {"name": "release_models", "type": "BOOLEAN", "widget": {"name": "release_models"}, "link": None},
                {"name": "clear_cuda_cache", "type": "BOOLEAN", "widget": {"name": "clear_cuda_cache"}, "link": None},
                {"name": "synchronize", "type": "BOOLEAN", "widget": {"name": "synchronize"}, "link": None},
            ],
            "outputs": [
                {"name": "LATENT", "type": "LATENT", "links": [new_link_id], "slot_index": 0},
                {"name": "MEMORY_REPORT_JSON", "type": "STRING", "links": [], "slot_index": 1},
            ],
            "properties": {"Node name for S&R": "IGE_LatentMemoryBarrier"},
            "widgets_values": [True, True, True],
            "widgets_values_named": {
                "release_models": True,
                "clear_cuda_cache": True,
                "synchronize": True,
            },
            "title": f"IGE · Memory Release Barrier · {branch_id}",
        }
        stage2["nodes"].append(barrier)
        new_link = [new_link_id, barrier_id, 0, decoder_id, decoder_slot, "LATENT"]
        stage2["links"].append(new_link)
        stage2_node_map[barrier_id] = barrier
        stage2_link_map[new_link_id] = new_link
        barrier_ids.append(barrier_id)
        next_order += 1

    # Pruning Node 262 also prunes its outgoing link from Node 67.
    valid_link_ids = set(_links(stage2))
    for node in stage2["nodes"]:
        for output in node.get("outputs", []):
            if output.get("links") is not None:
                output["links"] = [link_id for link_id in output["links"] if int(link_id) in valid_link_ids]

    stage2["last_node_id"] = max(int(stage2.get("last_node_id", 0)), max(_nodes(stage2), default=0))
    stage2["last_link_id"] = max(int(stage2.get("last_link_id", 0)), max(_links(stage2), default=0))
    stage2["extra"] = copy.deepcopy(stage2.get("extra") or {})
    stage2["extra"]["ige_siax_staging"] = {
        "schema_version": "ige-siax-staging/0.1",
        "stage": "STAGE_2_IGE_FLUX_CANDIDATE",
        "load_image_node_id": SOURCE_NODE_ID,
        "geometry_compiler_node_id": 300,
        "ttp_tile_batch_node_id": 36,
        "sampler_node_ids": [
            int(n["id"]) for n in stage2["nodes"] if n.get("type") == "SamplerCustomAdvanced"
        ],
        "requires_external_cpu_geometry_preflight": True,
        "memory_barrier_node_ids": barrier_ids,
        "removed_unordered_terminal_purge_node_id": REMOVE_UNORDERED_PURGE_NODE_ID,
        "release_models_before_vae_decode": True,
        "execution_allowed": False,
        "note": "Do not queue until the exact Stage 1 output has passed CPU geometry preflight and human registration review.",
    }
    _validate_links(stage2)

    report = {
        "schema_version": "ige-siax-staging-build-report/0.1",
        "stage1": {
            "node_count": len(stage1["nodes"]),
            "link_count": len(stage1["links"]),
            "contains_sampler": any(n.get("type") == "SamplerCustomAdvanced" for n in stage1["nodes"]),
            "contains_flux_unet_loader": any(n.get("type") == "UNETLoader" for n in stage1["nodes"]),
            "retained_node_ids": sorted(int(n["id"]) for n in stage1["nodes"]),
        },
        "stage2": {
            "node_count": len(stage2["nodes"]),
            "link_count": len(stage2["links"]),
            "canvas_node_type": _nodes(stage2)[SOURCE_NODE_ID]["type"],
            "sampler_count": len([n for n in stage2["nodes"] if n.get("type") == "SamplerCustomAdvanced"]),
            "removed_siax_preprocess_node_ids": sorted(REMOVE_FOR_STAGE2),
            "removed_unordered_terminal_purge_node_id": REMOVE_UNORDERED_PURGE_NODE_ID,
            "memory_barrier_node_ids": barrier_ids,
            "release_models_before_vae_decode": True,
            "execution_allowed": False,
        },
    }
    return stage1, stage2, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Split the archived Siax/IGE graph into Siax-only and IGE/Flux stages.")
    parser.add_argument("--input", required=True, help="Existing gated ComfyUI UI workflow JSON")
    parser.add_argument("--stage1-output", required=True)
    parser.add_argument("--stage2-output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    workflow = json.loads(Path(args.input).read_text(encoding="utf-8"))
    stage1, stage2, report = build_staged_workflows(workflow)
    for path, payload in (
        (Path(args.stage1_output), stage1),
        (Path(args.stage2_output), stage2),
        (Path(args.report), report),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
