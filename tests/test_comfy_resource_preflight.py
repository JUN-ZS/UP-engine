from __future__ import annotations

import unittest

from tools.comfy_resource_preflight import analyze_workflow, evaluate_preflight


def sample_workflow(gated=True, split_before_vae=True):
    nodes = [
        {"id": 1, "type": "TTP_Tile_image_size", "widgets_values": [2, 3, 0.05], "inputs": [], "outputs": [
            {"name": "tile_width", "type": "INT", "links": [1]},
            {"name": "tile_height", "type": "INT", "links": [2]}]},
        {"id": 2, "type": "TTP_Image_Tile_Batch", "inputs": [
            {"name": "tile_width", "type": "INT", "link": 1},
            {"name": "tile_height", "type": "INT", "link": 2}], "outputs": [
            {"name": "IMAGES", "type": "IMAGE", "links": [3]}]},
        {"id": 4, "type": "VAEEncode", "inputs": [
            {"name": "pixels", "type": "IMAGE", "link": 4 if split_before_vae else 3}], "outputs": [
            {"name": "LATENT", "type": "LATENT", "links": [5 if gated else 6]}]},
    ]
    links = [
        [1, 1, 0, 2, 0, "INT"],
        [2, 1, 1, 2, 1, "INT"],
    ]
    if split_before_vae:
        nodes.append({
            "id": 3,
            "type": "easy imageBatchToImageList",
            "inputs": [{"name": "image", "type": "IMAGE", "link": 3}],
            "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [4]}],
        })
        links.extend([
            [3, 2, 0, 3, 0, "IMAGE"],
            [4, 3, 0, 4, 0, "IMAGE"],
        ])
    else:
        links.append([3, 2, 0, 4, 0, "IMAGE"])

    if gated:
        nodes.append({
            "id": 5, "type": "IGE_ExecutionAuthorizationGate",
            "inputs": [{"name": "latent", "type": "LATENT", "link": 5}],
            "outputs": [{"name": "LATENT", "type": "LATENT", "links": [6]}],
        })
        nodes.append({
            "id": 6, "type": "SamplerCustomAdvanced",
            "inputs": [{"name": "latent_image", "type": "LATENT", "link": 6}],
            "outputs": [],
        })
        links.extend([
            [5, 4, 0, 5, 0, "LATENT"],
            [6, 5, 0, 6, 0, "LATENT"],
        ])
    else:
        nodes.append({
            "id": 6, "type": "SamplerCustomAdvanced",
            "inputs": [{"name": "latent_image", "type": "LATENT", "link": 5}],
            "outputs": [],
        })
        links.append([5, 4, 0, 6, 0, "LATENT"])

    return {"nodes": nodes, "links": links}


class ComfyResourcePreflightTests(unittest.TestCase):
    def test_recognizes_six_tiles_split_to_single_image_list_before_vae(self):
        graph = analyze_workflow(sample_workflow(gated=True, split_before_vae=True))
        sampler = graph["samplers"][0]
        self.assertTrue(sampler["execution_gate_present"])
        self.assertEqual(sampler["upstream_ttp_batches"][0]["configuration_derived_tile_count"], 6)
        self.assertTrue(sampler["list_split_before_vae"])
        self.assertEqual(sampler["list_splitter_node_ids"], [3])
        self.assertEqual(sampler["execution_semantics_evidence"], "candidate_sequential_map")
        self.assertFalse(sampler["static_batch_warning"])

    def test_blocks_multi_tile_path_without_pre_vae_list_split(self):
        graph = analyze_workflow(sample_workflow(gated=True, split_before_vae=False))
        sampler = graph["samplers"][0]
        self.assertFalse(sampler["list_split_before_vae"])
        self.assertTrue(sampler["static_batch_warning"])
        result = evaluate_preflight(
            graph,
            {"cuda_available": True, "vram_free_mb": 7000, "ram_available_mb": 24000},
            execution_allowed=True,
            operator_authorized=True,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("TTP_BATCH_NOT_SPLIT_BEFORE_VAE", result["reasons"])
        self.assertFalse(result["queue_submission"])

    def test_blocks_missing_gate_low_memory_and_missing_authorization(self):
        graph = analyze_workflow(sample_workflow(gated=False, split_before_vae=True))
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
