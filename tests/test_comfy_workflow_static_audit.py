from __future__ import annotations

import json
import unittest
from pathlib import Path

from ige.comfy.workflow_static_audit import (
    EXPECTED_DEV_FP8_MODELS,
    audit_comfy_workflows,
    structural_inventory_ok,
)
from ige.cli import build_parser, main
from ige.method_registry import MethodRegistry

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "comfy"
UI = FIXTURES / "workflow_ige_v03_dev_fp8.json"
API = FIXTURES / "workflow_cloud_api_prompt_v0.5.json"


class ComfyWorkflowStaticAuditTests(unittest.TestCase):
    def test_fixtures_exist(self):
        self.assertTrue(UI.is_file())
        self.assertTrue(API.is_file())

    def test_inventory_extracts_expected_dev_fp8_models(self):
        report = audit_comfy_workflows(ui_path=UI, api_path=API)
        ui_models = report["inventories"]["ui"]["models"]
        api_models = report["inventories"]["api"]["models"]
        for key, expected in EXPECTED_DEV_FP8_MODELS.items():
            self.assertEqual(ui_models.get(key), expected, key)
            self.assertEqual(api_models.get(key), expected, key)
        self.assertEqual(ui_models.get("upscale_model"), "4x_NMKD-Siax_200k.pth")
        self.assertEqual(ui_models.get("noise_seed"), 909424749197426)
        self.assertEqual(api_models.get("noise_seed"), 909424749197426)

    def test_api_per_tile_conditioning_detected_as_static_evidence(self):
        report = audit_comfy_workflows(api_path=API)
        cond = next(c for c in report["checks"] if c["code"] == "E_TILE_CONDITIONING_UNROUTED")
        self.assertEqual(cond["status"], "PASS")
        self.assertIn("static", cond["detail"].lower())
        self.assertGreaterEqual(cond["evidence"]["nonempty_prompt_count"], 2)
        self.assertGreaterEqual(cond["evidence"]["distinct_guider_conditioning_refs"], 2)

    def test_same_seed_noise_not_accepted_as_global_noise_proof(self):
        report = audit_comfy_workflows(ui_path=UI, api_path=API)
        noise = next(c for c in report["checks"] if c["code"] == "E_NOISE_FIELD_NOT_GLOBAL")
        self.assertEqual(noise["status"], "FAIL")
        self.assertIn("same seed", noise["detail"].lower())
        self.assertIn("≠", noise["evidence"]["rule"])
        self.assertEqual(noise["evidence"]["field_kind"], "shared_seed_only")
        self.assertEqual(noise["evidence"]["test_id"], "NOISE_FIELD_NOT_GLOBAL")
        self.assertEqual(report["noise_field_kind"], "shared_seed_only")
        self.assertIn("shared_seed_only", (report.get("noise_field_reason") or ""))

    def test_flux_remains_non_executable(self):
        report = audit_comfy_workflows(ui_path=UI, api_path=API)
        self.assertFalse(report["execution_allowed"])
        self.assertEqual(report["maturity_remains"], "workflow_candidate")
        self.assertEqual(report["overall_status"], "BLOCKED_WORKFLOW_CANDIDATE")
        self.assertEqual(report["method_id"], "FLUX_HR_TILE_IMG2IMG")
        # Structural inventory may PASS while maturity stays blocked.
        self.assertEqual(report["inventory_status"], "PASS_STATIC_INVENTORY")
        self.assertTrue(structural_inventory_ok(report))

    def test_registry_not_promoted_by_static_audit(self):
        registry = MethodRegistry.load()
        method = registry.resolve("FLUX_HR_TILE_IMG2IMG")
        self.assertEqual(method["maturity"], "workflow_candidate")
        self.assertIs(method["edit_permission"], False)
        report = audit_comfy_workflows(ui_path=UI, api_path=API)
        self.assertFalse(report["execution_allowed"])
        # Reload to ensure packaged registry unchanged by audit call.
        again = MethodRegistry.load().resolve("FLUX_HR_TILE_IMG2IMG")
        self.assertEqual(again["maturity"], "workflow_candidate")
        self.assertIs(again["edit_permission"], False)

    def test_ui_has_core_halo_inventory_nodes(self):
        report = audit_comfy_workflows(ui_path=UI)
        ui = report["inventories"]["ui"]
        self.assertTrue(ui["has_ige_tile_noise_mask"])
        self.assertTrue(ui["has_set_latent_noise_mask"])
        self.assertTrue(ui["has_ttp_tile_batch"])

    def test_single_shared_conditioning_fails_tile_check(self):
        report = audit_comfy_workflows(api_path=FIXTURES / "synthetic_single_cond_api.json")
        cond = next(c for c in report["checks"] if c["code"] == "E_TILE_CONDITIONING_UNROUTED")
        self.assertEqual(cond["status"], "FAIL")
        self.assertFalse(report["execution_allowed"])

    def test_missing_unet_fails_structural_inventory(self):
        report = audit_comfy_workflows(api_path=FIXTURES / "synthetic_missing_unet_api.json")
        self.assertEqual(report["inventory_status"], "FAIL_STATIC_INVENTORY")
        self.assertIn("E_COMFY_NODE_MISSING", report["structural_blockers"])
        self.assertFalse(structural_inventory_ok(report))

    def test_wrong_unet_filename_fails_model_inventory(self):
        report = audit_comfy_workflows(api_path=FIXTURES / "synthetic_wrong_unet_api.json")
        self.assertEqual(report["inventory_status"], "FAIL_STATIC_INVENTORY")
        self.assertIn("E_MODEL_INVENTORY_MISMATCH", report["structural_blockers"])
        model = next(c for c in report["checks"] if c["code"] == "E_MODEL_INVENTORY_MISMATCH")
        self.assertEqual(model["status"], "FAIL")

    def test_cli_parser_registers_audit_comfy_workflow(self):
        parser = build_parser()
        args = parser.parse_args([
            "audit-comfy-workflow",
            "--ui", str(UI),
            "--api", str(API),
            "--out", "out.json",
        ])
        self.assertEqual(args.command, "audit-comfy-workflow")
        self.assertEqual(args.ui, UI)
        self.assertEqual(args.api, API)

    def test_cli_main_returns_zero_for_fixture_inventory(self):
        import sys
        from io import StringIO
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
            self.assertEqual(payload["maturity_remains"], "workflow_candidate")

    def test_cli_main_nonzero_on_structural_blocker(self):
        import sys

        old = sys.argv
        sys.argv = [
            "ige",
            "audit-comfy-workflow",
            "--api",
            str(FIXTURES / "synthetic_missing_unet_api.json"),
        ]
        try:
            code = main()
        finally:
            sys.argv = old
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
