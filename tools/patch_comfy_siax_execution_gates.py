from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


GATE_TYPE = "IGE_ExecutionAuthorizationGate"
SAMPLER_TYPE = "SamplerCustomAdvanced"
COMPILER_TYPE = "IGE_GlobalLogicCompiler"


def _link_map(workflow: dict[str, Any]) -> dict[int, list[Any]]:
    return {int(link[0]): link for link in workflow.get("links", [])}


def patch_workflow(workflow: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Insert one contract-bound authorization gate before every sampler latent input.

    The original workflow is copied, never mutated. The gate defaults to an empty
    authorization JSON, so the resulting workflow is intentionally BLOCKED.
    """
    if not isinstance(workflow, dict) or not isinstance(workflow.get("nodes"), list):
        raise ValueError("Expected a ComfyUI UI workflow JSON with a nodes array")
    if not isinstance(workflow.get("links"), list):
        raise ValueError("Expected a ComfyUI UI workflow JSON with a links array")

    result = copy.deepcopy(workflow)
    nodes = result["nodes"]
    links = result["links"]
    node_by_id = {int(node["id"]): node for node in nodes}
    compilers = [node for node in nodes if node.get("type") == COMPILER_TYPE]
    if len(compilers) != 1:
        raise ValueError(f"Expected exactly one {COMPILER_TYPE}, found {len(compilers)}")
    compiler = compilers[0]
    compiler_id = int(compiler["id"])
    if len(compiler.get("outputs", [])) < 1:
        raise ValueError("GlobalLogicCompiler has no GLOBAL_CONTRACT output")
    if compiler["outputs"][0].get("type") != "IGE_CONTRACT":
        raise ValueError("GlobalLogicCompiler output 0 is not IGE_CONTRACT")

    by_link = _link_map(result)
    next_node_id = max(
        int(result.get("last_node_id", 0)),
        max(node_by_id.keys(), default=0),
    ) + 1
    next_link_id = max(
        int(result.get("last_link_id", 0)),
        max(by_link.keys(), default=0),
    ) + 1
    next_order = max((int(n.get("order", 0)) for n in nodes), default=0) + 1

    samplers = [node for node in nodes if node.get("type") == SAMPLER_TYPE]
    if not samplers:
        raise ValueError("No SamplerCustomAdvanced nodes found")
    patched = []
    already_gated = []

    for sampler in samplers:
        sampler_id = int(sampler["id"])
        inputs = sampler.get("inputs", [])
        latent_slots = [i for i, slot in enumerate(inputs) if slot.get("name") == "latent_image"]
        if len(latent_slots) != 1:
            raise ValueError(f"Sampler {sampler_id} must have exactly one latent_image input")
        latent_slot = latent_slots[0]
        old_link_id = inputs[latent_slot].get("link")
        if old_link_id is None:
            raise ValueError(f"Sampler {sampler_id} has no connected latent_image input")
        old_link_id = int(old_link_id)
        if old_link_id not in by_link:
            raise ValueError(f"Sampler {sampler_id} references missing latent link {old_link_id}")
        old_link = by_link[old_link_id]
        source_id = int(old_link[1])
        if node_by_id[source_id].get("type") == GATE_TYPE:
            already_gated.append(sampler_id)
            continue

        gate_id = next_node_id
        contract_link_id = next_link_id
        output_link_id = next_link_id + 1
        next_node_id += 1
        next_link_id += 2

        title = str(sampler.get("title") or "")
        if "Candidate B" in title or sampler_id == 310:
            branch_id = "candidate_B"
        elif sampler_id == 67:
            branch_id = "baseline_A"
        else:
            branch_id = f"sampler_{sampler_id}"

        # Retarget the original latent link from sampler -> gate; source output stays intact.
        old_link[3] = gate_id
        old_link[4] = 1
        old_link[5] = "LATENT"

        sampler_pos = sampler.get("pos", [0, 0])
        if isinstance(sampler_pos, dict):
            sx, sy = float(sampler_pos.get("0", 0)), float(sampler_pos.get("1", 0))
        else:
            sx, sy = float(sampler_pos[0]), float(sampler_pos[1])
        gate = {
            "id": gate_id,
            "type": GATE_TYPE,
            "pos": [sx, sy + 190.0],
            "size": [340.0, 150.0],
            "flags": {},
            "order": next_order,
            "mode": 0,
            "inputs": [
                {"name": "global_contract", "type": "IGE_CONTRACT", "link": contract_link_id},
                {"name": "latent", "type": "LATENT", "link": old_link_id},
                {"name": "authorization_json", "type": "STRING", "link": None,
                 "widget": {"name": "authorization_json"}},
                {"name": "branch_id", "type": "STRING", "link": None,
                 "widget": {"name": "branch_id"}},
            ],
            "outputs": [
                {"name": "AUTHORIZED_LATENT", "type": "LATENT", "links": [output_link_id], "slot_index": 0},
                {"name": "EXECUTION_GATE_REPORT_JSON", "type": "STRING", "links": [], "slot_index": 1},
            ],
            "properties": {"Node name for S&R": GATE_TYPE},
            "widgets_values": ["{}", branch_id],
            "title": f"IGE · Execution Gate · {branch_id}",
        }
        nodes.append(gate)
        node_by_id[gate_id] = gate
        links.append([contract_link_id, compiler_id, 0, gate_id, 0, "IGE_CONTRACT"])
        links.append([output_link_id, gate_id, 0, sampler_id, latent_slot, "LATENT"])
        inputs[latent_slot]["link"] = output_link_id

        compiler_links = compiler["outputs"][0].setdefault("links", [])
        if compiler_links is None:
            compiler_links = []
            compiler["outputs"][0]["links"] = compiler_links
        compiler_links.append(contract_link_id)

        patched.append({
            "sampler_id": sampler_id,
            "gate_node_id": gate_id,
            "branch_id": branch_id,
            "original_latent_link_id": old_link_id,
            "contract_link_id": contract_link_id,
            "gated_latent_link_id": output_link_id,
        })
        next_order += 1

    result["last_node_id"] = max(int(result.get("last_node_id", 0)), next_node_id - 1)
    result["last_link_id"] = max(int(result.get("last_link_id", 0)), next_link_id - 1)
    extra = result.setdefault("extra", {})
    extra["ige_execution_gate_patch"] = {
        "schema_version": "ige-comfy-execution-gate-patch/0.1",
        "status": "GATED_FAIL_CLOSED",
        "compiler_node_id": compiler_id,
        "patched_samplers": patched,
        "already_gated_samplers": already_gated,
        "authorization_widget_default": "{}",
        "execution_allowed": False,
        "note": "No sampler can execute without a contract-bound human approval record.",
    }
    return result, extra["ige_execution_gate_patch"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Add IGE fail-closed execution gates before ComfyUI samplers.")
    parser.add_argument("--input", required=True, help="Original ComfyUI UI workflow JSON")
    parser.add_argument("--output", required=True, help="New workflow JSON path; input is never overwritten")
    args = parser.parse_args()
    source = Path(args.input)
    target = Path(args.output)
    workflow = json.loads(source.read_text(encoding="utf-8"))
    patched, report = patch_workflow(workflow)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(patched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(target), **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
