from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ige.cli import build_parser, main
from ige.comfy.model_inventory import (
    EVIDENCE_GRADE_DECLARED,
    FAILURE_BACKEND_INVENTORY,
    ModelInventoryError,
    backend_model_inventory_verified,
    load_model_inventory,
    validate_declared_inventory,
    validate_inventory_payload,
    verify_against_workflow_audit,
    verify_siax_registry_pin,
)
from ige.comfy.workflow_static_audit import audit_comfy_workflows
from ige.method_registry import MethodRegistry

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "comfy"
INVENTORY = FIXTURES / "backend_model_inventory_pc_dev_fp8_v0.1.json"
UI = FIXTURES / "workflow_ige_v03_dev_fp8.json"
API = FIXTURES / "workflow_cloud_api_prompt_v0.5.json"


class BackendModelInventoryTests(unittest.TestCase):
    def test_fixture_validates(self):
        payload = load_model_inventory(INVENTORY)
        self.assertEqual(payload["schema"], "ige-backend-model-inventory/0.1")
        self.assertEqual(payload["policy"], "fail_closed")
        self.assertEqual(payload.get("evidence_grade"), EVIDENCE_GRADE_DECLARED)
        self.assertEqual(len(payload["assets"]), 5)
        self.assertGreaterEqual(len(payload["custom_nodes"]), 9)
        self.assertEqual(payload["load_options"]["unet_weight_dtype"], "fp8_e4m3fn_fast")
        self.assertFalse(validate_inventory_payload(payload))

    def test_siax_matches_registry_pin(self):
        inventory = load_model_inventory(INVENTORY)
        registry = MethodRegistry.load()
        pinned = registry.resolve("SIAX4X_TILE_CORE_SR")["model_sha256"]
        siax = next(a for a in inventory["assets"] if a["asset_id"] == "SIAX4X")
        self.assertEqual(siax["sha256"].lower(), pinned.lower())
        result = verify_siax_registry_pin(inventory, registry=registry)
        self.assertTrue(result["matched"])
        self.assertEqual(result["status"], "PASS")

    def test_wrong_sha_fails(self):
        inventory = load_model_inventory(INVENTORY)
        bad = copy.deepcopy(inventory)
        for asset in bad["assets"]:
            if asset["asset_id"] == "FLUX1_DEV":
                asset["sha256"] = "0" * 64
        # schema still ok
        self.assertFalse(validate_inventory_payload(bad))
        # mutate Siax instead for pin failure
        bad2 = copy.deepcopy(inventory)
        for asset in bad2["assets"]:
            if asset["asset_id"] == "SIAX4X":
                asset["sha256"] = "1" * 64
        result = verify_siax_registry_pin(bad2)
        self.assertFalse(result["matched"])
        self.assertEqual(result["status"], "FAIL")
        verified = backend_model_inventory_verified(bad2)
        self.assertFalse(verified["verified"])
        self.assertIn("siax_registry_pin_mismatch", verified["blockers"])
        self.assertFalse(verified["execution_allowed"])

    def test_missing_required_asset_fails(self):
        inventory = load_model_inventory(INVENTORY)
        bad = copy.deepcopy(inventory)
        bad["assets"] = [a for a in bad["assets"] if a["role"] != "unet"]
        errors = validate_inventory_payload(bad)
        self.assertFalse(errors)  # schema still valid with other assets
        verified = backend_model_inventory_verified(bad)
        self.assertFalse(verified["verified"])
        self.assertIn("missing_required_role:unet", verified["blockers"])

    def test_invalid_schema_rejected(self):
        inventory = load_model_inventory(INVENTORY)
        bad = copy.deepcopy(inventory)
        bad["schema"] = "wrong"
        with self.assertRaises(ModelInventoryError):
            # load path uses validate
            with TemporaryDirectory() as tmp:
                path = Path(tmp) / "bad.json"
                path.write_text(json.dumps(bad), encoding="utf-8")
                load_model_inventory(path)

    def test_verify_against_workflow_audit_pass(self):
        inventory = load_model_inventory(INVENTORY)
        report = audit_comfy_workflows(ui_path=UI, api_path=API)
        check = verify_against_workflow_audit(inventory, report)
        self.assertEqual(check["code"], FAILURE_BACKEND_INVENTORY)
        self.assertEqual(check["status"], "PASS")
        self.assertEqual(check["evidence"]["siax_registry_pin"]["status"], "PASS")

    def test_merged_static_audit_inventory_pass_but_not_executable(self):
        report = audit_comfy_workflows(
            ui_path=UI,
            api_path=API,
            model_inventory_path=INVENTORY,
        )
        self.assertEqual(report["inventory_status"], "PASS_STATIC_INVENTORY")
        self.assertFalse(report["execution_allowed"])
        self.assertEqual(report["maturity_remains"], "workflow_candidate")
        self.assertEqual(report["overall_status"], "BLOCKED_WORKFLOW_CANDIDATE")
        backend = report["backend_model_inventory"]
        self.assertEqual(backend["status"], "PASS")
        self.assertEqual(backend["evidence_grade"], EVIDENCE_GRADE_DECLARED)
        self.assertFalse(backend["inventory_live_verified"])
        self.assertTrue(backend["inventory_declared_ok"])
        check = next(c for c in report["checks"] if c["code"] == FAILURE_BACKEND_INVENTORY)
        self.assertEqual(check["status"], "PASS")
        siax = backend["siax_registry_pin"]
        self.assertTrue(siax["matched"])
        # Registry unchanged
        method = MethodRegistry.load().resolve("FLUX_HR_TILE_IMG2IMG")
        self.assertEqual(method["maturity"], "workflow_candidate")
        self.assertIs(method["edit_permission"], False)

    def test_merged_audit_fails_on_wrong_inventory_sha(self):
        inventory = load_model_inventory(INVENTORY)
        bad = copy.deepcopy(inventory)
        for asset in bad["assets"]:
            if asset["asset_id"] == "SIAX4X":
                asset["sha256"] = "a" * 64
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad_inv.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            report = audit_comfy_workflows(
                ui_path=UI,
                api_path=API,
                model_inventory_path=path,
            )
        self.assertEqual(report["inventory_status"], "FAIL_STATIC_INVENTORY")
        self.assertIn(FAILURE_BACKEND_INVENTORY, report["structural_blockers"])
        self.assertFalse(report["execution_allowed"])

    def test_flux_remains_non_executable_even_with_full_inventory(self):
        verified = backend_model_inventory_verified(
            load_model_inventory(INVENTORY),
            static_audit_report=audit_comfy_workflows(ui_path=UI, api_path=API),
        )
        # Declared record may pass filename/pin checks, but is NOT live-verified.
        self.assertTrue(verified["inventory_declared_ok"])
        self.assertFalse(verified["inventory_live_verified"])
        self.assertFalse(verified["verified"])  # alias of live_verified
        self.assertEqual(verified["evidence_grade"], EVIDENCE_GRADE_DECLARED)
        self.assertFalse(verified["execution_allowed"])
        self.assertTrue(verified["maturity_unchanged"])
        declared = validate_declared_inventory(load_model_inventory(INVENTORY))
        self.assertEqual(declared["status"], "DECLARED_RECORD_VALID")

    def test_cli_validate_model_inventory(self):
        import sys

        old = sys.argv
        sys.argv = ["ige", "validate-model-inventory", "--path", str(INVENTORY)]
        try:
            code = main()
        finally:
            sys.argv = old
        self.assertEqual(code, 0)

    def test_cli_audit_comfy_with_model_inventory(self):
        import sys
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "audit.json"
            old = sys.argv
            sys.argv = [
                "ige",
                "audit-comfy-workflow",
                "--ui",
                str(UI),
                "--api",
                str(API),
                "--model-inventory",
                str(INVENTORY),
                "--out",
                str(out),
            ]
            try:
                code = main()
            finally:
                sys.argv = old
            self.assertEqual(code, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(payload["execution_allowed"])
            self.assertEqual(payload["backend_model_inventory"]["status"], "PASS")

    def test_cli_parser_registers_commands(self):
        parser = build_parser()
        args = parser.parse_args(["validate-model-inventory", "--path", str(INVENTORY)])
        self.assertEqual(args.command, "validate-model-inventory")
        args2 = parser.parse_args(
            [
                "audit-comfy-workflow",
                "--ui",
                str(UI),
                "--model-inventory",
                str(INVENTORY),
            ]
        )
        self.assertEqual(args2.model_inventory, INVENTORY)


if __name__ == "__main__":
    unittest.main()
