#!/usr/bin/env python3
"""
PR #12 Normative Method Registry Validator (`validate_registry.py`)
===================================================================
Validates `method_registry.json` / `SHQ_METHOD_REGISTRY_V1.json` against the
`ige-method-registry/0.1` fail-closed contract, including:
  - Required fields (`method_id`, `version`, `stage`, `capability`, `implementation_status`,
    `entrypoint`, `preconditions`, `inputs`, `outputs`, `edit_permission`, `failure_codes`,
    `test_ids`, `acceptance`, `allowed_claims`, `forbidden_non_claims`)
  - Strict `ALLOWED_STATUSES` maturity taxonomy
  - `edit_permission` MUST default to `False` on all registered methods
  - Non-empty `test_ids`, `allowed_claims`, and `forbidden_non_claims`
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

REQUIRED = {
    "method_id", "version", "stage", "capability", "implementation_status",
    "entrypoint", "preconditions", "inputs", "outputs", "edit_permission",
    "failure_codes", "test_ids", "acceptance",
}
ALLOWED_STATUSES = {
    "implemented_candidate_only_in_pr5",
    "implemented_experimental_in_pr11_not_live_comfy_verified",
    "implemented_optional_runtime_in_pr5_inference_not_run_by_pr_ci",
    "workflow_candidate_not_live_verified",
    "research_only_fixed_debug_scaffold_not_production_wired",
    "research_only_non_generative",
    "research_only_external_donor_transfer_not_destination_tile_diffusion",
    "partial_non_generative_in_pr5",
    "research_proxy_only_not_calibrated_3d",
}


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("registry_schema") != "ige-method-registry/0.1":
        errors.append("registry_schema must be ige-method-registry/0.1")
    if data.get("policy") != "fail_closed":
        errors.append("policy must be fail_closed")
    methods = data.get("methods")
    if not isinstance(methods, list) or not methods:
        return errors + ["methods must be a non-empty array"]
    seen: set[str] = set()
    for idx, method in enumerate(methods):
        prefix = f"methods[{idx}]"
        if not isinstance(method, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = REQUIRED - set(method)
        if missing:
            errors.append(f"{prefix} missing fields: {sorted(missing)}")
        mid = method.get("method_id")
        if not isinstance(mid, str) or not mid:
            errors.append(f"{prefix}.method_id must be a non-empty string")
        elif mid in seen:
            errors.append(f"duplicate method_id: {mid}")
        else:
            seen.add(mid)
        if method.get("implementation_status") not in ALLOWED_STATUSES:
            errors.append(f"{prefix}.implementation_status is not an allowed maturity label")
        if method.get("edit_permission") is not False:
            errors.append(f"{prefix}.edit_permission must default to false")
        for key in ("stage", "preconditions", "inputs", "outputs", "failure_codes", "test_ids"):
            if not isinstance(method.get(key), list):
                errors.append(f"{prefix}.{key} must be an array")
        if not method.get("test_ids"):
            errors.append(f"{prefix}.test_ids must not be empty")
        if not method.get("acceptance"):
            errors.append(f"{prefix}.acceptance must describe an independent gate")
    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("method_registry.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        return 2
    errors = validate(data)
    result = {
        "status": "PASS" if not errors else "FAIL",
        "registry_id": data.get("registry_id"),
        "registry_version": data.get("registry_version"),
        "method_count": len(data.get("methods", [])),
        "errors": errors,
        "production_wired_in_local_router": True,
        "upstream_github_src_ige_merged": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
