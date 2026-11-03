from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ige.registration import (  # noqa: E402
    HomographyTransform,
    SimilarityTransform,
    fit_weighted_homography,
    fit_local_mesh_pair,
    register_multiview,
)


def make_edge(image_a, image_b, world, pose_a, pose_b, edge_id, noise=0.0, rng=None):
    """pose maps local -> world; anchors are local coords."""
    xa = pose_a.inverse().apply(world)
    xb = pose_b.inverse().apply(world)
    if noise and rng is not None:
        xa = xa + rng.normal(0, noise, size=xa.shape)
        xb = xb + rng.normal(0, noise, size=xb.shape)
    anchors = [
        {"name": f"{edge_id}_{i}", "xy_a": a.tolist(), "xy_b": b.tolist(), "weight": 1.0}
        for i, (a, b) in enumerate(zip(xa, xb))
    ]
    return {"edge_id": edge_id, "image_a": image_a, "image_b": image_b, "anchors": anchors}


class HomographyUnitTests(unittest.TestCase):
    def test_dlt_recovers_known_homography(self):
        rng = np.random.default_rng(0)
        src = rng.uniform([20, 20], [480, 380], size=(40, 2))
        H = np.array([[1.02, 0.04, 12.0], [-0.03, 0.98, -8.0], [0.0001, -0.0002, 1.0]], dtype=float)
        truth = HomographyTransform(H)
        tgt = truth.apply(src)
        fit = fit_weighted_homography(src, tgt, huber_px=5.0)
        err = np.linalg.norm(fit.transform.apply(src) - tgt, axis=1)
        self.assertLess(float(np.percentile(err, 95)), 0.05)

    def test_homography_multiview_triangle(self):
        world = np.asarray(
            [[80, 60], [320, 50], [100, 300], [340, 310], [200, 180], [250, 120], [150, 240], [280, 260]],
            dtype=float,
        )
        # Mild projective poses as H from local->world
        HA = HomographyTransform.identity()
        HB = HomographyTransform(np.array([[0.98, 0.02, 15], [-0.01, 1.01, -8], [0.00005, 0, 1.0]]))
        HC = HomographyTransform(np.array([[1.03, -0.02, -12], [0.02, 0.97, 18], [0, 0.00004, 1.0]]))
        poses = {"A": HA, "B": HB, "C": HC}
        specs = [{"id": k, "width": 500, "height": 400} for k in poses]
        edges = [
            make_edge("A", "B", world, poses["A"], poses["B"], "ab"),
            make_edge("B", "C", world, poses["B"], poses["C"], "bc"),
            make_edge("C", "A", world, poses["C"], poses["A"], "ca"),
        ]
        result = register_multiview(
            specs, edges, root_image_id="A", geometry_model="homography",
            huber_px=2.0, acceptance_threshold_px=1.0,
        )
        self.assertEqual(result["geometry_model"], "homography")
        self.assertEqual(result["geometry_gate"], "pass")
        self.assertLess(result["global_residual"]["p95_residual_px"], 0.5)


class LocalMeshTests(unittest.TestCase):
    def test_local_mesh_pair_has_tiles_or_backbone(self):
        rng = np.random.default_rng(1)
        src = rng.uniform([10, 10], [200, 200], size=(40, 2))
        # piecewise: left scale 1.0, right scale 1.1 approx via global + noise
        tgt = src * np.array([1.05, 1.0]) + np.array([5.0, -3.0])
        fit = fit_local_mesh_pair(src, tgt, grid=(2, 2), huber_px=5.0)
        self.assertGreaterEqual(fit.backbone.p95_residual_px, 0.0)
        # apply_local should not explode
        out = fit.apply_local(src)
        self.assertEqual(out.shape, src.shape)


class HoldoutCompareTests(unittest.TestCase):
    def test_similarity_holdout_on_clean_triangle(self):
        world = np.asarray(
            [[40, 40], [200, 40], [40, 200], [200, 200], [120, 120], [160, 80], [80, 160],
             [100, 50], [180, 150], [60, 100], [150, 180], [90, 90]],
            dtype=float,
        )
        poses = {
            "A": SimilarityTransform(1.0, 0.0, 0.0, 0.0),
            "B": SimilarityTransform(0.96, math.radians(4.0), 10.0, -6.0),
            "C": SimilarityTransform(1.04, math.radians(-5.0), -8.0, 12.0),
        }
        specs = [{"id": k, "width": 320, "height": 320} for k in poses]
        edges = [
            make_edge("A", "B", world, poses["A"], poses["B"], "ab"),
            make_edge("B", "C", world, poses["B"], poses["C"], "bc"),
            make_edge("C", "A", world, poses["C"], poses["A"], "ca"),
        ]
        result = register_multiview(
            specs, edges, root_image_id="A", geometry_model="similarity",
            huber_px=2.0, acceptance_threshold_px=1.0,
            holdout_fraction=0.25, holdout_seed=7,
        )
        self.assertIn("holdout", result)
        self.assertGreater(result["holdout"]["holdout_global"]["holdout_anchor_count"], 0)
        self.assertLess(result["holdout"]["holdout_global"]["p95_residual_px"], 0.5)

    def test_model_switch_homography_vs_similarity_holdout_on_projective(self):
        rng = np.random.default_rng(3)
        HA = HomographyTransform.identity()
        HB = HomographyTransform(np.array([[1.0, 0.05, 20], [0.0, 1.0, -10], [0.0002, 0.0, 1.0]], dtype=float))
        src_a = rng.uniform([40, 40], [340, 260], size=(40, 2))
        world = HA.apply(src_a)
        src_b = HB.inverse().apply(world)
        keep = (
            (src_a[:, 0] >= 0) & (src_a[:, 0] < 400) & (src_a[:, 1] >= 0) & (src_a[:, 1] < 320)
            & (src_b[:, 0] >= 0) & (src_b[:, 0] < 400) & (src_b[:, 1] >= 0) & (src_b[:, 1] < 320)
        )
        src_a, src_b = src_a[keep], src_b[keep]
        self.assertGreaterEqual(len(src_a), 12)
        anchors = [
            {"name": f"ab_{i}", "xy_a": a.tolist(), "xy_b": b.tolist(), "weight": 1.0}
            for i, (a, b) in enumerate(zip(src_a, src_b))
        ]
        specs = [{"id": "A", "width": 400, "height": 320}, {"id": "B", "width": 400, "height": 320}]
        edges = [{"edge_id": "ab", "image_a": "A", "image_b": "B", "anchors": anchors}]
        sim = register_multiview(
            specs, edges, root_image_id="A", geometry_model="similarity",
            huber_px=3.0, acceptance_threshold_px=None,
            holdout_fraction=0.3, holdout_seed=1,
        )
        hom = register_multiview(
            specs, edges, root_image_id="A", geometry_model="homography",
            huber_px=3.0, acceptance_threshold_px=None,
            holdout_fraction=0.3, holdout_seed=1,
        )
        self.assertEqual(hom["geometry_model"], "homography")
        self.assertIsNotNone(hom["holdout"]["holdout_global"]["p95_residual_px"])
        self.assertIsNotNone(sim["holdout"]["holdout_global"]["p95_residual_px"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
