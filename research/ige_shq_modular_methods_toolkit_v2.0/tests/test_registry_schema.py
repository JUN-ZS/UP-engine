#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_registry_schema.py
=============================
Portable unit test suite for `registry/method_registry.json` (`ige-method-registry/0.1`).
Uses strictly relative paths so any external AI or developer can run:
  `python3 -m unittest discover -s tests -v`
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent.parent
_REG_DIR = _PKG_ROOT / "registry"


def _load_validator():
    val_path = _REG_DIR / "validate_registry.py"
    spec = importlib.util.spec_from_file_location("validate_registry", str(val_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["validate_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestMethodRegistrySchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.val_mod = _load_validator()
        cls.reg_path = _REG_DIR / "method_registry.json"
        cls.data = json.loads(cls.reg_path.read_text(encoding="utf-8"))

    def test_01_registry_validates_with_zero_errors(self):
        errors = self.val_mod.validate(self.data)
        self.assertEqual(errors, [])

    def test_02_every_method_defaults_to_edit_permission_false(self):
        for m in self.data["methods"]:
            self.assertFalse(m["edit_permission"], f"{m['method_id']} must default to edit_permission=False")

    def test_03_all_8_layered_battlefield_methods_present(self):
        ids = {m["method_id"] for m in self.data["methods"]}
        required = {
            "BF_S0_EDIT_4WAY_ANTI_HOLE",
            "BF_S1_SELF_18PART_DECOMPOSE_READ",
            "BF_S2_SELF_PART_4X_GEOMETRY_LOCK",
            "BF_S3_HUMAN_PERMISSION_COMPILER",
            "SKILL_A_NEURAL_SR_BASE_4X",
            "SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN",
            "SKILL_C_MULTISCALE_DETAIL_SYNTHESIS",
            "SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD",
        }
        self.assertTrue(required.issubset(ids))

    def test_04_inpaint_explicitly_demoted_from_primary_upscaler(self):
        by_id = {m["method_id"]: m for m in self.data["methods"]}
        self.assertIn("INPAINT_HOLE_REPAIR_OPTIONAL", by_id)
        inp = by_id["INPAINT_HOLE_REPAIR_OPTIONAL"]
        self.assertIn("acts_as_the_primary_or_sole_high_resolution_upscaling_material_or_detail_engine", inp["forbidden_non_claims"])



    def test_05_preflight_check_passes_all_13_assets_and_anti_spoofing(self):
        pf_path = _PKG_ROOT / "preflight_check.py"
        spec = importlib.util.spec_from_file_location("preflight_check", str(pf_path))
        pf_mod = importlib.util.module_from_spec(spec)
        sys.modules["preflight_check"] = pf_mod
        spec.loader.exec_module(pf_mod)
        res = pf_mod.run_preflight(_PKG_ROOT)
        self.assertEqual(res["status"], "PASS", f"Preflight failed: {res['errors']}")
        self.assertEqual(res["exit_code"], 0)
        self.assertEqual(res["total_assets_verified"], 13)
        self.assertEqual(res["b0_gl_status"], "PASS")
        self.assertEqual(res["b2_gl_status"], "PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
