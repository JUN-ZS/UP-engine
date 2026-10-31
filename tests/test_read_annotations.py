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

    def test_normalized_polygon_loads(self):
        path = self._write({
            "coordinate_space": "normalized_0_1",
            "regions": [{
                "id": "coat", "label": "coat", "role": "editable",
                "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]
            }]
        })
        regions = load_regions(path)
        self.assertEqual(regions[0].region_id, "coat")
        self.assertEqual(regions[0].role.value, "editable")

    def test_out_of_range_coordinate_rejected(self):
        path = self._write({
            "coordinate_space": "normalized_0_1",
            "regions": [{
                "id": "bad", "label": "bad", "role": "editable",
                "polygon": [[-0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]
            }]
        })
        with self.assertRaises(ValueError):
            load_regions(path)

    def test_duplicate_region_ids_rejected(self):
        item = {
            "id": "same", "label": "region", "role": "context",
            "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]
        }
        path = self._write({"coordinate_space": "normalized_0_1", "regions": [item, item]})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_regions(path)
