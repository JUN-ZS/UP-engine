from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.build_comfy_siax_staged_workflows import build_staged_workflows

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/handoff/comfy-siax-return/pc_高清探/workflow_ige_v03_dev_fp8_gated_candidate.json"


class ComfySiaxStagingTests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads(BASE.read_text(encoding="utf-8"))

    def test_stage1_is_siaux_only_and_saves_node34_canvas(self):
        stage1, _, report = build_staged_workflows(self.original)
        nodes = {int(n["id"]): n for n in stage1["nodes"]}
        self.assertEqual(set(nodes), {34, 128, 133, 134, 233, 244})
        self.assertFalse(report["stage1"]["contains_sampler"])
        self.assertFalse(report["stage1"]["contains_flux_unet_loader"])
        self.assertEqual(nodes[34]["type"], "ImageScaleToTotalPixels")
        self.assertEqual(nodes[128]["type"], "SaveImage")
        self.assertEqual(nodes[128]["inputs"][0]["link"], 533)
        self.assertEqual(nodes[128]["widgets_values"][0], "IGE/SIAX_STAGE1_CANVAS")
        self.assertEqual(nodes[34]["outputs"][0]["links"], [533])

    def test_stage2_reuses_the_same_canvas_node_id_and_keeps_ige_gates(self):
        _, stage2, report = build_staged_workflows(self.original)
        nodes = {int(n["id"]): n for n in stage2["nodes"]}
        self.assertEqual(nodes[34]["type"], "LoadImage")
        self.assertNotIn(233, nodes)
        self.assertNotIn(244, nodes)
        self.assertNotIn(133, nodes)
        self.assertNotIn(134, nodes)
        self.assertIn(300, nodes)
        self.assertIn(36, nodes)
        self.assertIn(342, nodes)
        self.assertIn(343, nodes)
        self.assertEqual(report["stage2"]["sampler_count"], 2)
        self.assertFalse(report["stage2"]["execution_allowed"])

    def test_build_does_not_mutate_source_workflow(self):
        before = json.dumps(self.original, sort_keys=True)
        build_staged_workflows(self.original)
        self.assertEqual(json.dumps(self.original, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main()
