import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from ige.read.pipeline import run_read
from ige.read.providers.base import MaskProposal


class FakeProvider:
    provider_id = "test.fake"

    def __init__(self, shape):
        self.shape = shape

    def segment_text(self, image_path, prompts):
        height, width = self.shape
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[2:6, 3:8] = 255
        return [MaskProposal("fake-object-001", prompts[0], 0.91, mask)]


class ReadPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image_path = self.root / "base.png"
        Image.new("RGB", (20, 16), (80, 110, 140)).save(self.image_path)

    def tearDown(self):
        self.temp.cleanup()

    def _write_json(self, name, raw):
        path = self.root / name
        path.write_text(json.dumps(raw), encoding="utf-8")
        return path

    def _regions(self, entries):
        return self._write_json("regions.json", {
            "coordinate_space": "normalized_0_1",
            "regions": entries
        })

    def test_only_human_editable_region_becomes_writable(self):
        regions = self._regions([
            {
                "id": "edit-zone", "label": "edit zone", "semantic_type": "garment",
                "permission": "editable", "tags": ["object"],
                "polygon": [[0.10, 0.10], [0.45, 0.10], [0.45, 0.45], [0.10, 0.45]]
            },
            {
                "id": "face", "label": "face", "semantic_type": "face",
                "permission": "protected", "tags": ["object", "identity_anchor"],
                "polygon": [[0.65, 0.10], [0.90, 0.10], [0.90, 0.40], [0.65, 0.40]]
            }
        ])
        out = self.root / "read-output"
        report = run_read(self.image_path, out, regions_path=regions)
        editable = np.asarray(Image.open(out / "masks" / "editable.png"))
        protected = np.asarray(Image.open(out / "masks" / "protected_effective.png"))
        self.assertGreater(np.count_nonzero(editable), 0)
        self.assertEqual(np.count_nonzero((editable > 0) & (protected > 0)), 0)
        self.assertEqual(report["mask_policy"]["effective_protected_pixels"],
                         20 * 16 - report["mask_policy"]["editable_pixels"])
        self.assertEqual(report["semantic_segmentation"]["status"], "not_run")
        self.assertEqual(report["regions"][0]["semantic_type"], "garment")
        self.assertEqual(report["regions"][0]["permission"], "editable")
        self.assertTrue((out / "preview.png").is_file())
        self.assertTrue((out / "READ_REPORT.md").is_file())

    def test_model_proposal_does_not_create_edit_permission(self):
        out = self.root / "proposal-output"
        report = run_read(
            self.image_path, out,
            provider=FakeProvider((16, 20)),
            prompts=["silver helmet"]
        )
        editable = np.asarray(Image.open(out / "masks" / "editable.png"))
        proposal = np.asarray(Image.open(out / report["proposals"][0]["mask"]))
        self.assertEqual(int(np.count_nonzero(editable)), 0)
        self.assertGreater(int(np.count_nonzero(proposal)), 0)
        self.assertFalse(report["proposals"][0]["edit_permission"])
        self.assertEqual(report["proposals"][0]["status"], "unreviewed_proposal")

    def test_editable_protected_overlap_is_rejected(self):
        regions = self._regions([
            {
                "id": "edit", "label": "edit", "semantic_type": "garment",
                "permission": "editable",
                "polygon": [[0.1, 0.1], [0.8, 0.1], [0.8, 0.8], [0.1, 0.8]]
            },
            {
                "id": "protect", "label": "protect", "semantic_type": "hand",
                "permission": "protected",
                "polygon": [[0.4, 0.4], [0.9, 0.4], [0.9, 0.9], [0.4, 0.9]]
            }
        ])
        with self.assertRaisesRegex(ValueError, "overlap"):
            run_read(self.image_path, self.root / "overlap-output", regions_path=regions)

    def test_nonempty_output_directory_is_not_overwritten_by_default(self):
        out = self.root / "existing-output"
        out.mkdir()
        (out / "keep.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            run_read(self.image_path, out)
        self.assertEqual((out / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_provider_mask_shape_mismatch_is_rejected(self):
        class WrongShapeProvider:
            provider_id = "test.wrong-shape"
            def segment_text(self, image_path, prompts):
                return [MaskProposal("wrong", prompts[0], 0.8, np.zeros((2, 2), dtype=np.uint8))]
        with self.assertRaisesRegex(ValueError, "refusing implicit resize"):
            run_read(
                self.image_path, self.root / "wrong-shape",
                provider=WrongShapeProvider(), prompts=["object"]
            )

    def test_relations_are_serialized_as_a_graph(self):
        regions = self._regions([
            {
                "id": "left", "label": "left end face", "semantic_type": "cylindrical_end_face",
                "permission": "protected", "tags": ["object", "contact_surface"],
                "polygon": [[0.05, 0.2], [0.35, 0.2], [0.35, 0.8], [0.05, 0.8]]
            },
            {
                "id": "right", "label": "right end face", "semantic_type": "cylindrical_end_face",
                "permission": "protected", "tags": ["object", "contact_surface"],
                "polygon": [[0.65, 0.2], [0.95, 0.2], [0.95, 0.8], [0.65, 0.8]]
            },
            {
                "id": "contact", "label": "contact zone", "semantic_type": "contact_boundary",
                "permission": "protected", "tags": ["context", "contact_evidence"],
                "polygon": [[0.45, 0.4], [0.55, 0.4], [0.55, 0.6], [0.45, 0.6]]
            }
        ])
        relations = self._write_json("relations.json", {
            "version": "0.1.0",
            "relations": [{
                "id": "end-face-contact",
                "subject_region_id": "left",
                "predicate": "contacts_at",
                "object_region_id": "right",
                "status": "human_verified",
                "source": "human",
                "confidence": 1.0,
                "evidence": "Both cylindrical end faces visibly meet at the marked contact zone.",
                "evidence_region_id": "contact",
                "details": {
                    "subject_surface": "cylindrical_end_face",
                    "object_surface": "cylindrical_end_face"
                }
            }]
        })
        report = run_read(
            self.image_path, self.root / "graph-output",
            regions_path=regions, relations_path=relations
        )
        self.assertEqual(report["scene_graph"]["human_verified_relation_count"], 1)
        self.assertEqual(report["scene_graph"]["relations"][0]["predicate"], "contacts_at")
        self.assertEqual(report["scene_graph"]["relations"][0]["details"]["subject_surface"],
                         "cylindrical_end_face")
