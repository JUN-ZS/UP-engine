from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from ige.agent_driver import (
    AgentDriverError,
    CallableDispatcher,
    DispatchBlocked,
    MANIFEST_SCHEMA,
    run_agent_manifest,
)
from ige.method_registry import MethodRegistry

SIAX_SHA = "560424d9f68625713fc47e9e7289a98aabe1d744e1cd6a9ae5a35e9957fd127e"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AgentDriverTests(unittest.TestCase):
    def setUp(self):
        self.registry = MethodRegistry.load()

    def _manifest(self, root: Path, method_id: str = "SIAX4X_TILE_CORE_SR"):
        source = root / "source.png"
        Image.new("RGB", (2, 2), (30, 40, 50)).save(source)
        canvas = root / "coordinate_canvas.png"
        Image.new("RGB", (8, 8), (30, 40, 50)).save(canvas)
        approved = root / "approved.png"
        approved_array = np.zeros((8, 8), dtype=np.uint8)
        approved_array[1, 1] = 255
        Image.fromarray(approved_array).save(approved)
        protected = root / "protected.png"
        protected_array = np.zeros((8, 8), dtype=np.uint8)
        protected_array[6, 6] = 255
        Image.fromarray(protected_array).save(protected)
        checkpoint = root / "siax.pth"
        checkpoint.write_bytes(b"test-only-checkpoint-placeholder")
        return {
            "schema": MANIFEST_SCHEMA,
            "run_id": "unit-test-run",
            "method_id": method_id,
            "source": {"path": str(source), "sha256": sha(source)},
            "read_receipt": {
                "source_sha256": sha(source),
                "candidate_only": True,
                "observations": {
                    "topology_error": {"state": "absent", "verification": "human_verified"}
                },
            },
            "geometry_contract": {
                "source_sha256": sha(source),
                "canvas_path": str(canvas),
                "canvas_sha256": sha(canvas),
                "coordinate_frame": "native_4x_master",
                "geometry_human_verified": True,
                "object_transform": {"kind": "identity", "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
                "model_scale": 4,
                "tile_size": 32,
                "tile_context": 4,
            },
            "permission": {
                "human_reviewed": True,
                "permission_granted": True,
                "base_sha256": sha(source),
                "coordinate_canvas_sha256": sha(canvas),
                "approved_edit_mask_path": str(approved),
                "approved_edit_mask_sha256": sha(approved),
                "protected_mask_path": str(protected),
                "protected_mask_sha256": sha(protected),
                "target_regions": ["unit_test_region"],
                "reviewer_ref": "unit-test-reviewer",
                "reviewed_at": "2026-11-08T00:00:00+08:00",
            },
            "tile_plan": {"verified": True, "tile_size": 32, "tile_context": 4},
            "backend": {
                "checkpoint_path": str(checkpoint),
                "checkpoint_sha256": SIAX_SHA,
                "license_review_acknowledged": True,
                "device": "cpu",
            },
            "output_path": str(root / "candidate.png"),
        }, checkpoint

    def test_siax_is_the_only_current_callable_and_flux_is_blocked(self):
        dispatcher = CallableDispatcher()
        siax = self.registry.resolve("SIAX4X_TILE_CORE_SR")
        self.assertTrue(callable(dispatcher.resolve(siax)))
        flux = self.registry.resolve("FLUX_HR_TILE_IMG2IMG")
        with self.assertRaises(DispatchBlocked):
            dispatcher.resolve(flux)

    def test_plan_only_verifies_s0_to_s4_and_never_claims_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, checkpoint = self._manifest(root)
            with patch("ige.agent_driver.sha256_file", side_effect=lambda p: SIAX_SHA if Path(p) == checkpoint else sha(Path(p))):
                report = run_agent_manifest(manifest, execute=False, registry=self.registry)
        self.assertEqual(report["status"], "READY_FOR_EXPLICIT_EXECUTION")
        self.assertEqual([s["status"] for s in report["stages"][:5]], ["PASS"] * 5)
        self.assertEqual(report["stages"][5]["status"], "NOT_RUN")
        self.assertEqual(report["stages"][6]["status"], "NOT_RUN")
        self.assertFalse(report["execution_allowed"])
        self.assertFalse(report["edit_permission"])
        self.assertEqual(report["comfyui_claim"], "NOT_EXECUTED_NOT_VERIFIED")

    def test_flux_manifest_is_blocked_not_dispatched(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, checkpoint = self._manifest(Path(directory), "FLUX_HR_TILE_IMG2IMG")
            with patch("ige.agent_driver.sha256_file", side_effect=lambda p: SIAX_SHA if Path(p) == checkpoint else sha(Path(p))):
                report = run_agent_manifest(manifest, execute=True, registry=self.registry)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["execution_allowed"])
        self.assertIn("workflow_candidate", report["stages"][0]["reasons"][0])

    def test_overlapping_approved_and_protected_masks_block(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, checkpoint = self._manifest(Path(directory))
            Image.fromarray(np.asarray(Image.open(manifest["permission"]["approved_edit_mask_path"]).convert("L"))).save(
                manifest["permission"]["protected_mask_path"]
            )
            manifest["permission"]["protected_mask_sha256"] = sha(Path(manifest["permission"]["protected_mask_path"]))
            with patch("ige.agent_driver.sha256_file", side_effect=lambda p: SIAX_SHA if Path(p) == checkpoint else sha(Path(p))):
                report = run_agent_manifest(manifest, execute=False, registry=self.registry)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("overlap", report["stages"][0]["reasons"][0])

    def test_manifest_schema_rejects_missing_method_id(self):
        with self.assertRaises(AgentDriverError):
            run_agent_manifest({"schema": MANIFEST_SCHEMA, "run_id": "x"}, registry=self.registry)


if __name__ == "__main__":
    unittest.main()
