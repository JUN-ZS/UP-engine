"""Unit tests for src/ige/method_registry.py (extends package test_registry patterns)."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CONTRACT = ROOT / "contracts" / "IGE_S0_S7_METHOD_REGISTRY_V0.1.json"
PACKAGE_JSON = ROOT / "IGE_S0_S7_MethodRegistry_v0.1" / "method_registry.json"

sys.path.insert(0, str(SRC))

from ige.method_registry import (  # noqa: E402
    MethodNotFoundError,
    MethodRegistry,
    RegistryValidationError,
    load_registry,
    resolve,
    validate_registry_data,
)


class LoaderValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_seed_validates(self):
        self.assertEqual(validate_registry_data(self.data), [])

    def test_duplicate_method_is_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["methods"].append(copy.deepcopy(bad["methods"][0]))
        errors = validate_registry_data(bad)
        self.assertTrue(any("duplicate method_id" in e for e in errors))

    def test_ai_method_cannot_grant_edit_permission_by_default(self):
        bad = copy.deepcopy(self.data)
        bad["methods"][0]["edit_permission"] = True
        errors = validate_registry_data(bad)
        self.assertTrue(any("edit_permission" in e for e in errors))

    def test_missing_test_ids_are_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["methods"][0]["test_ids"] = []
        errors = validate_registry_data(bad)
        self.assertTrue(any("test_ids" in e for e in errors))

    def test_load_refuses_edit_permission_true(self):
        bad = copy.deepcopy(self.data)
        bad["methods"][0]["edit_permission"] = True
        with self.assertRaises(RegistryValidationError):
            MethodRegistry(bad)

    def test_default_edit_permission_must_be_false(self):
        bad = copy.deepcopy(self.data)
        bad["default_edit_permission"] = True
        errors = validate_registry_data(bad)
        self.assertTrue(any("default_edit_permission" in e for e in errors))


class LoaderQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = load_registry(CONTRACT)

    def test_method_count_is_nine(self):
        self.assertEqual(self.reg.method_count, 9)

    def test_all_edit_permission_false(self):
        self.reg.assert_no_edit_permission_granted()
        summary = self.reg.summary()
        self.assertTrue(summary["all_edit_permission_false"])
        self.assertFalse(summary["default_edit_permission"])
        self.assertFalse(summary["production_wired"])

    def test_resolve_known_method(self):
        rec = self.reg.resolve("FLUX_HR_TILE_IMG2IMG")
        self.assertEqual(rec["method_id"], "FLUX_HR_TILE_IMG2IMG")
        self.assertEqual(rec["backend_id"], "comfyui_flux_dev_img2img")
        self.assertIs(rec["edit_permission"], False)

    def test_resolve_unknown_fail_closed(self):
        with self.assertRaises(MethodNotFoundError):
            self.reg.resolve("DOES_NOT_EXIST")

    def test_module_level_resolve(self):
        rec = resolve("SIAX4X_TILE_CORE_SR", path=CONTRACT)
        self.assertEqual(rec["capability"], "neural_super_resolution")
        self.assertIs(rec["edit_permission"], False)

    def test_query_by_stage(self):
        s5 = self.reg.by_stage("S5")
        ids = {m["method_id"] for m in s5}
        self.assertIn("SIAX4X_TILE_CORE_SR", ids)
        self.assertIn("FLUX_HR_TILE_IMG2IMG", ids)
        self.assertIn("ALL24_AI_DONOR_MULTIBAND_TRANSFER", ids)
        # READ is S1-only
        self.assertNotIn("READ_LAYERED_EVIDENCE", ids)

    def test_query_by_capability(self):
        hits = self.reg.by_capability("high_resolution_tile_diffusion")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["method_id"], "FLUX_HR_TILE_IMG2IMG")

    def test_query_by_backend_id(self):
        hits = self.reg.by_backend_id("spandrel_siax_4x")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["method_id"], "SIAX4X_TILE_CORE_SR")

    def test_query_by_implementation_status(self):
        hits = self.reg.by_implementation_status(
            "research_only_external_donor_transfer_not_destination_tile_diffusion"
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["method_id"], "ALL24_AI_DONOR_MULTIBAND_TRANSFER")

    def test_three_backends_remain_distinct(self):
        ids = set(self.reg.method_ids())
        self.assertIn("SIAX4X_TILE_CORE_SR", ids)
        self.assertIn("FLUX_HR_TILE_IMG2IMG", ids)
        self.assertIn("ALL24_AI_DONOR_MULTIBAND_TRANSFER", ids)
        a = self.reg.resolve("SIAX4X_TILE_CORE_SR")
        b = self.reg.resolve("FLUX_HR_TILE_IMG2IMG")
        c = self.reg.resolve("ALL24_AI_DONOR_MULTIBAND_TRANSFER")
        self.assertNotEqual(a.get("backend_id"), b.get("backend_id"))
        self.assertNotEqual(a["capability"], b["capability"])
        self.assertNotEqual(b["capability"], c["capability"])
        self.assertNotEqual(a["capability"], c["capability"])

    def test_package_json_matches_contract_seed(self):
        pkg = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
        self.assertEqual(pkg["registry_version"], self.reg.registry_version)
        self.assertEqual(len(pkg["methods"]), self.reg.method_count)

    def test_resolve_does_not_mutate_store(self):
        rec = self.reg.resolve("HOLE_FOUR_ANTI_EVIDENCE")
        rec["edit_permission"] = True  # caller mutation must not poison store
        again = self.reg.resolve("HOLE_FOUR_ANTI_EVIDENCE")
        self.assertIs(again["edit_permission"], False)


if __name__ == "__main__":
    unittest.main()
