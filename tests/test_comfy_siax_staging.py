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
        self.assertNotIn(262, nodes)
        self.assertEqual(nodes[344]["type"], "IGE_LatentMemoryBarrier")
        self.assertEqual(nodes[345]["type"], "IGE_LatentMemoryBarrier")
        links = {int(link[0]): link for link in stage2["links"]}
        for sampler_id, barrier_id, decoder_id in ((67, 344, 96), (310, 345, 311)):
            sampler = nodes[sampler_id]
            latent_link_id = sampler["outputs"][0]["links"][0]
            self.assertEqual(int(links[int(latent_link_id)][3]), barrier_id)
            barrier_output_link = nodes[barrier_id]["outputs"][0]["links"][0]
            self.assertEqual(int(links[int(barrier_output_link)][3]), decoder_id)
            self.assertEqual(nodes[barrier_id]["widgets_values"], [True, True, True])
        self.assertEqual(report["stage2"]["sampler_count"], 2)
        self.assertEqual(report["stage2"]["memory_barrier_node_ids"], [344, 345])
        self.assertEqual(report["stage2"]["removed_unordered_terminal_purge_node_id"], 262)
        self.assertFalse(report["stage2"]["execution_allowed"])

    def test_build_does_not_mutate_source_workflow(self):
        before = json.dumps(self.original, sort_keys=True)
        build_staged_workflows(self.original)
        self.assertEqual(json.dumps(self.original, sort_keys=True), before)


    def test_committed_dev_workflow_artifacts_are_reproducible(self):
        stage1, stage2, report = build_staged_workflows(self.original)
        pack = ROOT / "docs/handoff/comfy-siax-return/pc_高清探"
        self.assertEqual(
            stage1,
            json.loads((pack / "workflow_ige_v03_dev_fp8_siax_stage1_export.json").read_text(encoding="utf-8")),
        )
        self.assertEqual(
            stage2,
            json.loads((pack / "workflow_ige_v03_dev_fp8_ige_stage2_gated_candidate.json").read_text(encoding="utf-8")),
        )
        self.assertEqual(
            report,
            json.loads((pack / "workflow_ige_v03_dev_fp8_staging_build_report.json").read_text(encoding="utf-8")),
        )

    def test_committed_local_workflow_artifacts_are_reproducible(self):
        local_path = ROOT / "docs/handoff/comfy-siax-return/pc_高清探/workflow_ige_v03_dev_fp8_local_gated_candidate.json"
        local_original = json.loads(local_path.read_text(encoding="utf-8"))
        stage1, stage2, report = build_staged_workflows(local_original)
        pack = ROOT / "docs/handoff/comfy-siax-return/pc_高清探"
        self.assertEqual(
            stage1,
            json.loads((pack / "workflow_ige_v03_dev_fp8_local_siax_stage1_export.json").read_text(encoding="utf-8")),
        )
        self.assertEqual(
            stage2,
            json.loads((pack / "workflow_ige_v03_dev_fp8_local_ige_stage2_gated_candidate.json").read_text(encoding="utf-8")),
        )
        self.assertEqual(
            report,
            json.loads((pack / "workflow_ige_v03_dev_fp8_local_staging_build_report.json").read_text(encoding="utf-8")),
        )


if __name__ == "__main__":
    unittest.main()
