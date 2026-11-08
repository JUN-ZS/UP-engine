from __future__ import annotations

import unittest

from tools.comfy_resource_preflight import analyze_workflow, evaluate_preflight


def sample_workflow(gated=True):
    gate_type = "IGE_ExecutionAuthorizationGate" if gated else "VAEEncode"
    return {
        "nodes": [
            {"id": 1, "type": "TTP_Tile_image_size", "widgets_values": [2, 3, 0.05], "inputs": [], "outputs": [
                {"name": "tile_width", "type": "INT", "links": [1]},
                {"name": "tile_height", "type": "INT", "links": [2]}]},
            {"id": 2, "type": "TTP_Image_Tile_Batch", "inputs": [
                {"name": "tile_width", "type": "INT", "link": 1},
                {"name": "tile_height", "type": "INT", "link": 2}], "outputs": []},
            {"id": 3, "type": "VAEEncode", "inputs": [
                {"name": "pixels", "type": "IMAGE", "link": 3}], "outputs": [
                {"name": "LATENT", "type": "LATENT", "links": [4]}]},
            {"id": 4, "type": gate_type, "inputs": [
                {"name": "latent", "type": "LATENT", "link": 4}], "outputs": [
                {"name": "LATENT", "type": "LATENT", "links": [5]}]},
            {"id": 5, "type": "SamplerCustomAdvanced", "inputs": [
                {"name": "latent_image", "type": "LATENT", "link": 5}], "outputs": []},
        ],
        "links": [
            [1, 1, 0, 2, 0, "INT"],
            [2, 1, 1, 2, 1, "INT"],
            [3, 2, 0, 3, 0, "IMAGE"],
            [4, 3, 0, 4, 0, "LATENT"],
            [5, 4, 0, 5, 0, "LATENT"],
        ],
    }


class ComfyResourcePreflightTests(unittest.TestCase):
    def test_finds_six_tile_batch_and_direct_gate(self):
        graph = analyze_workflow(sample_workflow(True))
        sampler = graph["samplers"][0]
        self.assertTrue(sampler["execution_gate_present"])
        self.assertEqual(sampler["upstream_ttp_batches"][0]["configuration_derived_tile_count"], 6)
        self.assertTrue(sampler["static_batch_warning"])

    def test_blocks_multi_tile_batch_even_when_resources_are_sufficient(self):
        graph = analyze_workflow(sample_workflow(True))
        result = evaluate_preflight(
            graph,
            {"cuda_available": True, "vram_free_mb": 7000, "ram_available_mb": 24000},
            execution_allowed=True,
            operator_authorized=True,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("MULTI_TILE_BATCH_NOT_SERIALIZED", result["reasons"])
        self.assertFalse(result["queue_submission"])

    def test_blocks_missing_gate_low_memory_and_missing_authorization(self):
        graph = analyze_workflow(sample_workflow(False))
        result = evaluate_preflight(
            graph,
            {"cuda_available": True, "vram_free_mb": 1000, "ram_available_mb": 4000},
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SAMPLER_PATH_NOT_GEOMETRY_GATED", result["reasons"])
        self.assertIn("FREE_VRAM_BELOW_RESERVE", result["reasons"])
        self.assertIn("FREE_RAM_BELOW_RESERVE", result["reasons"])
        self.assertIn("EXECUTION_NOT_AUTHORIZED", result["reasons"])
        self.assertIn("OPERATOR_NOT_AUTHORIZED", result["reasons"])


if __name__ == "__main__":
    unittest.main()
