from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.build_comfy_siax_staged_workflows import build_staged_workflows
from tools.comfy_siax_geometry_preflight import inspect_stage2_preflight

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/handoff/comfy-siax-return/pc_高清探/workflow_ige_v03_dev_fp8_gated_candidate.json"


def geometry(width=64, height=36):
    return {
        "schema_version": "ige-object-geometry/1.0",
        "geometry_status": "assistant_provisional",
        "source": {"filename": "reference.png", "sha256": "a" * 64, "width": width, "height": height},
        "provenance": {"operator_confirmation": "pending"},
        "object": {"id": "test-object", "bbox_xyxy": [10, 5, 30, 30], "polygon_xy": [[10,5],[30,5],[30,30],[10,30]]},
        "tolerances": {},
    }


def policy():
    return {
        "schema_version": "ige-global-logic-policy/0.1",
        "policy_id": "test-policy",
        "revision": 1,
        "default_action": "REFINE",
        "default_constraints": {"allow_new_semantics": False, "allow_geometry_change": False},
        "rules": [],
        "operator_regions": [],
        "source_alignment_status": "pending_operator_registration_to_siax_output",
        "global_instruction": "Preserve geometry.",
    }


class ComfySiaxGeometryPreflightTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads(BASE.read_text(encoding="utf-8"))

    def _write_inputs(self, root: Path, size=(64, 36)):
        image_path = root / "stage1_canvas.png"
        Image.new("RGB", size, (40, 80, 120)).save(image_path)
        geometry_path = root / "geometry.json"
        geometry_path.write_text(json.dumps(geometry()), encoding="utf-8")
        policy_path = root / "policy.json"
        policy_path.write_text(json.dumps(policy()), encoding="utf-8")
        _, stage2, _ = build_staged_workflows(self.base)
        nodes = {int(n["id"]): n for n in stage2["nodes"]}
        nodes[34]["widgets_values"][0] = image_path.name
        if isinstance(nodes[34].get("widgets_values_named"), dict):
            nodes[34]["widgets_values_named"]["image"] = image_path.name
        workflow_path = root / "stage2.json"
        workflow_path.write_text(json.dumps(stage2), encoding="utf-8")
        return workflow_path, image_path, geometry_path, policy_path

    def test_matching_dimensions_still_block_provisional_geometry_and_pending_alignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._write_inputs(Path(tmp))
            report = inspect_stage2_preflight(*paths)
        self.assertTrue(report["geometry_dimensions_match"])
        self.assertEqual(report["status"], "BLOCKED_PENDING_HUMAN_GEOMETRY_AND_SOURCE_REGISTRATION")
        self.assertFalse(report["execution_allowed"])
        self.assertFalse(report["queue_submission"])
        self.assertEqual(len(report["samplers"]), 2)
        self.assertEqual(
            [row["memory_barrier_node_id"] for row in report["samplers"]],
            [344, 345],
        )
        self.assertTrue(all(row["release_models_before_vae_decode"] for row in report["samplers"]))

    def test_dimension_mismatch_blocks_before_compile_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._write_inputs(Path(tmp), size=(60, 36))
            report = inspect_stage2_preflight(*paths)
        self.assertFalse(report["geometry_dimensions_match"])
        self.assertEqual(report["compiler_contract_status"], "NOT_RUN_DIMENSION_MISMATCH")
        self.assertTrue(report["explicit_transform_required"])
        self.assertEqual(report["status"], "BLOCKED_CANVAS_DIMENSION_MISMATCH")

    def test_wrong_loadimage_selection_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = list(self._write_inputs(Path(tmp)))
            workflow_path = paths[0]
            workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
            next(n for n in workflow["nodes"] if n["id"] == 34)["widgets_values"][0] = "another.png"
            workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "selects"):
                inspect_stage2_preflight(*paths)


if __name__ == "__main__":
    unittest.main()
