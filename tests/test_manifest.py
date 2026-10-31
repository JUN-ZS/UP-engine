import unittest
from pathlib import Path
from ige.manifest import load_manifest, PEEPManifest


class ManifestTests(unittest.TestCase):
    def test_example_manifest_is_valid(self):
        path = Path(__file__).parents[1] / "examples" / "peep_manifest.json"
        manifest = load_manifest(path)
        self.assertEqual(manifest.task_id, "example-retexture-001")

    def test_same_mask_is_rejected(self):
        raw = {
            "manifest_version": "0.1", "task_id": "x", "parent_asset_id": "base",
            "generation_mask": "same.png", "protected_mask": "same.png",
            "transform": {"kind": "identity"}, "adapter_id": "a", "output_uri": "out.png"
        }
        with self.assertRaises(ValueError):
            PEEPManifest.from_dict(raw)
