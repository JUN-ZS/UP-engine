from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
NODE_FILE = ROOT / "custom_nodes/ComfyUI-SIAX-MultiImage/nodes.py"
spec = importlib.util.spec_from_file_location("siaux_multimage_nodes_e2e", NODE_FILE)
node_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(node_module)

try:
    import cv2
    import torch
except ImportError:
    cv2 = None
    torch = None


@unittest.skipIf(cv2 is None or torch is None, "optional OpenCV SIFT and torch are needed for node E2E")
class ComfyNodeE2ETests(unittest.TestCase):
    def test_three_image_feature_register_warp_and_stitch_chain(self):
        rng = np.random.default_rng(10)
        scene = np.zeros((420, 620, 3), dtype=np.uint8)
        for _ in range(350):
            x, y = int(rng.integers(10,610)), int(rng.integers(10,410))
            cv2.circle(scene,(x,y),int(rng.integers(2,8)),
                       tuple(int(v) for v in rng.integers(50,255,3)),-1)
        for _ in range(70):
            x1,y1 = int(rng.integers(0,600)),int(rng.integers(0,400))
            x2,y2 = min(619,x1+int(rng.integers(5,60))),min(419,y1+int(rng.integers(5,60)))
            cv2.line(scene,(x1,y1),(x2,y2),tuple(int(v) for v in rng.integers(100,255,3)),1)
        arrays = [scene[:,:440].copy(),scene[:,90:530].copy(),scene[:,180:].copy()]
        tensors = [torch.from_numpy(x.astype(np.float32)/255.0).unsqueeze(0) for x in arrays]
        anchors, feature_report = node_module.SIAXMultiImageFeatureMatches().build_matches(
            tensors[0],tensors[1],"flann",4000,0.75,2.5,12,image_2=tensors[2])
        self.assertEqual(__import__("json").loads(feature_report)["candidate_edges"],3)
        transforms, report = node_module.SIAXMultiImageGeometryRegistration().register(
            tensors[0],tensors[1],anchors,"image_0",3.0,1.0,100.0,False,image_2=tensors[2])
        self.assertEqual(__import__("json").loads(report)["geometry_gate"],"pass")
        registered, masks = [], []
        for i, tensor in enumerate(tensors):
            image, mask = node_module.SIAXApplyGeometryTransform().apply_transform(
                tensor,transforms,f"image_{i}","bicubic")
            registered.append(image); masks.append(mask)
        composite, coverage, overlap = node_module.SIAXMultiImageStitch().stitch(
            registered[0],masks[0],registered[1],masks[1],0,
            image_2=registered[2],mask_2=masks[2])
        self.assertEqual(composite.shape[0],1)
        self.assertGreater(float(coverage.sum()),620*420*0.995)
        self.assertGreater(float(overlap.sum()),0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
