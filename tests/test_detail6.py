import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from ige.upscale.detail6 import run_detail6
from ige.upscale.siax import MODEL_ID, MODEL_SHA256


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Detail6Tests(unittest.TestCase):
    def _fixture(self, root: Path):
        base = root / "base.png"
        yy, xx = np.mgrid[0:16, 0:16]
        source = np.stack([(xx * 11) % 255, (yy * 13) % 255, ((xx + yy) * 7) % 255], axis=2).astype("uint8")
        Image.fromarray(source, "RGB").save(base)
        high = np.asarray(Image.fromarray(source).resize((64, 64), Image.Resampling.LANCZOS)).astype("uint8")
        high_path = root / "s iax.png"
        Image.fromarray(high, "RGB").save(high_path)
        high_path.with_suffix(".upscale.json").write_text(json.dumps({"model_id":MODEL_ID,"scale":4,"checkpoint_sha256":MODEL_SHA256,"output_sha256":sha(high_path),"input_sha256":sha(base),"license_review":"user_confirmed"}), encoding="utf-8")
        masks_dir = root / "masks"
        masks_dir.mkdir()
        masks = {}
        for name in ("metal", "stone", "text", "fire", "face", "skin", "eye_white"):
            arr = np.zeros((16, 16), dtype="uint8")
            if name == "metal":
                arr[2:12, 2:12] = 255
            Image.fromarray(arr, "L").save(masks_dir / f"{name}.png")
            masks[name] = f"masks/{name}.png"
        manifest = root / "masks.json"
        manifest.write_text(json.dumps({"mask_version":"1.0", "masks":masks}), encoding="utf-8")
        return base, high_path, manifest

    def test_detail6_is_true_4x_and_protects_outside_masks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, high, masks = self._fixture(root)
            report = run_detail6(base, high, masks, root / "out", minimum_bytes=1, gain=0.15)
            self.assertTrue(report["gates"]["exact_4x"])
            self.assertTrue(report["gates"]["protected_pixels_preserved_on_png"])
            self.assertTrue(report["execution_complete"])
            self.assertEqual(report["visual_quality_review"], "REQUIRED_NOT_RUN")
            self.assertFalse(report["final_acceptance"])
            self.assertEqual(report["pixel_audit"]["changed_inside_protected_masks"], 0)
            self.assertTrue((root / "out" / "DETAIL6_WORKING.png").is_file())

    def test_detail6_does_not_inflate_to_fake_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, high, masks = self._fixture(root)
            report = run_detail6(base, high, masks, root / "out", minimum_bytes=100_000_000)
            self.assertFalse(report["gates"]["minimum_delivery_bytes"])
            self.assertFalse(report["execution_complete"])
            self.assertFalse(report["final_acceptance"])

    def test_wrong_dimensions_are_rejected_not_resized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, high, masks = self._fixture(root)
            wrong = root / "wrong.png"
            Image.new("RGB", (63, 64), "black").save(wrong)
            wrong.with_suffix(".upscale.json").write_text(json.dumps({"model_id":MODEL_ID,"scale":4,"checkpoint_sha256":MODEL_SHA256,"output_sha256":sha(wrong),"input_sha256":sha(base),"license_review":"user_confirmed"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_detail6(base, wrong, masks, root / "out", minimum_bytes=1)


if __name__ == "__main__":
    unittest.main()
