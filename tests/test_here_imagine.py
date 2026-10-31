import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from ige.adapters.here_imagine import HereImagineAdapter, HereImagineError
from ige.adapters.registration import require_registration_for_composite
from ige.reconstruction import composite_candidate


class HereImagineAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "base.png"
        Image.new("RGB", (16, 12), color=(50, 60, 70)).save(self.base)
        self.base_sha = hashlib.sha256(self.base.read_bytes()).hexdigest()
        self.packet_dir = self.root / "packet"
        self.packet_dir.mkdir()
        generation = np.zeros((12, 16), dtype=np.uint8)
        generation[2:6, 3:8] = 255
        protected = 255 - generation
        Image.fromarray(generation, mode="L").save(self.packet_dir / "generation_mask.png")
        Image.fromarray(protected, mode="L").save(self.packet_dir / "protected_mask.png")
        self.packet = {
            "packet_version": "0.1.0",
            "task_id": "here-test",
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

    def test_prepare_job_is_primary_and_does_not_generate(self):
        out = self.root / "job"
        adapter = HereImagineAdapter()
        job = adapter.prepare_job(self.packet_path, self.base, out)
        self.assertEqual(job.backend, "here")
        self.assertEqual(job.adapter_id, "grok.imagine.here")
        self.assertEqual(job.status, "awaiting_here_imagine_candidate")
        self.assertTrue(Path(job.prompt_path).is_file())
        self.assertTrue(Path(job.job_path).is_file())
        data = json.loads(Path(job.job_path).read_text(encoding="utf-8"))
        self.assertFalse(data["claims"]["generated"])
        self.assertFalse(data["claims"]["final_acceptance"])
        self.assertIn("controlled image-editing task", job.prompt)
        # BASE untouched
        self.assertEqual(hashlib.sha256(self.base.read_bytes()).hexdigest(), self.base_sha)

    def test_ingest_candidate_persists_bytes_and_registration(self):
        source = self.root / "here-produced.png"
        Image.new("RGB", (16, 12), color=(200, 10, 10)).save(source)
        out = self.root / "ingested"
        adapter = HereImagineAdapter()
        artifact = adapter.ingest_candidate(
            self.packet_path, self.base, source, out, request_id="asset-demo"
        )
        self.assertEqual(artifact.backend, "here")
        self.assertTrue(Path(artifact.candidate_path).is_file())
        self.assertEqual(artifact.registration_quality, "pending_dimension_match_only")
        meta = json.loads(Path(artifact.metadata_path).read_text(encoding="utf-8"))
        self.assertFalse(meta["claims"]["pixel_preserving"])
        self.assertEqual(meta["request_id"], "asset-demo")

    def test_ingest_wrong_size_marks_registration_failed(self):
        source = self.root / "bad.png"
        Image.new("RGB", (32, 12), color=(200, 10, 10)).save(source)
        adapter = HereImagineAdapter()
        artifact = adapter.ingest_candidate(
            self.packet_path, self.base, source, self.root / "bad-out"
        )
        self.assertEqual(artifact.registration_quality, "failed")
        with self.assertRaises(Exception):
            require_registration_for_composite(self.base, artifact.candidate_path)

    def test_ingested_matching_candidate_composites_with_zero_protected_leak(self):
        source = self.root / "cand.png"
        Image.new("RGB", (16, 12), color=(220, 30, 40)).save(source)
        out = self.root / "ok"
        artifact = HereImagineAdapter().ingest_candidate(
            self.packet_path, self.base, source, out
        )
        composite = self.root / "composite.png"
        audit = composite_candidate(
            self.packet_path,
            self.base,
            artifact.candidate_path,
            composite,
            candidate_model_id="grok.imagine.here",
        )
        self.assertEqual(audit["pixel_diff"]["changed_pixels_outside_authorized_region"], 0)
        self.assertFalse(audit["final_acceptance"])

    def test_base_hash_mismatch_rejected_on_prepare(self):
        other = self.root / "other.png"
        Image.new("RGB", (16, 12), color=(1, 1, 1)).save(other)
        with self.assertRaises(HereImagineError):
            HereImagineAdapter().prepare_job(
                self.packet_path, other, self.root / "fail"
            )
