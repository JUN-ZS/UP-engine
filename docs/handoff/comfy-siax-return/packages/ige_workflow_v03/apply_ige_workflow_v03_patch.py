#!/usr/bin/env python3
"""Apply a conservative, graph-validated v0.3 optimization patch to the supplied ComfyUI workflow.

This script deliberately does NOT invent missing IGE node inputs or promote provisional geometry.
It updates the model metadata, fixes repeatability, adds a same-stitcher B branch for diagnosis,
ensures the logic-map preview is executed, and exposes IGE diagnostic JSON through ShowText nodes.

Usage:
  python apply_ige_workflow_v03_patch.py input_workflow.json output_workflow_v03.json
  python apply_ige_workflow_v03_patch.py --self-test
"""
from __future__ import annotations
import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

EXPECTED = {
    31: "VAELoader", 36: "TTP_Image_Tile_Batch", 70: "RandomNoise",
    127: "TTP_Image_Assy", 233: "LoadImage", 245: "Image Comparer (rgthree)",
    300: "IGE_GlobalLogicCompiler", 301: "IGE_TTPSubsetProjector",
    302: "IGE_ApplyLogicGate", 303: "IGE_GlobalReconciler",
    304: "IGE_GlobalAcceptanceAudit", 305: "IGE_IterationFeedback",
    306: "IGE_LogicMapPreview", 308: "IGE_TileNoiseMask", 77: "UNETLoader",
    34: "ImageScaleToTotalPixels", 237: "ImageListToImageBatch",
}


def die(message: str) -> None:
    raise ValueError(message)


def node_map(wf: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for n in wf.get("nodes", []):
        nid = n.get("id")
        if not isinstance(nid, int):
            die(f"Node has invalid id: {nid!r}")
        if nid in out:
            die(f"Duplicate node id: {nid}")
        out[nid] = n
    return out


def require_node(nodes: dict[int, dict[str, Any]], nid: int, typ: str | None = None) -> dict[str, Any]:
    if nid not in nodes:
        die(f"Required node {nid} is missing")
    n = nodes[nid]
    if typ and n.get("type") != typ:
        die(f"Node {nid}: expected type {typ!r}, got {n.get('type')!r}")
    return n


def ensure_slots(n: dict[str, Any], kind: str, count: int, nid: int) -> None:
    slots = n.get(kind, [])
    if len(slots) < count:
        die(f"Node {nid} has {len(slots)} {kind}; needs at least {count}")


def append_output_link(n: dict[str, Any], slot: int, link_id: int) -> None:
    outputs = n.setdefault("outputs", [])
    ensure_slots(n, "outputs", slot + 1, n.get("id", "?"))
    links = outputs[slot].get("links")
    if links is None:
        links = []
        outputs[slot]["links"] = links
    if link_id not in links:
        links.append(link_id)


def connect(wf: dict[str, Any], nodes: dict[int, dict[str, Any]], link_id: int,
            src_id: int, src_slot: int, dst_id: int, dst_slot: int, typ: str) -> None:
    if any(int(l[0]) == link_id for l in wf.get("links", [])):
        die(f"Link id already exists: {link_id}")
    src = require_node(nodes, src_id)
    dst = require_node(nodes, dst_id)
    ensure_slots(src, "outputs", src_slot + 1, src_id)
    ensure_slots(dst, "inputs", dst_slot + 1, dst_id)
    if dst["inputs"][dst_slot].get("link") not in (None, link_id):
        die(f"Destination {dst_id}:{dst_slot} already has link {dst['inputs'][dst_slot].get('link')}")
    dst["inputs"][dst_slot]["link"] = link_id
    append_output_link(src, src_slot, link_id)
    wf.setdefault("links", []).append([link_id, src_id, src_slot, dst_id, dst_slot, typ])


def rewire_link_source(wf: dict[str, Any], nodes: dict[int, dict[str, Any]], link_id: int,
                       new_src_id: int, new_src_slot: int) -> None:
    matches = [l for l in wf.get("links", []) if int(l[0]) == link_id]
    if len(matches) != 1:
        die(f"Expected exactly one existing link {link_id}, found {len(matches)}")
    link = matches[0]
    old_src_id, old_src_slot = int(link[1]), int(link[2])
    old_src = require_node(nodes, old_src_id)
    new_src = require_node(nodes, new_src_id)
    ensure_slots(old_src, "outputs", old_src_slot + 1, old_src_id)
    ensure_slots(new_src, "outputs", new_src_slot + 1, new_src_id)
    old_links = old_src["outputs"][old_src_slot].get("links") or []
    old_src["outputs"][old_src_slot]["links"] = [x for x in old_links if int(x) != link_id]
    link[1], link[2] = new_src_id, new_src_slot
    append_output_link(new_src, new_src_slot, link_id)


def make_ttp_assembly(nid: int, order: int) -> dict[str, Any]:
    return {
        "id": nid, "type": "TTP_Image_Assy", "pos": [2150, 1450], "size": [313, 118],
        "flags": {}, "order": order, "mode": 0,
        "inputs": [
            {"label": "tiles", "name": "tiles", "type": "IMAGE", "link": None},
            {"label": "positions", "name": "positions", "type": "LIST", "link": None},
            {"label": "original_size", "name": "original_size", "type": "TUPLE", "link": None},
            {"label": "grid_size", "name": "grid_size", "type": "TUPLE", "link": None},
            {"label": "padding", "name": "padding", "type": "INT",
             "widget": {"name": "padding"}, "link": None},
        ],
        "outputs": [{"label": "RECONSTRUCTED_IMAGE", "name": "RECONSTRUCTED_IMAGE",
                     "type": "IMAGE", "slot_index": 0, "links": []}],
        "properties": {"Node name for S&R": "TTP_Image_Assy", "widget_ue_connectable": {}},
        "widgets_values": [125], "widgets_values_named": {"padding": 125},
        "title": "B · Same TTP Assembly (Logic Gate only)",
    }


def make_save_image(nid: int, order: int, pos: list[int], prefix: str) -> dict[str, Any]:
    return {
        "id": nid, "type": "SaveImage", "pos": pos, "size": [330, 85], "flags": {},
        "order": order, "mode": 0,
        "inputs": [
            {"label": "images", "name": "images", "type": "IMAGE", "link": None},
            {"label": "filename_prefix", "name": "filename_prefix", "type": "STRING",
             "widget": {"name": "filename_prefix"}, "link": None},
        ],
        "outputs": [
            {"label": "image_urls", "name": "image_urls", "type": "STRING", "links": None},
            {"label": "images", "name": "images", "type": "IMAGE", "links": None},
        ],
        "properties": {"Node name for S&R": "SaveImage", "widget_ue_connectable": {}},
        "widgets_values": [prefix], "widgets_values_named": {"filename_prefix": prefix},
        "title": f"Save · {prefix}",
    }


def make_show_text(nid: int, order: int, pos: list[int], title: str) -> dict[str, Any]:
    # This node type is already present in the supplied workflow's embedded groupNodes metadata.
    return {
        "id": nid, "type": "ShowText|pysssss", "pos": pos, "size": [350, 145], "flags": {},
        "order": order, "mode": 0,
        "inputs": [{"widget": {"name": "text"}, "name": "text", "label": "text",
                    "type": "STRING", "link": None}],
        "outputs": [{"shape": 6, "name": "STRING", "slot_index": 0,
                     "links": None, "label": "STRING", "type": "STRING"}],
        "properties": {"Node name for S&R": "ShowText|pysssss", "widget_ue_connectable": {}},
        "widgets_values": ["", ""], "title": title,
    }


def make_comparer(template: dict[str, Any], nid: int, order: int, pos: list[int], title: str) -> dict[str, Any]:
    n = copy.deepcopy(template)
    n["id"] = nid
    n["pos"] = pos
    n["order"] = order
    n["mode"] = 0
    n["title"] = title
    # Preserve the installed rgthree comparer schema, but clear stale previous-run preview URLs.
    for i in n.get("inputs", []):
        i["link"] = None
    for o in n.get("outputs", []):
        o["links"] = None
    n["widgets_values"] = [[]]
    n["widgets_values_named"] = {"rgthree_comparer": {"images": []}}
    return n


def validate_graph(wf: dict[str, Any]) -> dict[str, Any]:
    nodes = node_map(wf)
    link_ids = [int(l[0]) for l in wf.get("links", [])]
    if len(link_ids) != len(set(link_ids)):
        die("Duplicate link IDs found")
    node_ids = set(nodes)
    for l in wf.get("links", []):
        lid, sid, sslot, did, dslot, _typ = l
        if int(sid) not in node_ids or int(did) not in node_ids:
            die(f"Link {lid} references missing node")
        s, d = nodes[int(sid)], nodes[int(did)]
        ensure_slots(s, "outputs", int(sslot) + 1, int(sid))
        ensure_slots(d, "inputs", int(dslot) + 1, int(did))
        if d["inputs"][int(dslot)].get("link") != lid:
            die(f"Link {lid}: destination input backlink mismatch")
        outlinks = s["outputs"][int(sslot)].get("links") or []
        if lid not in outlinks:
            die(f"Link {lid}: source output backlink mismatch")
    return {"nodes": len(nodes), "links": len(link_ids), "unique_node_ids": True,
            "unique_link_ids": True, "link_backreferences": "PASS"}


def patch(wf: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(wf, dict) or not isinstance(wf.get("nodes"), list) or not isinstance(wf.get("links"), list):
        die("Input is not a ComfyUI workflow JSON with nodes[] and links[]")
    nodes = node_map(wf)
    for nid, typ in EXPECTED.items():
        require_node(nodes, nid, typ)
    # Verify the exact upstream links that this patch depends on.
    links_by_id = {int(l[0]): l for l in wf["links"]}
    for lid in (431, 432, 477, 479, 481, 493, 495, 496, 498, 499, 501, 502, 504, 505, 506):
        if lid not in links_by_id:
            die(f"Expected baseline link {lid} is missing; source workflow revision differs")

    # 1) Resolve duplicated widget metadata without changing the selected assets.
    unet = nodes[77]
    unet.setdefault("widgets_values_named", {})["unet_name"] = unet["widgets_values"][0]
    vae = nodes[31]
    vae.setdefault("widgets_values_named", {})["vae_name"] = vae["widgets_values"][0]
    # Record the chosen baseline explicitly.
    unet["title"] = "UNETLoader · FLUX Dev FP8 baseline (not CC_V1 parity)"

    # 2) Reproducibility: keep the current seed, stop auto-randomizing it between runs.
    noise = nodes[70]
    vals = noise.setdefault("widgets_values", [])
    if len(vals) < 2:
        die("RandomNoise node 70 has an unexpected widget schema")
    seed_before = vals[0]
    vals[1] = "fixed"
    noise.setdefault("widgets_values_named", {})["noise_seed"] = seed_before
    noise["widgets_values_named"]["control_after_generate"] = "fixed"

    # 3) Compare like-for-like resolution: 16MP SIAX canvas vs reconstructed A.
    # Existing comparer node 245 was comparing the original low-res input (node 233) to the 16MP output.
    rewire_link_source(wf, nodes, 431, 34, 0)

    # 4) Add B branch through the SAME TTP assembler used by A.
    new_nodes = [
        make_ttp_assembly(327, 66),
        make_comparer(nodes[245], 328, 67, [2560, 1430], "A vs B · same TTP assembly"),
        make_comparer(nodes[245], 329, 68, [2560, 2140], "B · TTP assembly vs Global Reconciler"),
        make_save_image(330, 69, [2150, 1690], "IGE/B_TTP_GatedTiles"),
        make_save_image(331, 70, [1170, 1930], "IGE/GlobalLogicMap"),
        make_comparer(nodes[245], 340, 79, [2950, 1450], "Source vs B · Global Reconciler"),
        make_comparer(nodes[245], 341, 80, [2950, 2140], "A vs B · Final candidate"),
    ]
    # Surface every decision/report artifact in the workflow UI. The final state is displayed
    # for manual carry-forward; this does not claim automatic disk persistence.
    report_specs = [
        (332, "IGE · Contract report", 300, 3),
        (333, "IGE · Tile subset tasks", 301, 1),
        (334, "IGE · Execution groups", 301, 2),
        (335, "IGE · Noise mask report", 308, 1),
        (336, "IGE · Logic gate report", 302, 1),
        (337, "IGE · Reconcile report", 303, 2),
        (338, "IGE · Global audit report", 304, 0),
        (339, "IGE · Next iteration state (manual carry-forward)", 305, 0),
    ]
    for idx, (nid, title, _src, _slot) in enumerate(report_specs):
        new_nodes.append(make_show_text(nid, 71 + idx, [2150 + (idx % 2) * 390, 2480 + (idx // 2) * 180], title))
    for n in new_nodes:
        if n["id"] in nodes:
            die(f"New node ID already exists: {n['id']}")
        wf["nodes"].append(n)
        nodes[n["id"]] = n

    # B's gated tiles pass through the same TTP_Image_Assy parameters as original A.
    connect(wf, nodes, 507, 302, 0, 327, 0, "IMAGE")
    connect(wf, nodes, 508, 36, 1, 327, 1, "LIST")
    connect(wf, nodes, 509, 36, 2, 327, 2, "TUPLE")
    connect(wf, nodes, 510, 36, 3, 327, 3, "TUPLE")
    connect(wf, nodes, 511, 327, 0, 330, 0, "IMAGE")
    # Three diagnostic comparisons: source-vs-A (existing node 245), A-vs-B with identical
    # TTP assembly, and B's TTP assembly-vs-global reconciliation.
    connect(wf, nodes, 512, 127, 0, 328, 0, "IMAGE")
    connect(wf, nodes, 513, 327, 0, 328, 1, "IMAGE")
    connect(wf, nodes, 514, 327, 0, 329, 0, "IMAGE")
    connect(wf, nodes, 515, 303, 0, 329, 1, "IMAGE")
    # Logic map preview was previously a dead-end output, so it could be skipped by execution.
    connect(wf, nodes, 516, 306, 0, 331, 0, "IMAGE")
    connect(wf, nodes, 525, 34, 0, 340, 0, "IMAGE")
    connect(wf, nodes, 526, 303, 0, 340, 1, "IMAGE")
    connect(wf, nodes, 527, 127, 0, 341, 0, "IMAGE")
    connect(wf, nodes, 528, 303, 0, 341, 1, "IMAGE")
    # Report sinks force evaluation and expose the structured diagnostics in the UI.
    for lid, (nid, _title, src, slot) in zip(range(517, 525), report_specs):
        connect(wf, nodes, lid, src, slot, nid, 0, "STRING")

    wf["last_node_id"] = max(int(wf.get("last_node_id", 0)), 341)
    wf["last_link_id"] = max(int(wf.get("last_link_id", 0)), 528)
    extra = wf.setdefault("extra", {})
    extra["ige_workflow_optimization_v03"] = {
        "version": "0.3-structural-diagnostic-patch",
        "model_baseline": "flux1-dev.safetensors + fp8_e4m3fn_fast",
        "vae": "ae.safetensors (standard FLUX AE candidate; not SHA-parity certified against ae.sft)",
        "seed": seed_before,
        "control_after_generate": "fixed",
        "preserved": [
            "full-image NMKD-Siax upscale", "16MP Lanczos canvas", "TTP 2x3 full-image tiling",
            "TTP positions/original_size/grid_size metadata", "original A sampler/decoder/TTP assembly",
            "IGE B branch and provisional geometry status",
        ],
        "added": [
            "B logic-gated tiles through same TTP_Image_Assy as A",
            "A-vs-B same-stitcher comparison", "B-TTP-vs-GlobalReconciler comparison",
            "source-vs-B final comparison", "A-vs-B final comparison",
            "16MP source-vs-A comparison fix", "executable LogicMapPreview save node",
            "visible contract/subset/mask/gate/reconcile/audit/next-state reports",
        ],
        "not_claimed": [
            "CC_V1 parity", "original ae.sft SHA/tensor parity", "true shared global latent/noise field",
            "geometry guard proven active", "automatic iteration-state persistence",
            "real GPU execution", "formal geometry acceptance",
        ],
        "required_preflight": [
            "All referenced custom nodes are installed and importable",
            "IGE contract embeds Geometry Guard and projector propagates it into TILE_SUBSETS (verify code)",
            "Geometry file coordinates are registered to the 16MP canvas",
            "Noise-mask report confirms intended policy fractions and mask alignment",
            "ShowText|pysssss is installed (it is referenced in the source workflow embedded group metadata)",
        ],
    }
    result = validate_graph(wf)
    result.update({
        "model_metadata_sync": "PASS",
        "seed_fixed_without_changing_seed": seed_before,
        "source_compare_resolution": "16MP source canvas",
        "same_ttp_stitcher_ab_comparison": "WIRED",
        "global_reconciler_effect_comparison": "WIRED",
        "logic_map_preview_execution": "WIRED_TO_SAVEIMAGE",
        "report_sinks": 8,
        "geometry_acceptance": "NOT_RUN",
        "gpu_execution": "NOT_RUN",
    })
    wf["extra"]["ige_workflow_optimization_v03"]["static_validation"] = result
    return wf


def self_test() -> None:
    """Build a graph fixture with expected ids/slots and verify patch invariants."""
    nodes = []
    for nid, typ in EXPECTED.items():
        n={"id":nid,"type":typ,
           "inputs":[{"link":None} for _ in range(32)],
           "outputs":[{"links":[]} for _ in range(32)],
           "widgets_values":[],"widgets_values_named":{}}
        nodes.append(n)
    by={n['id']:n for n in nodes}
    by[70]['widgets_values']=[909424749197426,'randomize']
    by[31]['widgets_values']=['ae.safetensors']
    by[77]['widgets_values']=['flux1-dev.safetensors','fp8_e4m3fn_fast']
    links=[]
    def old(lid,s,ss,d,ds,t):
        links.append([lid,s,ss,d,ds,t])
        by[d]['inputs'][ds]['link']=lid
        by[s]['outputs'][ss]['links'].append(lid)
    old(431,233,0,245,0,'IMAGE')
    old(432,127,0,245,1,'IMAGE')
    sentinel_ids=(477,479,481,493,495,496,498,499,501,502,504,505,506)
    for j,lid in enumerate(sentinel_ids):
        old(lid,34,j,300,j,'STRING')
    wf={"nodes":nodes,"links":links,"last_node_id":315,"last_link_id":506,"extra":{}}
    out=patch(wf)
    assert out['last_node_id']==341 and out['last_link_id']==528
    nm=node_map(out)
    assert nm[77]['widgets_values_named']['unet_name']=='flux1-dev.safetensors'
    assert nm[31]['widgets_values_named']['vae_name']=='ae.safetensors'
    assert nm[70]['widgets_values'][0]==909424749197426 and nm[70]['widgets_values'][1]=='fixed'
    assert any(l[0]==507 and l[1]==302 and l[3]==327 for l in out['links'])
    assert any(l[0]==516 and l[1]==306 and l[3]==331 for l in out['links'])
    assert len([n for n in out['nodes'] if n['type']=='ShowText|pysssss'])==8
    print(json.dumps({"self_test":"PASS","added_nodes":15,"added_links":22,
                      "seed_preserved":909424749197426,"metadata_sync":"PASS"},indent=2))


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", nargs="?", help="Original exported ComfyUI workflow JSON")
    ap.add_argument("output", nargs="?", help="Patched output JSON path")
    ap.add_argument("--self-test", action="store_true")
    args=ap.parse_args()
    try:
        if args.self_test:
            self_test(); return 0
        if not args.input or not args.output:
            ap.error("input and output are required unless --self-test is used")
        src=Path(args.input); dst=Path(args.output)
        wf=json.loads(src.read_text(encoding="utf-8"))
        out=patch(wf)
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"output":str(dst),"bytes":dst.stat().st_size,
                          "validation":out['extra']['ige_workflow_optimization_v03']['static_validation']},
                         ensure_ascii=False,indent=2))
        return 0
    except Exception as e:
        print(f"ERROR: {e}",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
