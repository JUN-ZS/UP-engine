import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from ige.read.geometry import GeometryContractError, compile_generation_packet


class GenerationPacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run_dir = self.root / "read-run"
        (self.run_dir / "masks" / "regions").mkdir(parents=True)
        self.width, self.height = 10, 8
        self.base_path = self.root / "base.png"
        Image.new("RGB", (self.width, self.height), (40, 70, 90)).save(self.base_path)
        self.base_sha = self._sha(self.base_path)
        self._mask("region-armor.png", [(1, 1), (2, 1), (1, 2)])
        self._mask("region-cloak.png", [(7, 1), (8, 1)])
        self._mask("region-face.png", [(4, 1)])
        self.analysis_path = self.run_dir / "analysis.json"
        self._write_analysis()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _mask(self, name, pixels):
        mask = np.zeros((self.height, self.width), dtype=np.uint8)
        for x, y in pixels:
            mask[y, x] = 255
        path = self.run_dir / "masks" / "regions" / name
        Image.fromarray(mask, mode="L").save(path)
        return self._sha(path)

    def _write_analysis(self):
        analysis = {
            "read_version": "0.3.0",
            "source": {
                "path": str(self.base_path),
                "sha256": self.base_sha,
                "width": self.width,
                "height": self.height,
                "orientation": "EXIF-transposed-to-display-orientation"
            },
            "regions": [
                {"id": "armor", "label": "armor", "semantic_type": "garment",
                 "permission": "editable", "tags": ["object"]},
                {"id": "cloak", "label": "cloak", "semantic_type": "garment",
                 "permission": "editable", "tags": ["object"]},
                {"id": "face", "label": "face", "semantic_type": "face",
                 "permission": "protected", "tags": ["object", "identity_anchor"]}
            ],
            "region_masks": [
                {"id": "armor", "mask": "masks/regions/region-armor.png",
                 "sha256": self._sha(self.run_dir / "masks/regions/region-armor.png")},
                {"id": "cloak", "mask": "masks/regions/region-cloak.png",
                 "sha256": self._sha(self.run_dir / "masks/regions/region-cloak.png")},
                {"id": "face", "mask": "masks/regions/region-face.png",
                 "sha256": self._sha(self.run_dir / "masks/regions/region-face.png")}
            ],
            "scene_graph": {
                "relations": [
                    {
                        "id": "verified-contact", "subject_region_id": "armor",
                        "predicate": "contacts_at", "object_region_id": "face",
                        "status": "human_verified", "source": "human",
                        "confidence": 1.0, "evidence": "Visible contact evidence.",
                        "details": {"subject_surface": "armor_edge", "object_surface": "face_guard"}
                    },
                    {
                        "id": "candidate-occlusion", "subject_region_id": "cloak",
                        "predicate": "occludes", "object_region_id": "armor",
                        "status": "candidate", "source": "model",
                        "confidence": 0.4, "evidence": "Possible overlap."
                    }
                ]
            }
        }
        self.analysis_path.write_text(json.dumps(analysis), encoding="utf-8")

    def _compile(self, out, targets=None, base=None):
        return compile_generation_packet(
            self.analysis_path,
            out,
            objective="retexture chest armor",
            target_region_ids=targets or ["armor"],
            base_image_path=base,
        )

    def test_target_mask_is_only_selected_region_not_all_editable_regions(self):
        out = self.root / "generation-task"
        packet = self._compile(out)
        generation = np.asarray(Image.open(out / "generation_mask.png"))
        protected = np.asarray(Image.open(out / "protected_mask.png"))
        self.assertEqual(np.count_nonzero(generation), 3)
        self.assertEqual(np.count_nonzero(protected), 80 - 3)
        self.assertEqual(np.count_nonzero((generation > 0) & (protected > 0)), 0)
        self.assertEqual(packet["targets"][0]["region_id"], "armor")
        # A separate editable cloak region remains protected in this task.
        self.assertEqual(int(generation[1, 7]), 0)
        self.assertEqual(int(protected[1, 7]), 255)
        self.assertEqual(packet["base"]["sha256"], self.base_sha)

    def test_only_human_verified_relations_become_geometry_locks(self):
        packet = self._compile(self.root / "task-2")
        locks = packet["geometry_locks"]
        self.assertEqual([r["id"] for r in locks["relations"]], ["verified-contact"])
        self.assertEqual(locks["candidate_relations_excluded"], ["candidate-occlusion"])
        self.assertEqual(locks["dimensionality"], "2d_image_plane_assertions_only")
        self.assertIn("face", locks["protected_region_ids"])

    def test_protected_target_is_rejected(self):
        with self.assertRaisesRegex(GeometryContractError, "not human-approved editable"):
            self._compile(self.root / "bad-task", ["face"])

    def test_unknown_target_is_rejected(self):
        with self.assertRaisesRegex(GeometryContractError, "unknown target"):
            self._compile(self.root / "bad-task", ["missing"])

    def test_tampered_mask_integrity_is_rejected(self):
        Image.new("L", (self.width, self.height), 255).save(
            self.run_dir / "masks" / "regions" / "region-armor.png"
        )
        with self.assertRaisesRegex(GeometryContractError, "integrity check failed"):
            self._compile(self.root / "bad-task")

    def test_path_traversal_in_manifest_is_rejected(self):
        raw = json.loads(self.analysis_path.read_text(encoding="utf-8"))
        raw["region_masks"][0]["mask"] = "../../outside.png"
        self.analysis_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(GeometryContractError, "escapes the run directory"):
            self._compile(self.root / "bad-task")

    def test_changed_base_image_is_rejected(self):
        Image.new("RGB", (self.width, self.height), (0, 0, 0)).save(self.base_path)
        with self.assertRaisesRegex(GeometryContractError, "BASE SHA-256 does not match"):
            self._compile(self.root / "bad-task")

    def test_missing_base_image_is_rejected(self):
        self.base_path.unlink()
        with self.assertRaisesRegex(GeometryContractError, "BASE image is unavailable"):
            self._compile(self.root / "bad-task")

    def test_model_cannot_enter_human_verified_geometry_locks(self):
        raw = json.loads(self.analysis_path.read_text(encoding="utf-8"))
        raw["scene_graph"]["relations"][0]["source"] = "model"
        self.analysis_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(GeometryContractError, "model-originated relation"):
            self._compile(self.root / "bad-task")

    def test_duplicate_target_ids_are_rejected(self):
        with self.assertRaisesRegex(GeometryContractError, "cannot contain duplicates"):
            self._compile(self.root / "bad-task", ["armor", "armor"])

    def test_nonempty_output_dir_is_not_overwritten_by_default(self):
        out = self.root / "existing"
        out.mkdir()
        (out / "keep.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self._compile(out)
        self.assertEqual((out / "keep.txt").read_text(encoding="utf-8"), "keep")


    def test_part_of_cycle_in_human_verified_locks_is_rejected(self):
        raw = json.loads(self.analysis_path.read_text(encoding="utf-8"))
        raw["scene_graph"]["relations"] = [
            {
                "id": "armor-part-of-face", "subject_region_id": "armor",
                "predicate": "part_of", "object_region_id": "face",
                "status": "human_verified", "source": "human",
                "evidence": "Human-verified structural relation."
            },
            {
                "id": "face-part-of-armor", "subject_region_id": "face",
                "predicate": "part_of", "object_region_id": "armor",
                "status": "human_verified", "source": "human",
                "evidence": "Contradictory human-verified structural relation."
            }
        ]
        self.analysis_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(GeometryContractError, "part_of relations contain a cycle"):
            self._compile(self.root / "bad-task")

    def test_human_verified_contact_without_both_surfaces_is_rejected(self):
        raw = json.loads(self.analysis_path.read_text(encoding="utf-8"))
        raw["scene_graph"]["relations"][0]["details"] = {
            "subject_surface": "armor_edge"
        }
        self.analysis_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(GeometryContractError, "must name both surfaces"):
            self._compile(self.root / "bad-task")


    def test_explicit_path_argument_for_base_is_supported(self):
        packet = self._compile(self.root / "explicit-base", base=self.base_path)
        self.assertEqual(packet["base"]["sha256"], self.base_sha)
