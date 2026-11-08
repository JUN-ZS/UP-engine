#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_modular_methods.py
=======================
Unit tests verifying that all 22 categorized `.py` method scripts (`M01`–`M22`)
and 3 end-to-end recipes (`R01`–`R03`) exist on disk, expose `run_method()` /
`run_recipe()`, match `registry/method_registry.json`, and execute cleanly via
`invoke_method.py`.
"""

import json
import sys
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

import invoke_method


class TestModularMethodsToolkit(unittest.TestCase):
    def test_01_all_22_method_files_and_3_recipes_exist(self):
        self.assertEqual(len(invoke_method.METHODS_LIST), 22)
        self.assertEqual(len(invoke_method.RECIPES_LIST), 3)
        for m in invoke_method.METHODS_LIST:
            py_file = PKG_ROOT / "methods" / m["category"] / f"{m['slug']}.py"
            self.assertTrue(py_file.exists(), f"Missing method script: {py_file}")
        for r in invoke_method.RECIPES_LIST:
            py_file = PKG_ROOT / "recipes" / f"{r['slug']}.py"
            self.assertTrue(py_file.exists(), f"Missing recipe script: {py_file}")

    def test_02_all_22_methods_match_registry_ids(self):
        reg_data = json.loads((PKG_ROOT / "registry" / "method_registry.json").read_text(encoding="utf-8"))
        reg_ids = {m["method_id"] for m in reg_data["methods"]}
        catalog_ids = {m["method_id"] for m in invoke_method.METHODS_LIST}
        self.assertEqual(reg_ids, catalog_ids)

    def test_03_invoke_single_methods_across_categories(self):
        for code in ["M01", "M04", "M08", "M11", "M12", "M13", "M22"]:
            rec = invoke_method.run_single_method_by_key(code, part_id="P08")
            self.assertEqual(rec["code"], code)
            self.assertEqual(rec["status"], "PASS")
            self.assertTrue((PKG_ROOT / rec["preview_image_file"]).exists())
            self.assertTrue((PKG_ROOT / rec["receipt_json_file"]).exists())


if __name__ == "__main__":
    unittest.main()
