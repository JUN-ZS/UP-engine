from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import cv2
except ImportError:
    cv2 = None


@unittest.skipIf(cv2 is None or not hasattr(cv2, "SIFT_create"), "OpenCV SIFT is not installed")
class SiftFeatureMatchTests(unittest.TestCase):
    def test_three_overlapping_crops_produce_a_redundant_match_graph(self):
        from ige.registration.features import build_sift_match_graph
        from ige.registration import register_multiview

        rng = np.random.default_rng(10)
        scene = np.zeros((420, 620, 3), dtype=np.uint8)
        for _ in range(350):
            x, y = int(rng.integers(10, 610)), int(rng.integers(10, 410))
            color = tuple(int(v) for v in rng.integers(50, 255, 3))
            cv2.circle(scene, (x, y), int(rng.integers(2, 8)), color, -1)
        for _ in range(70):
            x1, y1 = int(rng.integers(0, 600)), int(rng.integers(0, 400))
            x2 = min(619, x1 + int(rng.integers(5, 60)))
            y2 = min(419, y1 + int(rng.integers(5, 60)))
            cv2.line(scene, (x1, y1), (x2, y2), tuple(int(v) for v in rng.integers(100,255,3)), 1)
        images = {"A": scene[:, :440], "B": scene[:, 90:530], "C": scene[:, 180:]}
        payload = build_sift_match_graph(images, max_features=4000, ratio_threshold=0.75,
            ransac_reprojection_px=2.5, min_inliers=12, matcher_backend="flann")
        self.assertEqual(len(payload["matches"]), 3)
        self.assertTrue(all(len(edge["anchors"]) >= 12 for edge in payload["matches"]))
        self.assertTrue(all(row["status"] == "candidate_edge" for row in payload["pair_diagnostics"]))
        result = register_multiview(payload["images"], payload["matches"], root_image_id="A",
            huber_px=3.0, acceptance_threshold_px=1.0)
        self.assertEqual(result["graph"]["cycle_rank"], 1)
        self.assertEqual(result["geometry_gate"], "pass")
        for image_id, expected_x in (("B", 90.0), ("C", 180.0)):
            transform = result["images"][image_id]["world_transform"]
            self.assertAlmostEqual(transform["scale"], 1.0, delta=0.01)
            self.assertAlmostEqual(transform["rotation_degrees"], 0.0, delta=0.1)
            self.assertAlmostEqual(transform["translation_px"][0], expected_x, delta=0.75)
            self.assertAlmostEqual(transform["translation_px"][1], 0.0, delta=0.75)


if __name__ == "__main__":
    unittest.main(verbosity=2)
