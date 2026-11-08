from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "docs/handoff/comfy-siax-return/packages/ComfyUI_IGE_GlobalLogicCoordinator/ige_logic/execution_gate.py"
SPEC = importlib.util.spec_from_file_location("comfy_execution_gate_under_test", MODULE)
GATE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(GATE)


def valid_bundle():
    source_sha = "a" * 64
    contract = {
        "schema_version": "ige-global-logic-contract/0.1",
        "contract_id": "contract-001",
        "source_sha256": source_sha,
        "canvas": {"width": 1024, "height": 768},
        "geometry_status": "operator_confirmed",
        "source_alignment_status": "operator_confirmed",
        "policy_id": "policy-1",
        "policy_revision": 3,
    }
    return {"contract": contract, "source_shape": [768, 1024], "source_hash": source_sha}


def approval_for(bundle):
    c = bundle["contract"]
    return {
        "schema_version": "ige-comfy-execution-authorization/0.1",
        "contract_id": c["contract_id"],
        "source_sha256": c["source_sha256"],
        "policy_id": c["policy_id"],
        "policy_revision": c["policy_revision"],
        "geometry_status": "operator_confirmed",
        "source_alignment_status": "operator_confirmed",
        "workflow_status": "ACCEPTED",
        "geometry_acceptance_status": "ACCEPTED",
        "execution_allowed": True,
        "operator_authorized": True,
        "approval_reference": "human-acceptance-record-001",
        "authorized_branches": ["baseline_A", "candidate_B"],
    }


class ExecutionGateTests(unittest.TestCase):
    def test_empty_default_authorization_blocks(self):
        with self.assertRaises(GATE.ExecutionGateError):
            GATE.validate_execution_authorization(valid_bundle(), "{}", "baseline_A")

    def test_provisional_geometry_blocks_even_with_true_flags(self):
        bundle = valid_bundle()
        bundle["contract"]["geometry_status"] = "assistant_provisional"
        approval = approval_for(bundle)
        with self.assertRaisesRegex(GATE.ExecutionGateError, "geometry is not operator_confirmed"):
            GATE.validate_execution_authorization(bundle, __import__("json").dumps(approval), "baseline_A")

    def test_source_alignment_mismatch_blocks(self):
        bundle = valid_bundle()
        bundle["contract"]["source_alignment_status"] = "pending_operator_registration"
        approval = approval_for(bundle)
        with self.assertRaisesRegex(GATE.ExecutionGateError, "registration is not operator_confirmed"):
            GATE.validate_execution_authorization(bundle, __import__("json").dumps(approval), "baseline_A")

    def test_source_shape_mismatch_blocks(self):
        bundle = valid_bundle()
        bundle["source_shape"] = [2172, 3862]
        with self.assertRaisesRegex(GATE.ExecutionGateError, "contract canvas"):
            GATE.validate_execution_authorization(bundle, "{}", "baseline_A")

    def test_token_must_match_contract_and_branch(self):
        bundle = valid_bundle()
        approval = approval_for(bundle)
        approval["contract_id"] = "different"
        with self.assertRaisesRegex(GATE.ExecutionGateError, "binding mismatch"):
            GATE.validate_execution_authorization(bundle, __import__("json").dumps(approval), "baseline_A")
        approval = approval_for(bundle)
        with self.assertRaisesRegex(GATE.ExecutionGateError, "not authorized"):
            GATE.validate_execution_authorization(bundle, __import__("json").dumps(approval), "diagnostic_branch")

    def test_valid_contract_bound_human_approval_passes(self):
        bundle = valid_bundle()
        report = GATE.validate_execution_authorization(
            bundle, __import__("json").dumps(approval_for(bundle)), "baseline_A"
        )
        self.assertEqual(report["status"], "AUTHORIZED")
        self.assertEqual(report["contract_id"], "contract-001")


if __name__ == "__main__":
    unittest.main()
