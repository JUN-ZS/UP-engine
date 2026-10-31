import base64
import hashlib
import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from ige.adapters.registration import (
    RegistrationError,
    assess_registration,
    require_registration_for_composite,
)
from ige.adapters.xai_imagine import GrokImagineAdapter, GrokImagineError
from ige.reconstruction import composite_candidate


def _png_bytes(width=16, height=12, color=(10, 20, 30)):
    buf = BytesIO()
    Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
    return buf.getvalue()


class RegistrationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "base.png"
        self.same = self.root / "same.png"
        self.diff = self.root / "diff.png"
        Image.new("RGB", (20, 10), color=(1, 2, 3)).save(self.base)
        Image.new("RGB", (20, 10), color=(9, 9, 9)).save(self.same)
        Image.new("RGB", (21, 10), color=(9, 9, 9)).save(self.diff)

    def tearDown(self):
        self.temp.cleanup()

    def test_matching_dimensions_are_pending_not_accepted(self):
        report = assess_registration(self.base, self.same)
        self.assertTrue(report.dimensions_match)
        self.assertTrue(report.allowed_for_compositor)
        self.assertEqual(report.registration_quality, "pending_dimension_match_only")
        self.assertEqual(report.transformation["type"], "identity")
        self.assertFalse(report.transformation["applied"])

    def test_dimension_mismatch_blocks_compositor(self):
        report = assess_registration(self.base, self.diff)
        self.assertFalse(report.allowed_for_compositor)
        self.assertEqual(report.registration_quality, "failed")
        with self.assertRaises(RegistrationError):
            require_registration_for_composite(self.base, self.diff)


class GrokImagineAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "base.png"
        Image.new("RGB", (16, 12), color=(50, 60, 70)).save(self.base)
        self.base_sha = hashlib.sha256(self.base.read_bytes()).hexdigest()
        self.packet_dir = self.root / "packet"
        self.packet_dir.mkdir()
        # Minimal packet for imagine path
        generation = np.zeros((12, 16), dtype=np.uint8)
        generation[2:6, 3:8] = 255
        protected = 255 - generation
        Image.fromarray(generation, mode="L").save(self.packet_dir / "generation_mask.png")
        Image.fromarray(protected, mode="L").save(self.packet_dir / "protected_mask.png")
        self.packet = {
            "packet_version": "0.1.0",
            "task_id": "imagine-test",
            "objective": "retexture the marked region while preserving silhouette",
            "base": {
                "sha256": self.base_sha,
                "width": 16,
                "height": 12,
                "orientation": "EXIF-transposed-to-display-orientation",
            },
            "targets": [
                {
                    "region_id": "armor",
                    "label": "armor plate",
                    "semantic_type": "garment",
                    "permission": "editable",
                }
            ],
            "pixel_authorization": {
                "source": "human_region_annotation",
                "generation_mask": "generation_mask.png",
                "generation_mask_sha256": hashlib.sha256(
                    (self.packet_dir / "generation_mask.png").read_bytes()
                ).hexdigest(),
                "protected_mask": "protected_mask.png",
                "protected_mask_sha256": hashlib.sha256(
                    (self.packet_dir / "protected_mask.png").read_bytes()
                ).hexdigest(),
                "generation_pixels": int(np.count_nonzero(generation)),
                "protected_pixels": int(np.count_nonzero(protected)),
                "rule": "only selected editable region",
                "target_mask_inputs": [],
            },
            "geometry_locks": {
                "coordinate_space": "source_display_pixels",
                "dimensionality": "2d_image_plane_assertions_only",
                "relations": [],
                "protected_region_ids": ["face"],
                "candidate_relations_excluded": [],
                "limitation": "2d only",
            },
            "acceptance_requirements": ["pixel preservation"],
            "provenance": {
                "read_analysis_path": "analysis.json",
                "read_analysis_sha256": "0" * 64,
                "read_version": "0.3.0",
                "model_proposals_grant_no_permission": True,
            },
        }
        self.packet_path = self.packet_dir / "generation_packet.json"
        self.packet_path.write_text(json.dumps(self.packet), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_api_key_fails(self):
        env = {k: v for k, v in os.environ.items() if k != "XAI_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(GrokImagineError, "XAI_API_KEY"):
                GrokImagineAdapter(api_key="")

    def test_mock_generate_persists_binary_and_hash(self):
        png = _png_bytes(16, 12, color=(200, 10, 10))
        b64 = base64.b64encode(png).decode("ascii")

        def transport(url, payload):
            self.assertIn("/images/edits", url)
            self.assertEqual(payload["response_format"], "b64_json")
            self.assertEqual(payload["model"], "grok-imagine-image-2.0")
            # secondary API path
            self.assertIn("image", payload)
            return {
                "data": [{"b64_json": b64, "mime_type": "image/png"}],
                "id": "img_req_1",
            }, {"x-request-id": "img-req-1"}

        out = self.root / "candidate-out"
        adapter = GrokImagineAdapter(api_key="k", transport=transport)
        artifact = adapter.generate_from_packet(self.packet_path, self.base, out)
        self.assertTrue(Path(artifact.candidate_path).is_file())
        self.assertEqual(artifact.candidate_sha256, hashlib.sha256(png).hexdigest())
        self.assertEqual(artifact.registration_quality, "pending_dimension_match_only")
        meta = json.loads(Path(artifact.metadata_path).read_text(encoding="utf-8"))
        self.assertFalse(meta["claims"]["final_acceptance"])
        self.assertFalse(meta["claims"]["pixel_preserving"])
        # BASE not overwritten
        self.assertEqual(hashlib.sha256(self.base.read_bytes()).hexdigest(), self.base_sha)

    def test_registration_size_error_refuses_composite_gate(self):
        png = _png_bytes(32, 12, color=(200, 10, 10))  # wrong size
        b64 = base64.b64encode(png).decode("ascii")

        def transport(url, payload):
            return {"data": [{"b64_json": b64}]}, {}

        out = self.root / "candidate-bad"
        adapter = GrokImagineAdapter(api_key="k", transport=transport)
        artifact = adapter.generate_from_packet(self.packet_path, self.base, out)
        self.assertEqual(artifact.registration_quality, "failed")
        with self.assertRaises(RegistrationError):
            require_registration_for_composite(self.base, artifact.candidate_path)

    def test_protected_pixel_zero_leakage_after_matching_candidate(self):
        # Candidate same size; red everywhere
        candidate_arr = np.full((12, 16, 3), [220, 30, 40], dtype=np.uint8)
        candidate_path = self.root / "cand.png"
        Image.fromarray(candidate_arr, mode="RGB").save(candidate_path)
        output = self.root / "composite.png"
        report = require_registration_for_composite(self.base, candidate_path)
        self.assertTrue(report.allowed_for_compositor)
        audit = composite_candidate(
            self.packet_path,
            self.base,
            candidate_path,
            output,
            candidate_model_id="xai.grok.imagine",
        )
        self.assertEqual(audit["pixel_diff"]["changed_pixels_outside_authorized_region"], 0)
        self.assertFalse(audit["final_acceptance"])

    def test_url_only_response_is_rejected(self):
        def transport(url, payload):
            return {"data": [{"url": "https://example.invalid/tmp.jpg"}]}, {}

        adapter = GrokImagineAdapter(api_key="k", transport=transport)
        with self.assertRaisesRegex(GrokImagineError, "b64_json"):
            adapter.generate_from_packet(
                self.packet_path, self.base, self.root / "out-url"
            )
