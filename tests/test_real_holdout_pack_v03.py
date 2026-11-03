from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ige.registration import register_multiview  # noqa: E402

PACK = ROOT / "docs/evidence/siax_real_multiview_holdout_v03"


class RealHoldoutPackTests(unittest.TestCase):
    def test_operator_geom_pack_loads_and_holdout(self):
        anchors = json.loads((PACK / "N1_CHAIN4_OPERATOR_GEOM_anchors.json").read_text())
        specs = json.loads((PACK / "N1_CHAIN4_OPERATOR_GEOM_specs.json").read_text())["image_specs"]
        specs_n = [{"id": s["id"], "width": s["width"], "height": s["height"]} for s in specs]
        self.assertGreaterEqual(len(specs_n), 2)
        self.assertGreaterEqual(len(anchors["matches"]), 1)
        result = register_multiview(
            specs_n, anchors["matches"], root_image_id=specs_n[0]["id"],
            geometry_model="similarity", holdout_fraction=0.25, holdout_seed=42,
            allow_unverified_bridge_edges=True,
        )
        self.assertIn("holdout", result)
        self.assertGreater(result["holdout"]["holdout_global"]["holdout_anchor_count"], 0)
        self.assertLess(result["holdout"]["holdout_global"]["p95_residual_px"], 1e-6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
