import json
import tempfile
import unittest
from pathlib import Path

from ige.read.annotations import load_regions


class ReadAnnotationTests(unittest.TestCase):
    def _write(self, raw):
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
        with temp:
            json.dump(raw, temp)
        self.addCleanup(Path(temp.name).unlink, missing_ok=True)
        return Path(temp.name)

    def test_semantic_type_is_independent_of_pixel_permission(self):
        path = self._write({
            "coordinate_space": "normalized_0_1",
            "regions": [{
                "id": "armor", "label": "silver armor", "semantic_type": "garment",
                "permission": "editable", "tags": ["object"],
                "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]
            }]
        })
        region = load_regions(path)[0]
        self.assertEqual(region.semantic_type, "garment")
        self.assertEqual(region.permission.value, "editable")
        self.assertIn("object", region.tags)

    def test_out_of_range_coordinate_rejected(self):
        path = self._write({
            "coordinate_space": "normalized_0_1",
            "regions": [{
                "id": "bad", "label": "bad", "semantic_type": "unknown",
                "permission": "editable",
                "polygon": [[-0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]
            }]
        })
        with self.assertRaises(ValueError):
            load_regions(path)

    def test_duplicate_region_ids_rejected(self):
        item = {
            "id": "same", "label": "region", "semantic_type": "context",
            "permission": "protected",
            "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]
        }
        path = self._write({"coordinate_space": "normalized_0_1", "regions": [item, item]})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_regions(path)
