import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from ige.reconstruction import ReconstructionError, composite_candidate


class ReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.packet_dir = self.root / "packet"
        self.packet_dir.mkdir()
        self.base_path = self.root / "base.png"
        self.candidate_path = self.root / "candidate.png"
        self.packet_path = self.packet_dir / "generation_packet.json"
        self.width, self.height = 12, 8

        base = np.full((self.height, self.width, 3), [50, 70, 90], dtype=np.uint8)
        candidate = np.full((self.height, self.width, 3), [220, 30, 40], dtype=np.uint8)
        Image.fromarray(base, mode="RGB").save(self.base_path)
        Image.fromarray(candidate, mode="RGB").save(self.candidate_path)

        generation = np.zeros((self.height, self.width), dtype=np.uint8)
        generation[2:4, 3:5] = 255
        protected = 255 - generation
        self.generation_path = self.packet_dir / "generation_mask.png"
        self.protected_path = self.packet_dir / "protected_mask.png"
        Image.fromarray(generation, mode="L").save(self.generation_path)
        Image.fromarray(protected, mode="L").save(self.protected_path)
        self.generation_pixels = int(np.count_nonzero(generation))

        self.packet = {
            "packet_version": "0.1.0",
            "task_id": "test-retexture",
            "base": {
                "sha256": self._sha(self.base_path),
                "width": self.width,
                "height": self.height
            },
            "pixel_authorization": {
                "generation_mask": "generation_mask.png",
                "generation_mask_sha256": self._sha(self.generation_path),
                "protected_mask": "protected_mask.png",
                "protected_mask_sha256": self._sha(self.protected_path),
                "generation_pixels": self.generation_pixels
            }
        }
        self._write_packet()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_packet(self):
        self.packet_path.write_text(json.dumps(self.packet), encoding="utf-8")

    def test_only_authorized_pixels_are_copied_and_verified_after_save(self):
        output = self.root / "composite.png"
        audit = composite_candidate(
            self.packet_path, self.base_path, self.candidate_path, output,
            candidate_model_id="test.generator"
        )
        base = np.asarray(Image.open(self.base_path).convert("RGB"))
        candidate = np.asarray(Image.open(self.candidate_path).convert("RGB"))
        result = np.asarray(Image.open(output).convert("RGB"))
        protected = np.asarray(Image.open(self.protected_path)) > 0
        generation = np.asarray(Image.open(self.generation_path)) > 0
        self.assertTrue(np.array_equal(result[protected], base[protected]))
        self.assertTrue(np.array_equal(result[generation], candidate[generation]))
        self.assertEqual(audit["pixel_diff"]["changed_pixels_outside_authorized_region"], 0)
        self.assertEqual(audit["pixel_diff"]["changed_pixels_inside_authorized_region"], self.generation_pixels)
        self.assertEqual(audit["hard_gates"]["protected_region_pixel_preservation"], "pass")
        self.assertEqual(audit["hard_gates"]["identity"], "pending")
        self.assertFalse(audit["final_acceptance"])
        self.assertTrue(Path(str(output) + ".audit.json").is_file())

    def test_base_hash_mismatch_is_rejected(self):
        Image.new("RGB", (self.width, self.height), (1, 2, 3)).save(self.base_path)
        with self.assertRaisesRegex(ReconstructionError, "BASE SHA-256"):
            composite_candidate(self.packet_path, self.base_path, self.candidate_path, self.root / "out.png")

    def test_generation_mask_hash_mismatch_is_rejected(self):
        Image.new("L", (self.width, self.height), 0).save(self.generation_path)
        with self.assertRaisesRegex(ReconstructionError, "generation mask SHA-256"):
            composite_candidate(self.packet_path, self.base_path, self.candidate_path, self.root / "out.png")

    def test_inconsistent_protected_mask_is_rejected(self):
        Image.new("L", (self.width, self.height), 0).save(self.protected_path)
        self.packet["pixel_authorization"]["protected_mask_sha256"] = self._sha(self.protected_path)
        self._write_packet()
        with self.assertRaisesRegex(ReconstructionError, "exact complement"):
            composite_candidate(self.packet_path, self.base_path, self.candidate_path, self.root / "out.png")

    def test_candidate_size_mismatch_is_not_silently_resized(self):
        Image.new("RGB", (4, 4), (200, 0, 0)).save(self.candidate_path)
        with self.assertRaisesRegex(ReconstructionError, "automatic resize is forbidden"):
            composite_candidate(self.packet_path, self.base_path, self.candidate_path, self.root / "out.png")

    def test_lossy_output_format_is_rejected(self):
        with self.assertRaisesRegex(ReconstructionError, "lossless .png"):
            composite_candidate(self.packet_path, self.base_path, self.candidate_path, self.root / "out.jpg")

    def test_existing_output_and_audit_are_not_overwritten(self):
        output = self.root / "existing.png"
        output.write_bytes(b"preserve")
        with self.assertRaises(FileExistsError):
            composite_candidate(self.packet_path, self.base_path, self.candidate_path, output)
        self.assertEqual(output.read_bytes(), b"preserve")

    def test_output_is_not_accepted_just_because_pixel_diff_passes(self):
        audit = composite_candidate(
            self.packet_path, self.base_path, self.candidate_path, self.root / "candidate-out.png"
        )
        self.assertEqual(audit["status"], "composited_candidate_not_accepted")
        self.assertEqual(audit["hard_gates"]["mask_leakage"], "pass")
        self.assertEqual(audit["hard_gates"]["registration_quality"], "pending")
        self.assertFalse(audit["final_acceptance"])


    def test_output_cannot_overwrite_immutable_base(self):
        with self.assertRaisesRegex(ReconstructionError, "must not overwrite"):
            composite_candidate(
                self.packet_path, self.base_path, self.candidate_path, self.base_path,
                overwrite=True
            )

    def test_output_cannot_overwrite_candidate_input(self):
        with self.assertRaisesRegex(ReconstructionError, "must not overwrite"):
            composite_candidate(
                self.packet_path, self.base_path, self.candidate_path, self.candidate_path,
                overwrite=True
            )
