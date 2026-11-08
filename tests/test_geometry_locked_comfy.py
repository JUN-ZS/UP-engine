from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from ige.comfy.geometry_locked import GeometryLockedError, compose_core_only_master, validate_geometry_tile_plan
from ige.comfy.geometry_locked_runtime import (
    GeometryLockedRuntimeError,
    create_geometry_locked_comfy_manifest,
    run_comfy_geometry_locked,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeCloudClient:
    base_url = "https://cloud.comfy.org"

    def __init__(self, outputs: dict[str, Image.Image] | None = None):
        self.outputs = outputs or {}
        self.uploaded = []
        self.submitted = None

    def health(self):
        return {"status": "reachable", "node_count": 2, "object_info": {}, "features": {}}

    def model_inventory(self):
        return {"folders": [], "models_by_folder": {}}

    def upload_image(self, path):
        self.uploaded.append(Path(path))
        return {"name": Path(path).name, "subfolder": "", "type": "input"}

    def submit_prompt(self, workflow):
        self.submitted = workflow
        return "cloud-job-001"

    def wait_for_job(self, prompt_id, **kwargs):
        return {
            "status": "completed",
            "outputs": {
                "save-left": {"images": [{"filename": "left.png", "type": "output"}]},
                "save-right": {"images": [{"filename": "right.png", "type": "output"}]},
            },
        }

    @staticmethod
    def collect_images(job):
        from ige.comfy.cloud_client import ComfyCloudClient
        return ComfyCloudClient.collect_images(job)

    def download_output(self, record, destination):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        image = self.outputs[record["filename"]]
        image.save(path, format="PNG")
        return {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
            "source_file": record["filename"],
            "image_format": "PNG",
            "width": image.width,
            "height": image.height,
        }


class GeometryLockedFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.png"
        self.canvas = self.root / "canvas.png"
        self.approved = self.root / "approved.png"
        self.protected = self.root / "protected.png"
        self.workflow = self.root / "workflow.json"
        self.geometry_contract = self.root / "s2_geometry_contract.json"
        self.plan_path = self.root / "tile_plan.json"
        self.manifest = self.root / "run.json"
        self.output_dir = self.root / "run-output"

        Image.new("RGB", (2, 1), (9, 8, 7)).save(self.source)
        Image.new("RGB", (8, 4), (10, 20, 30)).save(self.canvas)
        s2 = {
            "source_sha256": sha(self.source),
            "canvas_path": str(self.canvas),
            "canvas_sha256": sha(self.canvas),
            "coordinate_frame": "canvas_px_4x_v1",
            "geometry_human_verified": True,
            "object_transform": {"uniform_scale": 4.0},
            "model_scale": 4.0,
            "tile_size": 64,
            "tile_context": 8,
        }
        self.geometry_contract.write_text(json.dumps(s2), encoding="utf-8")
        approved = Image.new("L", (8, 4), 0)
        for x in range(2, 6):
            for y in range(4):
                approved.putpixel((x, y), 255)
        approved.save(self.approved)
        protected = Image.new("L", (8, 4), 0)
        for x in range(0, 2):
            for y in range(4):
                protected.putpixel((x, y), 255)
        protected.save(self.protected)
        workflow = {
            "load-left": {"class_type": "LoadImage", "inputs": {"image": "replace-left.png"}},
            "load-right": {"class_type": "LoadImage", "inputs": {"image": "replace-right.png"}},
            "save-left": {"class_type": "SaveImage", "inputs": {}},
            "save-right": {"class_type": "SaveImage", "inputs": {}},
        }
        self.workflow.write_text(json.dumps(workflow), encoding="utf-8")
        plan = {
            "schema": "ige-comfy-tile-plan/0.1",
            "coordinate_frame": "canvas_px_4x_v1",
            "coverage_target": {"kind": "rect_union", "rects": [[0, 0, 8, 4]]},
            "tiles": [
                {"tile_id": "LEFT", "input_node_id": "load-left", "read_bounds": [0, 0, 4, 4], "core_bounds": [0, 0, 4, 4]},
                {"tile_id": "RIGHT", "input_node_id": "load-right", "read_bounds": [4, 0, 8, 4], "core_bounds": [4, 0, 8, 4]},
            ],
        }
        self.plan_path.write_text(json.dumps(plan), encoding="utf-8")
        result = create_geometry_locked_comfy_manifest(
            workflow_path=self.workflow,
            source_path=self.source,
            canvas_path=self.canvas,
            geometry_contract_path=self.geometry_contract,
            approved_mask_path=self.approved,
            protected_mask_path=self.protected,
            tile_plan_path=self.plan_path,
            manifest_path=self.manifest,
            output_dir=self.output_dir,
        )
        self.permission_path = Path(result["permission_template_path"])
        permission = json.loads(self.permission_path.read_text(encoding="utf-8"))
        permission.update({
            "decision": "APPROVED",
            "reviewer_ref": "reviewer:test",
            "reviewed_at": "2026-11-08T09:00:00+08:00",
            "reviewed_artifacts": ["source", "canvas", "geometry_contract", "approved_mask", "protected_mask", "tile_plan", "workflow"],
        })
        self.permission_path.write_text(json.dumps(permission), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _audit(self, workflow, **kwargs):
        return {
            "blockers": ["E_NOISE_FIELD_NOT_GLOBAL", "E_TILE_COMPOSITOR_MISSING", "E_CLOUD_MODEL_SHA_UNVERIFIED"],
            "routed_tiles": [
                {"tile_id": "LEFT", "origin_xy": [0, 0], "input_node_id": "load-left", "save_node_ids": ["save-left"]},
                {"tile_id": "RIGHT", "origin_xy": [4, 0], "input_node_id": "load-right", "save_node_ids": ["save-right"]},
            ],
        }

    def test_prepare_generates_bound_crops_and_pending_permission_template(self):
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertTrue(manifest["diagnostic_only"])
        self.assertEqual(manifest["canvas"]["width"], 8)
        self.assertIn("geometry_contract", manifest)
        self.assertEqual(len(manifest["tile_plan"]["tiles"]), 2)
        self.assertEqual(json.loads(self.permission_path.read_text())["decision"], "APPROVED")
        left = self.root / "run-output" / "inputs" / "LEFT.png"
        right = self.root / "run-output" / "inputs" / "RIGHT.png"
        with Image.open(left) as image:
            self.assertEqual(image.size, (4, 4))
        with Image.open(right) as image:
            self.assertEqual(image.size, (4, 4))

    def test_exact_once_local_compositor_writes_approved_core_pixels_only(self):
        left = self.root / "left-output.png"
        right = self.root / "right-output.png"
        Image.new("RGB", (4, 4), (200, 1, 1)).save(left)
        Image.new("RGB", (4, 4), (1, 200, 1)).save(right)
        manifest = json.loads(self.manifest.read_text())
        plan = manifest["tile_plan"]
        result = compose_core_only_master(
            base_canvas_path=self.canvas,
            approved_mask_path=self.approved,
            protected_mask_path=self.protected,
            tile_plan=plan,
            tile_outputs=[{"tile_id": "LEFT", "path": str(left), "sha256": sha(left)},
                          {"tile_id": "RIGHT", "path": str(right), "sha256": sha(right)}],
            canvas_sha256=manifest["canvas"]["sha256"],
            output_path=self.root / "master.png",
        )
        self.assertEqual(result["status"], "PASS_LOCAL_CORE_ONLY_COMPOSITOR")
        self.assertEqual(result["changed_pixels_outside_approved"], 0)
        self.assertEqual(result["changed_pixels_in_protected"], 0)
        out = np.asarray(Image.open(self.root / "master.png").convert("RGB"))
        self.assertTrue(np.all(out[:, 0:2] == np.array([10, 20, 30])))
        self.assertTrue(np.all(out[:, 2:4] == np.array([200, 1, 1])))
        self.assertTrue(np.all(out[:, 4:6] == np.array([1, 200, 1])))
        self.assertTrue(np.all(out[:, 6:8] == np.array([10, 20, 30])))
        self.assertFalse(result["execution_allowed"])

    def test_s2_contract_must_bind_source_canvas_and_scale(self):
        s2 = json.loads(self.geometry_contract.read_text())
        s2["model_scale"] = 2.0
        self.geometry_contract.write_text(json.dumps(s2), encoding="utf-8")
        with self.assertRaisesRegex(GeometryLockedRuntimeError, "does not map source dimensions"):
            create_geometry_locked_comfy_manifest(
                workflow_path=self.workflow, source_path=self.source, canvas_path=self.canvas,
                geometry_contract_path=self.geometry_contract, approved_mask_path=self.approved,
                protected_mask_path=self.protected, tile_plan_path=self.plan_path,
                manifest_path=self.root / "wrong_s2.json", output_dir=self.root / "wrong_s2_out",
            )

    def test_rejects_core_overlap_and_missing_tile_output(self):
        plan = json.loads(self.plan_path.read_text())
        plan["tiles"][1]["core_bounds"] = [3, 0, 8, 4]
        with self.assertRaises(GeometryLockedError):
            validate_geometry_tile_plan(plan, canvas_size=(8, 4), canvas_sha256=sha(self.canvas))

    def test_rejects_unsafe_tile_id_before_creating_input_path(self):
        plan = json.loads(self.plan_path.read_text())
        plan["tiles"][0]["tile_id"] = "../outside"
        with self.assertRaisesRegex(GeometryLockedError, "safe filename"):
            validate_geometry_tile_plan(plan, canvas_size=(8, 4), canvas_sha256=sha(self.canvas))

    def test_run_requires_explicit_diagnostic_submit(self):
        with self.assertRaisesRegex(GeometryLockedRuntimeError, "--diagnostic-submit"):
            run_comfy_geometry_locked(self.manifest, permission_path=self.permission_path)

    def test_full_cloud_to_s6_path_keeps_production_gates_blocked(self):
        fake = FakeCloudClient({
            "left.png": Image.new("RGB", (4, 4), (200, 1, 1)),
            "right.png": Image.new("RGB", (4, 4), (1, 200, 1)),
        })
        with patch("ige.comfy.geometry_locked_runtime.audit_api_workflow_live", side_effect=self._audit):
            receipt = run_comfy_geometry_locked(
                self.manifest,
                permission_path=self.permission_path,
                diagnostic_submit=True,
                client=fake,
            )
        self.assertEqual(receipt["execution_kind"], "comfy_cloud_job_plus_local_s6_compositor")
        self.assertIn("FakeCloudClient", receipt["cloud_transport"])
        self.assertEqual(receipt["s6_local_compositor"]["status"], "PASS_LOCAL_CORE_ONLY_COMPOSITOR")
        self.assertFalse(receipt["candidate_accepted"])
        self.assertEqual(receipt["geometry_contract_sha256"], sha(self.geometry_contract))
        self.assertFalse(receipt["execution_allowed"])
        self.assertFalse(receipt["global_coordinate_noise_verified"])
        self.assertFalse(receipt["cloud_weight_sha_verified"])
        self.assertEqual(receipt["s7_status"], "NOT_PERFORMED")
        self.assertEqual(len(fake.uploaded), 2)
        self.assertEqual(fake.submitted["load-left"]["inputs"]["image"], "LEFT.png")
        master = Image.open(receipt["s6_local_compositor"]["master_path"]).convert("RGB")
        self.assertEqual(master.size, (8, 4))

    def test_permission_receipt_must_bind_all_frozen_inputs(self):
        permission = json.loads(self.permission_path.read_text())
        permission["canvas_sha256"] = "f" * 64
        self.permission_path.write_text(json.dumps(permission), encoding="utf-8")
        fake = FakeCloudClient()
        with self.assertRaisesRegex(GeometryLockedRuntimeError, "SHA/frame binding mismatch"):
            with patch("ige.comfy.geometry_locked_runtime.audit_api_workflow_live", side_effect=self._audit):
                run_comfy_geometry_locked(
                    self.manifest,
                    permission_path=self.permission_path,
                    diagnostic_submit=True,
                    client=fake,
                )
        self.assertEqual(fake.uploaded, [])

    def test_output_size_mismatch_fails_without_auto_resize(self):
        left = self.root / "left-bad.png"
        right = self.root / "right-good.png"
        Image.new("RGB", (3, 4), (1, 2, 3)).save(left)
        Image.new("RGB", (4, 4), (1, 2, 3)).save(right)
        manifest = json.loads(self.manifest.read_text())
        with self.assertRaisesRegex(GeometryLockedError, "resizing is forbidden"):
            compose_core_only_master(
                base_canvas_path=self.canvas,
                approved_mask_path=self.approved,
                protected_mask_path=self.protected,
                tile_plan=manifest["tile_plan"],
                tile_outputs=[{"tile_id": "LEFT", "path": str(left), "sha256": sha(left)},
                              {"tile_id": "RIGHT", "path": str(right), "sha256": sha(right)}],
                canvas_sha256=manifest["canvas"]["sha256"],
                output_path=self.root / "bad-master.png",
            )


if __name__ == "__main__":
    unittest.main()
