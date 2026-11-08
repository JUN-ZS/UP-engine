from __future__ import annotations

import unittest

from tools.patch_comfy_siax_execution_gates import patch_workflow


def sample_workflow():
    return {
        "last_node_id": 10,
        "last_link_id": 3,
        "nodes": [
            {"id": 1, "type": "IGE_GlobalLogicCompiler", "pos": [0, 0], "order": 1,
             "inputs": [], "outputs": [{"name": "GLOBAL_CONTRACT", "type": "IGE_CONTRACT", "links": []}]},
            {"id": 2, "type": "VAEEncode", "pos": [100, 0], "order": 2,
             "inputs": [], "outputs": [{"name": "LATENT", "type": "LATENT", "links": [1, 2]}]},
            {"id": 3, "type": "SamplerCustomAdvanced", "title": "Baseline A", "pos": [300, 0], "order": 3,
             "inputs": [{"name": "latent_image", "type": "LATENT", "link": 1}],
             "outputs": [{"name": "output", "type": "LATENT", "links": []}]},
            {"id": 4, "type": "SamplerCustomAdvanced", "title": "Candidate B", "pos": [300, 300], "order": 4,
             "inputs": [{"name": "latent_image", "type": "LATENT", "link": 2}],
             "outputs": [{"name": "output", "type": "LATENT", "links": []}]},
        ],
        "links": [
            [1, 2, 0, 3, 0, "LATENT"],
            [2, 2, 0, 4, 0, "LATENT"],
        ],
        "extra": {},
    }


class ExecutionGateWorkflowPatchTests(unittest.TestCase):
    def test_all_samplers_get_a_gate_and_input_links_remain_resolvable(self):
        original = sample_workflow()
        patched, report = patch_workflow(original)
        self.assertEqual(len(report["patched_samplers"]), 2)
        nodes = {n["id"]: n for n in patched["nodes"]}
        links = {l[0]: l for l in patched["links"]}
        self.assertEqual(nodes[3]["inputs"][0]["link"], report["patched_samplers"][0]["gated_latent_link_id"])
        self.assertEqual(nodes[4]["inputs"][0]["link"], report["patched_samplers"][1]["gated_latent_link_id"])
        for sampler in (nodes[3], nodes[4]):
            latent_link = links[sampler["inputs"][0]["link"]]
            gate = nodes[latent_link[1]]
            self.assertEqual(gate["type"], "IGE_ExecutionAuthorizationGate")
            self.assertEqual(gate["widgets_values"][0], "{}")
        for link in patched["links"]:
            self.assertIn(link[1], nodes)
            self.assertIn(link[3], nodes)
        self.assertEqual(len(original["nodes"]), 4)

    def test_patch_is_idempotent(self):
        once, _ = patch_workflow(sample_workflow())
        twice, report = patch_workflow(once)
        self.assertEqual(report["patched_samplers"], [])
        self.assertEqual(len(twice["nodes"]), len(once["nodes"]))
        self.assertEqual(len(twice["links"]), len(once["links"]))

    def test_missing_compiler_fails_closed(self):
        graph = sample_workflow()
        graph["nodes"] = [n for n in graph["nodes"] if n["type"] != "IGE_GlobalLogicCompiler"]
        with self.assertRaisesRegex(ValueError, "exactly one"):
            patch_workflow(graph)


if __name__ == "__main__":
    unittest.main()
