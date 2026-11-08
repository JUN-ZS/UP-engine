from __future__ import annotations

import json
import re
from typing import Any


class ExecutionGateError(RuntimeError):
    """Raised when a Comfy sampler lacks a contract-bound human authorization."""


def validate_execution_authorization(
    contract_bundle: dict[str, Any],
    authorization_json: str,
    branch_id: str,
) -> dict[str, Any]:
    """Fail-closed gate. This validates an explicit approval record; it never creates one.

    The approval record is an operator-consent artifact, not a cryptographic signature.
    It must be generated/reviewed outside this node and bound to the exact compiled
    contract, source digest, policy revision and sampler branch.
    """
    if not isinstance(contract_bundle, dict):
        raise ExecutionGateError("BLOCK: missing IGE contract bundle")
    contract = contract_bundle.get("contract")
    if not isinstance(contract, dict):
        raise ExecutionGateError("BLOCK: contract bundle has no compiled contract")

    if contract.get("schema_version") != "ige-global-logic-contract/0.1":
        raise ExecutionGateError("BLOCK: unsupported or missing IGE contract schema")

    canvas = contract.get("canvas")
    shape = contract_bundle.get("source_shape")
    if not isinstance(canvas, dict) or not isinstance(shape, (list, tuple)) or len(shape) != 2:
        raise ExecutionGateError("BLOCK: source canvas metadata is incomplete")
    try:
        source_h, source_w = int(shape[0]), int(shape[1])
        canvas_w, canvas_h = int(canvas["width"]), int(canvas["height"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ExecutionGateError("BLOCK: invalid source canvas metadata") from exc
    if source_w != canvas_w or source_h != canvas_h:
        raise ExecutionGateError(
            f"BLOCK: contract canvas {canvas_w}x{canvas_h} != compiled source {source_w}x{source_h}"
        )

    source_sha = contract_bundle.get("source_hash")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", source_sha):
        raise ExecutionGateError("BLOCK: source image SHA256 is missing or invalid")
    if contract.get("source_sha256") != source_sha:
        raise ExecutionGateError("BLOCK: contract source SHA does not match compiler bundle")

    if contract.get("geometry_status") != "operator_confirmed":
        raise ExecutionGateError("BLOCK: geometry is not operator_confirmed")
    if contract.get("source_alignment_status") != "operator_confirmed":
        raise ExecutionGateError("BLOCK: source-to-geometry registration is not operator_confirmed")

    try:
        approval = json.loads(authorization_json or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise ExecutionGateError("BLOCK: authorization_json is not valid JSON") from exc
    if not isinstance(approval, dict):
        raise ExecutionGateError("BLOCK: authorization_json must be a JSON object")
    if approval.get("schema_version") != "ige-comfy-execution-authorization/0.1":
        raise ExecutionGateError("BLOCK: explicit execution authorization is absent")

    bindings = {
        "contract_id": contract.get("contract_id"),
        "source_sha256": source_sha,
        "policy_id": contract.get("policy_id"),
        "policy_revision": contract.get("policy_revision"),
        "geometry_status": "operator_confirmed",
        "source_alignment_status": "operator_confirmed",
    }
    for key, expected in bindings.items():
        if expected is None or approval.get(key) != expected:
            raise ExecutionGateError(f"BLOCK: authorization binding mismatch for {key}")

    if approval.get("execution_allowed") is not True:
        raise ExecutionGateError("BLOCK: execution_allowed is not true")
    if approval.get("operator_authorized") is not True:
        raise ExecutionGateError("BLOCK: explicit operator authorization is absent")
    if approval.get("workflow_status") != "ACCEPTED":
        raise ExecutionGateError("BLOCK: workflow is not ACCEPTED")
    if approval.get("geometry_acceptance_status") != "ACCEPTED":
        raise ExecutionGateError("BLOCK: geometry acceptance is not ACCEPTED")
    if not str(approval.get("approval_reference", "")).strip():
        raise ExecutionGateError("BLOCK: approval_reference is required")

    branches = approval.get("authorized_branches")
    if not isinstance(branches, list) or branch_id not in branches:
        raise ExecutionGateError(f"BLOCK: sampler branch {branch_id!r} is not authorized")

    return {
        "schema_version": "ige-comfy-execution-gate-report/0.1",
        "status": "AUTHORIZED",
        "contract_id": contract["contract_id"],
        "source_sha256": source_sha,
        "policy_id": contract["policy_id"],
        "policy_revision": contract["policy_revision"],
        "branch_id": branch_id,
        "execution_allowed": True,
        "operator_authorized": True,
        "approval_reference": approval["approval_reference"],
        "non_claims": [
            "This approval record is not cryptographically signed.",
            "The gate does not prove cross-tile semantic continuity.",
            "The gate does not estimate or guarantee GPU memory safety.",
        ],
    }
