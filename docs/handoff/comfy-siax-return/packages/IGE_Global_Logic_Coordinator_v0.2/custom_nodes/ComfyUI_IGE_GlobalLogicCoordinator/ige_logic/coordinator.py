from __future__ import annotations
import json
from pathlib import Path
from .core import sha256_json, make_iteration_feedback


def write_iteration_state(contract: dict, audit_report: dict, output_path: str | Path,
                          operator_feedback: dict | None = None) -> dict:
    state=make_iteration_feedback(contract,audit_report,operator_feedback)
    Path(output_path).write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    return state


def summarize_subset_compatibility(subsets: dict) -> dict:
    """Group tiles that share their effective rule and local-instruction profile."""
    groups={}
    for entry in subsets['tiles']:
        task=entry['task']
        key=sha256_json({"subset_signature":task["subset_signature"],"local_prompt":task.get("local_prompt","")})[:16]
        groups.setdefault(key,{"profile":task["action_counts"],"rule_ids":task["rule_ids_inherited"],
                              "local_prompt":task.get("local_prompt",""),"tile_ids":[]})["tile_ids"].append(task['tile_id'])
    compatible=(len(groups)==1)
    return {
      "schema_version":"ige-subset-compatibility/0.1",
      "groups":[{"subset_signature":k,**v} for k,v in groups.items()],
      "group_count":len(groups),
      "single_shared_sampler_batch_compatible":compatible,
      "limitation":"Stock SamplerCustomAdvanced uses one shared conditioning object for its latent batch. Different per-subset text conditioning requires separate subset executions or a verified batch-conditioning adapter.",
      "global_rule_inheritance":"Every subset retains the same parent contract_id and rules_digest."
    }

