from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

REGISTRY_SCHEMA = "ige-method-registry/0.2"
STAGES = {f"S{i}" for i in range(8)}
MATURITY = {
    "candidate_only", "experimental", "optional_runtime", "workflow_candidate",
    "research_only", "non_generative", "external_donor_research", "partial",
    "documented_only", "proxy_only", "contract_only",
}
RUNNABLE = {"optional_runtime", "non_generative", "partial"}
BLOCKED = {
    "workflow_candidate": "BLOCKED_BACKEND_NOT_VERIFIED",
    "research_only": "BLOCKED_RESEARCH_ONLY",
    "external_donor_research": "BLOCKED_DONOR_RESEARCH_ONLY",
    "documented_only": "BLOCKED_NOT_IMPLEMENTED",
    "proxy_only": "BLOCKED_PROXY_NOT_PHYSICAL_GEOMETRY",
    "contract_only": "BLOCKED_CONTRACT_ONLY",
}
REQUIRED = {
    "method_id", "version", "skill_aliases", "stage", "capability", "maturity",
    "execution_kind", "entrypoint", "preconditions", "inputs", "outputs",
    "requires_human_permission", "edit_permission", "failure_codes",
    "test_ids", "acceptance",
}
S7_GATES = (
    "identity", "pose", "topology", "geometry", "coverage",
    "permission", "protected_region", "provenance", "visual_quality",
)
_SHA = re.compile(r"^[0-9a-f]{64}$", re.I)


class MethodRegistryError(ValueError):
    pass


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_registry_payload(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("registry_schema") != REGISTRY_SCHEMA:
        errors.append(f"registry_schema must be {REGISTRY_SCHEMA}")
    if data.get("policy") != "fail_closed":
        errors.append("policy must be fail_closed")
    if data.get("default_edit_permission") is not False:
        errors.append("default_edit_permission must be false")
    methods = data.get("methods")
    if not isinstance(methods, list) or not methods:
        return errors + ["methods must be a non-empty array"]
    ids: set[str] = set()
    aliases: set[str] = set()
    for i, method in enumerate(methods):
        p = f"methods[{i}]"
        if not isinstance(method, dict):
            errors.append(f"{p} must be an object")
            continue
        missing = REQUIRED - set(method)
        if missing:
            errors.append(f"{p} missing fields: {sorted(missing)}")
        mid = method.get("method_id")
        if not isinstance(mid, str) or not mid.strip():
            errors.append(f"{p}.method_id must be a non-empty string")
        elif mid in ids:
            errors.append(f"duplicate method_id: {mid}")
        else:
            ids.add(mid)
        if method.get("maturity") not in MATURITY:
            errors.append(f"{p}.maturity is invalid")
        if method.get("edit_permission") is not False:
            errors.append(f"{p}.edit_permission must be false; Registry cannot grant permission")
        if not isinstance(method.get("requires_human_permission"), bool):
            errors.append(f"{p}.requires_human_permission must be boolean")
        if not isinstance(method.get("acceptance"), str) or not method.get("acceptance", "").strip():
            errors.append(f"{p}.acceptance must be non-empty")
        stages = method.get("stage")
        if not isinstance(stages, list) or not stages or any(x not in STAGES for x in stages):
            errors.append(f"{p}.stage must contain valid S0-S7 stages")
        for key in ("skill_aliases", "preconditions", "inputs", "outputs", "failure_codes", "test_ids"):
            value = method.get(key)
            if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
                errors.append(f"{p}.{key} must be an array of non-empty strings")
        if isinstance(method.get("test_ids"), list) and not method["test_ids"]:
            errors.append(f"{p}.test_ids must not be empty")
        for alias in method.get("skill_aliases", []) if isinstance(method.get("skill_aliases"), list) else []:
            if alias in aliases:
                errors.append(f"duplicate skill_alias: {alias}")
            aliases.add(alias)
    return errors


class MethodRegistry:
    """Versioned method resolver. The Registry never grants pixel-edit permission."""

    def __init__(self, payload: Mapping[str, Any], source: str = "<memory>"):
        errors = validate_registry_payload(payload)
        if errors:
            raise MethodRegistryError("invalid Registry: " + "; ".join(errors))
        self.payload = dict(payload)
        self.source = source
        self.methods = {m["method_id"]: dict(m) for m in payload["methods"]}
        self.aliases = {
            alias: m["method_id"]
            for m in payload["methods"]
            for alias in m["skill_aliases"]
        }

    @classmethod
    def load(cls, path: str | Path | None = None) -> "MethodRegistry":
        p = Path(path) if path else Path(__file__).with_name("data") / "method_registry.json"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MethodRegistryError(f"cannot load Registry {p}: {exc}") from exc
        if not isinstance(data, dict):
            raise MethodRegistryError("Registry root must be an object")
        return cls(data, str(p.resolve()))

    def resolve(self, method_id: str) -> dict[str, Any]:
        if method_id not in self.methods:
            raise MethodRegistryError(f"unknown method_id: {method_id}")
        return dict(self.methods[method_id])

    def resolve_skill(self, skill_alias: str) -> dict[str, Any]:
        method_id = self.aliases.get(skill_alias)
        if method_id is None:
            raise MethodRegistryError(f"no Registry mapping for skill alias: {skill_alias}")
        return self.resolve(method_id)

    def evaluate(self, method_id: str, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        m = self.resolve(method_id)
        state = dict(context or {})
        blockers = [f"E_PRECONDITION_{key.upper()}" for key in m["preconditions"] if state.get(key) is not True]
        if "topology_verified" in m["preconditions"]:
            if state.get("topology_state") not in {"absent", "resolved"}:
                blockers.append("E_TOPOLOGY_NOT_VERIFIED_ABSENT_OR_RESOLVED")
            elif state.get("topology_human_verified") is not True:
                blockers.append("E_TOPOLOGY_REQUIRES_HUMAN_VERIFICATION")
        if m["requires_human_permission"] and state.get("human_permission") is not True:
            blockers.append("E_HUMAN_EDIT_PERMISSION_MISSING")
        if m.get("backend_id") and state.get("backend_adapter_available") is not True:
            blockers.append("E_BACKEND_ADAPTER_UNAVAILABLE")

        maturity = m["maturity"]
        if maturity == "candidate_only":
            status = "CANDIDATE_ONLY"
            warnings = ["candidate/evidence only; cannot authorize image edits"]
        elif maturity == "experimental":
            status = "REVIEW_REQUIRED_EXPERIMENTAL"
            warnings = ["experimental method; independent holdout and operator review required"]
        elif maturity in BLOCKED:
            status = BLOCKED[maturity]
            blockers.append("E_METHOD_MATURITY_BLOCKS_EXECUTION")
            warnings = []
        elif maturity not in RUNNABLE:
            status = "BLOCKED_UNKNOWN_MATURITY"
            blockers.append("E_METHOD_MATURITY_UNSUPPORTED")
            warnings = []
        elif blockers:
            status = "BLOCKED_PRECONDITIONS"
            warnings = []
        else:
            status = "READY_FOR_CANDIDATE_EXECUTION"
            warnings = []
        return {
            "method_id": method_id, "maturity": maturity, "status": status,
            "execution_allowed": maturity in RUNNABLE and not blockers,
            "edit_permission": False,
            "blockers": list(dict.fromkeys(blockers)), "warnings": warnings,
        }


def _result(stage: str, status: str, reasons: list[str], **extra: Any) -> dict[str, Any]:
    return {"stage": stage, "status": status, "reasons": reasons, **extra}


def _not_run(start: int) -> list[dict[str, Any]]:
    return [_result(f"S{i}", "NOT_RUN", ["blocked by an earlier stage"]) for i in range(start, 8)]


def _local_hash_matches(path: Any, expected: Any) -> bool:
    if not isinstance(path, str) or not path.strip() or not is_sha256(expected):
        return False
    try:
        p = Path(path)
        return p.is_file() and file_sha256(p) == expected.lower()
    except OSError:
        return False


def evaluate_s0_s7(evidence: Mapping[str, Any], registry: MethodRegistry | None = None) -> dict[str, Any]:
    """Fail-closed S0-S7 audit. Receipts are checked; no inference is performed here."""
    registry = registry or MethodRegistry.load()
    stages: list[dict[str, Any]] = []

    s0 = evidence.get("S0", {})
    source_sha = s0.get("source_sha256") if isinstance(s0, dict) else None
    if not (
        isinstance(s0, dict) and is_sha256(source_sha)
        and s0.get("source_frozen") is True and s0.get("immutable") is True
        and _local_hash_matches(s0.get("source_path"), source_sha)
    ):
        stages.append(_result("S0", "BLOCKED", ["source path/hash/freeze receipt missing or inconsistent"]))
        stages.extend(_not_run(1))
        return {"status": "BLOCKED", "stages": stages, "selected_method": None, "execution_allowed": False}
    stages.append(_result("S0", "PASS", [], source_sha256=source_sha))

    s1 = evidence.get("S1", {})
    read = s1.get("read_receipt", {}) if isinstance(s1, dict) else {}
    if not (
        isinstance(read, dict) and read.get("source_sha256") == source_sha
        and read.get("candidate_only") is True and isinstance(read.get("observations"), dict)
    ):
        stages.append(_result("S1", "BLOCKED", ["READ receipt must be source-bound and candidate-only"]))
        stages.extend(_not_run(2))
        return {"status": "BLOCKED", "stages": stages, "selected_method": None, "execution_allowed": False}
    stages.append(_result("S1", "PASS", ["READ evidence remains candidate-only; it grants no permission"]))

    s2 = evidence.get("S2", {})
    g = s2.get("geometry_contract", {}) if isinstance(s2, dict) else {}
    geometry_ok = (
        isinstance(g, dict) and g.get("source_sha256") == source_sha
        and is_sha256(g.get("canvas_sha256")) and isinstance(g.get("coordinate_frame"), str)
        and g.get("geometry_human_verified") is True and isinstance(g.get("object_transform"), dict)
        and isinstance(g.get("model_scale"), (int, float)) and g.get("model_scale", 0) > 0
        and isinstance(g.get("tile_size"), int) and g.get("tile_size", 0) > 0
        and isinstance(g.get("tile_context"), int) and g.get("tile_context", -1) >= 0
        and (g.get("delivery_resampled") is not True or isinstance(g.get("delivery_transform"), dict))
    )
    if not geometry_ok:
        stages.append(_result("S2", "BLOCKED", ["global geometry incomplete; model_scale, object_transform, tile_size and tile_context must remain independent"]))
        stages.extend(_not_run(3))
        return {"status": "BLOCKED", "stages": stages, "selected_method": None, "execution_allowed": False}
    stages.append(_result("S2", "PASS", [], coordinate_frame=g["coordinate_frame"], canvas_sha256=g["canvas_sha256"]))

    s3 = evidence.get("S3", {})
    p = s3.get("permission", {}) if isinstance(s3, dict) else {}
    permission_ok = (
        isinstance(p, dict) and p.get("human_reviewed") is True and p.get("permission_granted") is True
        and p.get("base_sha256") == source_sha and p.get("coordinate_canvas_sha256") == g["canvas_sha256"]
        and is_sha256(p.get("approved_edit_mask_sha256")) and is_sha256(p.get("protected_mask_sha256"))
        and _local_hash_matches(p.get("approved_edit_mask_path"), p.get("approved_edit_mask_sha256"))
        and _local_hash_matches(p.get("protected_mask_path"), p.get("protected_mask_sha256"))
        and isinstance(p.get("target_regions"), list) and bool(p.get("target_regions"))
    )
    if not permission_ok:
        stages.append(_result("S3", "BLOCKED", ["human-reviewed, source-bound approved/protected masks missing or inconsistent"]))
        stages.extend(_not_run(4))
        return {"status": "BLOCKED", "stages": stages, "selected_method": None, "execution_allowed": False}
    stages.append(_result("S3", "PASS", [], target_regions=p["target_regions"]))

    s4 = evidence.get("S4", {})
    method_id = s4.get("method_id") if isinstance(s4, dict) else None
    if not isinstance(method_id, str) or not method_id:
        stages.append(_result("S4", "BLOCKED", ["Router did not select method_id from Registry"]))
        stages.extend(_not_run(5))
        return {"status": "BLOCKED", "stages": stages, "selected_method": None, "execution_allowed": False}
    obs = read["observations"]
    topology = obs.get("topology_error", {})
    topology_ok = isinstance(topology, dict) and topology.get("state") in {"absent", "resolved"} and topology.get("verification") == "human_verified"
    derived = {
        "s0_source_sha_verified": True, "topology_verified": topology_ok,
        "topology_state": topology.get("state", "unknown") if isinstance(topology, dict) else "unknown",
        "topology_human_verified": topology_ok, "geometry_contract_verified": True,
        "human_permission": True, "approved_masks_verified": True,
    }
    method_context = s4.get("method_context", {}) if isinstance(s4, dict) else {}
    if not isinstance(method_context, dict):
        method_context = {}
    decision = registry.evaluate(method_id, {**method_context, **derived})
    if not decision["execution_allowed"]:
        stages.append(_result("S4", "BLOCKED", decision["blockers"] or [decision["status"]], method_decision=decision))
        stages.extend(_not_run(5))
        return {"status": "BLOCKED", "stages": stages, "selected_method": method_id, "method_decision": decision, "execution_allowed": False}
    stages.append(_result("S4", "PASS", [], method_decision=decision))

    method = registry.resolve(method_id)
    s5 = evidence.get("S5", {})
    if method.get("execution_kind") in {"neural_sr", "diffusion", "external_backend"}:
        r = s5.get("backend_receipt", {}) if isinstance(s5, dict) else {}
        receipt_ok = (
            isinstance(r, dict) and r.get("real_backend_call") is True and r.get("receipt_verified") is True
            and r.get("backend_id") == method.get("backend_id")
            and isinstance(r.get("model_id"), str) and bool(r.get("model_id"))
            and is_sha256(r.get("model_sha256")) and r.get("parent_source_sha256") == source_sha
            and isinstance(r.get("input_sha256s"), list) and bool(r.get("input_sha256s"))
            and all(is_sha256(x) for x in r.get("input_sha256s", []))
            and is_sha256(r.get("output_sha256"))
            and isinstance(r.get("request_id"), str) and bool(r.get("request_id"))
            and isinstance(r.get("parameters"), dict)
        )
        output_sha = r.get("output_sha256") if isinstance(r, dict) else None
        detail = {"backend_id": r.get("backend_id"), "model_id": r.get("model_id"), "output_sha256": output_sha} if isinstance(r, dict) else {}
        why = "real backend/model/input/output receipt incomplete or method-mismatched"
    else:
        r = s5.get("operation_receipt", {}) if isinstance(s5, dict) else {}
        receipt_ok = (
            isinstance(r, dict) and r.get("execution_verified") is True and r.get("method_id") == method_id
            and is_sha256(r.get("implementation_sha256")) and r.get("parent_source_sha256") == source_sha
            and isinstance(r.get("input_sha256s"), list) and bool(r.get("input_sha256s"))
            and all(is_sha256(x) for x in r.get("input_sha256s", []))
            and is_sha256(r.get("output_sha256")) and isinstance(r.get("operation_parameters"), dict)
        )
        output_sha = r.get("output_sha256") if isinstance(r, dict) else None
        detail = {"execution_kind": method.get("execution_kind"), "output_sha256": output_sha} if isinstance(r, dict) else {}
        why = "deterministic operation receipt incomplete or method-mismatched"
    if not receipt_ok:
        stages.append(_result("S5", "BLOCKED", [why]))
        stages.extend(_not_run(6))
        return {"status": "BLOCKED", "stages": stages, "selected_method": method_id, "method_decision": decision, "execution_allowed": False}
    stages.append(_result("S5", "PASS", [], **detail))

    s6 = evidence.get("S6", {})
    a = s6.get("return_audit", {}) if isinstance(s6, dict) else {}
    return_ok = (
        isinstance(a, dict) and a.get("source_sha256") == source_sha and a.get("output_sha256") == output_sha
        and a.get("core_only_writes") is True and a.get("halo_write_pixels") == 0
        and a.get("core_overlap_pixels") == 0 and a.get("coverage_gap_pixels") == 0
        and a.get("outside_authorized_changed_pixels") == 0
        and a.get("implicit_resize") is False and a.get("implicit_flip") is False
    )
    if not return_ok:
        stages.append(_result("S6", "BLOCKED", ["core-only return, coverage, or pixel-preservation audit failed/incomplete"]))
        stages.extend(_not_run(7))
        return {"status": "BLOCKED", "stages": stages, "selected_method": method_id, "method_decision": decision, "execution_allowed": False}
    stages.append(_result("S6", "PASS", []))

    s7 = evidence.get("S7", {})
    ac = s7.get("acceptance", {}) if isinstance(s7, dict) else {}
    gates = ac.get("gate_results", {}) if isinstance(ac, dict) else {}
    gates_ok = isinstance(gates, dict) and all(gates.get(k) == "PASS" for k in S7_GATES)
    accepted = (
        isinstance(ac, dict) and ac.get("independent_reloaded") is True
        and ac.get("source_sha256") == source_sha and ac.get("saved_output_sha256") == a.get("output_sha256")
        and ac.get("human_visual_review") == "PASS" and ac.get("visual_review_source") == "human"
        and gates_ok
    )
    if not accepted:
        missing = [f"E_S7_GATE_{k.upper()}" for k in S7_GATES if not isinstance(gates, dict) or gates.get(k) != "PASS"]
        stages.append(_result("S7", "BLOCKED", ["independent reload/acceptance gates missing or failed", *missing]))
        return {"status": "BLOCKED", "stages": stages, "selected_method": method_id, "method_decision": decision, "execution_allowed": False}
    stages.append(_result("S7", "PASS", [], accepted_output_sha256=ac["saved_output_sha256"]))
    return {
        "status": "ACCEPTED_CANDIDATE", "stages": stages, "selected_method": method_id,
        "method_decision": decision, "execution_allowed": True, "edit_permission": False,
        "note": "S7 acceptance audits a candidate; Registry never grants edit permission.",
    }
