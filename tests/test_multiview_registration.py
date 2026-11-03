from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ige.registration import (  # noqa: E402
    MultiViewRegistrationError,
    SimilarityTransform,
    fit_weighted_similarity,
    register_multiview,
)


class DDXXFixtureTests(unittest.TestCase):
    def test_manual_ddxx_fixture_matches_weighted_umeyama(self):
        fixture = json.loads((ROOT / "tests/fixtures/DDXX_MANUAL_PANEL_GOLD_01.json").read_text())
        rows = fixture["landmarks"]
        source = np.asarray([x["donor_xy"] for x in rows], dtype=float)
        target = np.asarray([x["target_xy"] for x in rows], dtype=float)
        weights = np.asarray([x["weight"] for x in rows], dtype=float)
        fit = fit_weighted_similarity(source, target, weights, huber_px=10.0)
        expected, tolerance = fixture["expected"], fixture["tolerance"]
        self.assertAlmostEqual(fit.transform.scale, expected["scale_a"], delta=tolerance["scale_a_abs"])
        self.assertAlmostEqual(math.degrees(fit.transform.rotation_rad), expected["rotation_degrees_row_convention"], delta=tolerance["rotation_degrees_abs"])
        self.assertAlmostEqual(fit.transform.tx, expected["translation_target_px"][0], delta=tolerance["translation_px_abs"])
        self.assertAlmostEqual(fit.transform.ty, expected["translation_target_px"][1], delta=tolerance["translation_px_abs"])
        self.assertAlmostEqual(fit.weighted_rmse_px, expected["weighted_rmse_px"], delta=tolerance["weighted_rmse_px_abs"])
        # The legacy fixture does not exercise Huber downweighting.
        self.assertTrue(np.allclose(fit.robust_weights, fit.base_weights))


class PoseGraphTests(unittest.TestCase):
    @staticmethod
    def edge(image_a, image_b, world, pose_a, pose_b, edge_id):
        xa, xb = pose_a.inverse().apply(world), pose_b.inverse().apply(world)
        anchors = [{"name": f"{edge_id}_{i}", "xy_a": a.tolist(), "xy_b": b.tolist(), "weight": 1.0}
                   for i, (a, b) in enumerate(zip(xa, xb))]
        return {"edge_id": edge_id, "image_a": image_a, "image_b": image_b, "anchors": anchors}

    def test_global_triangle_fit_and_cycle_closure(self):
        world = np.asarray([[120,100],[330,100],[120,320],[330,320],[220,210],[270,160],[170,260]], dtype=float)
        poses = {
            "A": SimilarityTransform(1.0, 0.0, 0.0, 0.0),
            "B": SimilarityTransform(0.95, math.radians(5.0), 15.0, -10.0),
            "C": SimilarityTransform(1.05, math.radians(-8.0), -10.0, 20.0),
        }
        specs = [{"id": k, "width": 600, "height": 500} for k in poses]
        edges = [
            self.edge("A","B",world,poses["A"],poses["B"],"ab"),
            self.edge("B","C",world,poses["B"],poses["C"],"bc"),
            self.edge("C","A",world,poses["C"],poses["A"],"ca"),
        ]
        result = register_multiview(specs, edges, root_image_id="A", huber_px=3.0, acceptance_threshold_px=0.1)
        self.assertEqual(result["graph"]["cycle_rank"], 1)
        self.assertEqual(result["geometry_gate"], "pass")
        for image_id in ("B", "C"):
            got, expected = result["images"][image_id]["world_transform"], poses[image_id]
            self.assertAlmostEqual(got["scale"], expected.scale, places=5)
            self.assertAlmostEqual(got["rotation_degrees"], math.degrees(expected.rotation_rad), places=4)
            self.assertAlmostEqual(got["translation_px"][0], expected.tx, places=4)
            self.assertAlmostEqual(got["translation_px"][1], expected.ty, places=4)
        self.assertLess(result["global_residual"]["p95_residual_px"], 1e-4)

    def test_huber_downweights_one_gross_outlier(self):
        rng = np.random.default_rng(42)
        source = rng.uniform([20,20], [480,380], size=(30,2))
        truth = SimilarityTransform(1.08, math.radians(6.0), 24.0, -13.0)
        target = truth.apply(source)
        target[-1] += [180.0, -140.0]
        robust = fit_weighted_similarity(source, target, huber_px=5.0)
        ordinary = fit_weighted_similarity(source, target, huber_px=1e6)
        robust_error = np.linalg.norm(robust.transform.apply(source[:-1])-target[:-1], axis=1).mean()
        ordinary_error = np.linalg.norm(ordinary.transform.apply(source[:-1])-target[:-1], axis=1).mean()
        self.assertLess(robust_error, ordinary_error*0.35)
        self.assertLess(robust.robust_weights[-1], 0.1)

    def test_cycle_does_not_validate_dangling_bridge(self):
        world = np.asarray([[20,20],[80,20],[20,80],[80,80],[50,35]], dtype=float)
        poses = {
            "A": SimilarityTransform(1.0,0.0,0.0,0.0),
            "B": SimilarityTransform(1.0,0.0,12.0,-3.0),
            "C": SimilarityTransform(1.0,0.0,-5.0,8.0),
            "D": SimilarityTransform(1.0,0.0,10.0,2.0),
        }
        specs = [{"id": k, "width": 150, "height": 150} for k in poses]
        edges = [
            self.edge("A","B",world,poses["A"],poses["B"],"ab"),
            self.edge("B","C",world,poses["B"],poses["C"],"bc"),
            self.edge("C","A",world,poses["C"],poses["A"],"ca"),
            self.edge("C","D",world,poses["C"],poses["D"],"cd-bridge"),
        ]
        result = register_multiview(specs, edges, root_image_id="A", acceptance_threshold_px=1.0)
        self.assertEqual(result["graph"]["cycle_rank"], 1)
        self.assertEqual(result["graph"]["bridge_edge_ids"], ["cd-bridge"])
        self.assertEqual(result["geometry_gate"], "pending_unverified_bridge_edges")

    def test_invalid_collinear_anchor_geometry_fails_closed(self):
        points = [[10,10],[20,20],[30,30],[40,40]]
        edge = {"image_a":"A","image_b":"B","anchors":[{"xy_a":p,"xy_b":p} for p in points]}
        with self.assertRaisesRegex(MultiViewRegistrationError, "collinear"):
            register_multiview([{"id":"A","width":80,"height":80},{"id":"B","width":80,"height":80}], [edge])

    def test_acceptance_threshold_is_mandatory(self):
        world = np.asarray([[10,10],[50,10],[10,50],[50,50],[30,20],[20,40]], dtype=float)
        edge = self.edge("A","B",world,SimilarityTransform(1,0,0,0),SimilarityTransform(1,0,0,0),"ab")
        result = register_multiview([{"id":"A","width":64,"height":64},{"id":"B","width":64,"height":64}], [edge])
        self.assertEqual(result["geometry_gate"], "pending_threshold_not_declared")


if __name__ == "__main__":
    unittest.main(verbosity=2)
