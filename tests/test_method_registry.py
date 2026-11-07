from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ige.method_registry import (
    MethodRegistry, MethodRegistryError, evaluate_s0_s7, file_sha256,
    validate_registry_payload,
)
from ige.comfy.tile_core_halo_ledger import (
    CODE_LEDGER_REQUIRED,
    CODE_S2_BIND,
    synthetic_halo_write_ledger,
    synthetic_valid_two_tile_ledger,
)

REGISTRY = Path(__file__).parents[1] / "src" / "ige" / "data" / "method_registry.json"
SIAX_SHA256 = "560424d9f68625713fc47e9e7289a98aabe1d744e1cd6a9ae5a35e9957fd127e"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bound_siax_ledger(canvas_sha: str) -> dict:
    """Single-tile instrumented ledger matching the Driver S5 fixture (schema 0.2)."""
    return {
        "schema": "ige-tile-core-halo-ledger/0.2",
        "coordinate_frame": "native_4x_master",
        "canvas_sha256": canvas_sha,
        "canvas_size_wh": [16, 16],
        "coverage_target": {"kind": "rect_union", "rects": [[0, 0, 16, 16]]},
        "tiles": [{
            "tile_id": "whole-canvas",
            "read_bounds": [0, 0, 16, 16],
            "core_bounds": [0, 0, 16, 16],
            "output_sha256": "b" * 64,
            "halo_write_pixels": 0,
            "wrote_halo": False,
            "coordinate_frame": "native_4x_master",
            "write_receipt": {"wrote_core": True, "wrote_halo": False, "halo_write_pixels": 0},
        }],
        "evidence_grade": "runtime_instrumented_adapter",
        "non_claims": [
            "Synthetic unit-test ledger; not live Siax inference proof.",
            "Does not unlock Flux or set execution_allowed=true.",
        ],
    }


class MethodRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = MethodRegistry.load(REGISTRY)
        cls.payload = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_registry_validates_and_resolves_existing_skills(self):
        self.assertEqual(validate_registry_payload(self.payload), [])
        self.assertEqual(self.registry.resolve_skill("SIAX4X")["method_id"], "SIAX4X_TILE_CORE_SR")
        self.assertEqual(self.registry.resolve_skill("DETAIL6")["method_id"], "DETAIL6_MATERIAL_RESIDUAL")
        self.assertEqual(self.registry.resolve("SIAX4X_TILE_CORE_SR")["model_sha256"], SIAX_SHA256)

    def test_duplicate_method_alias_and_permission_grant_rejected(self):
        duplicate = json.loads(json.dumps(self.payload))
        duplicate["methods"].append(json.loads(json.dumps(duplicate["methods"][0])))
        self.assertTrue(any("duplicate method_id" in e for e in validate_registry_payload(duplicate)))
        alias = json.loads(json.dumps(self.payload))
        alias["methods"][1]["skill_aliases"].append("SIAX4X")
        self.assertTrue(any("duplicate skill_alias" in e for e in validate_registry_payload(alias)))
        permission = json.loads(json.dumps(self.payload))
        permission["methods"][0]["edit_permission"] = True
        self.assertTrue(any("edit_permission" in e for e in validate_registry_payload(permission)))

    def test_unknown_method_fails_closed(self):
        with self.assertRaises(MethodRegistryError):
            self.registry.resolve("UNKNOWN_METHOD")

    def test_flux_workflow_candidate_stays_blocked_even_when_flags_are_true(self):
        context = {k: True for k in (
            "s0_source_sha_verified", "topology_verified", "geometry_contract_verified",
            "tile_plan_verified", "comfy_nodes_available", "backend_model_inventory_verified",
            "tile_conditioning_verified", "global_noise_field_verified", "approved_masks_verified",
            "human_permission", "backend_adapter_available",
        )}
        context.update({"topology_state": "absent", "topology_human_verified": True})
        result = self.registry.evaluate("FLUX_HR_TILE_IMG2IMG", context)
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(result["status"], "BLOCKED_BACKEND_NOT_VERIFIED")
        self.assertFalse(result["edit_permission"])

    def test_siax_needs_preconditions_and_permission_is_external(self):
        denied = self.registry.evaluate("SIAX4X_TILE_CORE_SR", {
            "s0_source_sha_verified": True, "topology_verified": True,
            "topology_state": "absent", "topology_human_verified": True,
        })
        self.assertFalse(denied["execution_allowed"])
        self.assertIn("E_HUMAN_EDIT_PERMISSION_MISSING", denied["blockers"])
        allowed = self.registry.evaluate("SIAX4X_TILE_CORE_SR", {
            **{k: True for k in (
                "s0_source_sha_verified", "topology_verified", "checkpoint_sha_verified",
                "license_acknowledged", "geometry_contract_verified", "tile_plan_verified",
                "approved_masks_verified", "human_permission", "backend_adapter_available",
            )},
            "topology_state": "absent", "topology_human_verified": True,
        })
        self.assertTrue(allowed["execution_allowed"])
        self.assertFalse(allowed["edit_permission"])

    def _bundle(self, root: Path):
        base = root / "base.png"
        base.write_bytes(b"base-fixture")
        source_sha = sha(base.read_bytes())

        canvas = root / "coordinate-canvas.png"
        Image.new("RGB", (16, 16), (16, 16, 16)).save(canvas)
        canvas_sha = file_sha256(canvas)

        approved = root / "approved.png"
        approved_image = Image.new("L", (16, 16), 0)
        approved_image.putpixel((0, 0), 255)
        approved_image.save(approved)
        protected = root / "protected.png"
        protected_image = Image.new("L", (16, 16), 0)
        protected_image.putpixel((15, 15), 255)
        protected_image.save(protected)

        output = root / "candidate.png"
        candidate_image = Image.new("RGB", (16, 16), (16, 16, 16))
        candidate_image.putpixel((0, 0), (250, 250, 250))
        candidate_image.save(output)
        output_sha = file_sha256(output)

        model = root / "fixture-model.bin"
        model.write_bytes(b"synthetic-model-fixture")
        model_sha = SIAX_SHA256  # mocked below; fixture is not the real checkpoint

        tile_trace = [{
            "tile_id": "whole-canvas",
            "read_bounds": [0, 0, 16, 16],
            "core_bounds": [0, 0, 16, 16],
        }]
        ledger = bound_siax_ledger(canvas_sha)
        ledger_path = root / "runtime_tile_ledger.json"
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
        metadata = {
            "model_id": "4x_NMKD-Siax_200k",
            "checkpoint_sha256": model_sha,
            "input_sha256": source_sha,
            "output_sha256": output_sha,
            "tile_trace": tile_trace,
        }
        metadata_path = root / "siax_metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        tile_trace_sha = hashlib.sha256(
            json.dumps(tile_trace, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        return {
            "S0": {"source_path": str(base), "source_sha256": source_sha, "source_frozen": True, "immutable": True},
            "S1": {"read_receipt": {"source_sha256": source_sha, "candidate_only": True, "observations": {
                "topology_error": {"state": "absent", "verification": "human_verified"}
            }}},
            "S2": {"geometry_contract": {
                "source_sha256": source_sha, "canvas_path": str(canvas), "canvas_sha256": canvas_sha,
                "coordinate_frame": "native_4x_master", "geometry_human_verified": True, "model_scale": 4,
                "object_transform": {"kind": "identity", "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
                "tile_size": 256, "tile_context": 8, "delivery_resampled": False,
            }},
            "S3": {"permission": {
                "human_reviewed": True, "permission_granted": True, "base_sha256": source_sha,
                "reviewer_ref": "synthetic-test-reviewer", "reviewed_at": "2026-11-08T00:00:00+08:00",
                "coordinate_canvas_sha256": canvas_sha, "approved_edit_mask_path": str(approved),
                "approved_edit_mask_sha256": file_sha256(approved), "protected_mask_path": str(protected),
                "protected_mask_sha256": file_sha256(protected), "target_regions": ["metal_mesh"],
            }},
            "S4": {"method_id": "SIAX4X_TILE_CORE_SR", "method_context": {
                "checkpoint_sha_verified": True, "license_acknowledged": True,
                "tile_plan_verified": True, "backend_adapter_available": True,
            }},
            "S5": {"backend_receipt": {
                "real_backend_call": True, "receipt_verified": True, "backend_id": "spandrel_siax_4x",
                "model_id": "4x_NMKD-Siax_200k", "model_sha256": model_sha, "model_path": str(model),
                "parent_source_sha256": source_sha, "input_sha256s": [source_sha, sha(b"tile")],
                "output_sha256": output_sha, "output_path": str(output), "request_id": "fixture-run-1",
                "parameters": {"scale": 4, "tile_size": 256, "tile_pad": 8},
                "adapter_metadata_path": str(metadata_path), "adapter_metadata_sha256": file_sha256(metadata_path),
                "tile_trace_sha256": tile_trace_sha,
                "tile_ledger_path": str(ledger_path), "tile_ledger_sha256": file_sha256(ledger_path),
            }},
            "S6": {"return_audit": {
                "source_sha256": source_sha, "output_sha256": output_sha, "output_path": str(output),
                "core_only_writes": True, "halo_write_pixels": 0, "core_overlap_pixels": 0,
                "coverage_gap_pixels": 0, "outside_authorized_changed_pixels": 0,
                "implicit_resize": False, "implicit_flip": False,
                "tile_core_halo_ledger_path": str(ledger_path),
                "tile_core_halo_ledger_sha256": file_sha256(ledger_path),
            }},
            "S7": {"acceptance": {
                "independent_reloaded": True, "source_sha256": source_sha, "saved_output_sha256": output_sha,
                "saved_output_path": str(output), "human_visual_review": "PASS", "visual_review_source": "human",
                "reviewer_ref": "synthetic-test-reviewer", "reviewed_at": "2026-11-08T00:01:00+08:00",
                "gate_results": {k: "PASS" for k in (
                    "identity", "pose", "topology", "geometry", "coverage",
                    "permission", "protected_region", "provenance", "visual_quality",
                )},
            }},
        }

    def _audit(self, bundle):
        real_hash = file_sha256
        model_path = bundle["S5"]["backend_receipt"]["model_path"]
        def hash_with_fixture(path):
            if Path(path) == Path(model_path):
                return SIAX_SHA256
            return real_hash(path)
        with patch("ige.method_registry.file_sha256", side_effect=hash_with_fixture):
            return evaluate_s0_s7(bundle, self.registry)

    def test_complete_s0_s7_evidence_bundle_passes_pixel_audit_but_grants_no_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self._audit(self._bundle(Path(directory)))
        self.assertEqual(report["status"], "ACCEPTED_CANDIDATE")
        self.assertTrue(all(stage["status"] == "PASS" for stage in report["stages"]))
        self.assertEqual(report["stages"][6]["pixel_audit"]["changed_pixels_outside_authorized_region"], 0)
        self.assertFalse(report["edit_permission"])
        self.assertFalse(report["execution_allowed"])
        self.assertTrue(report["candidate_accepted"])

    def test_invalid_source_freeze_blocks_s0(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S0"]["source_sha256"] = "0" * 64
            report = self._audit(bundle)
        self.assertEqual(report["stages"][0]["status"], "BLOCKED")
        self.assertEqual(report["stages"][1]["status"], "NOT_RUN")

    def test_wrong_root_mask_blocks_s3_and_invalidates_downstream(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S3"]["permission"]["base_sha256"] = "f" * 64
            report = self._audit(bundle)
        self.assertEqual(report["stages"][3]["status"], "BLOCKED")
        self.assertTrue(all(stage["status"] == "NOT_RUN" for stage in report["stages"][4:]))

    def test_halo_write_or_outside_pixel_change_blocks_s6(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S6"]["return_audit"]["halo_write_pixels"] = 1
            report = self._audit(bundle)
        self.assertEqual(report["stages"][6]["status"], "BLOCKED")
        self.assertEqual(report["stages"][7]["status"], "NOT_RUN")

    def test_actual_outside_pixel_change_blocks_even_when_json_claims_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            output = Path(bundle["S6"]["return_audit"]["output_path"])
            with Image.open(output) as opened:
                candidate = opened.convert("RGB")
            candidate.putpixel((8, 8), (255, 0, 0))  # outside the approved one-pixel mask
            candidate.save(output)
            new_sha = file_sha256(output)
            bundle["S5"]["backend_receipt"]["output_sha256"] = new_sha
            metadata_path = Path(bundle["S5"]["backend_receipt"]["adapter_metadata_path"])
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["output_sha256"] = new_sha
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            bundle["S5"]["backend_receipt"]["adapter_metadata_sha256"] = file_sha256(metadata_path)
            bundle["S6"]["return_audit"]["output_sha256"] = new_sha
            bundle["S7"]["acceptance"]["saved_output_sha256"] = new_sha
            report = self._audit(bundle)
        self.assertEqual(report["stages"][6]["status"], "BLOCKED")
        self.assertEqual(report["stages"][7]["status"], "NOT_RUN")

    def test_mandatory_tile_ledger_pass_does_not_grant_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            report = self._audit(bundle)
        self.assertEqual(report["status"], "ACCEPTED_CANDIDATE")
        self.assertEqual(report["stages"][6]["status"], "PASS")
        self.assertIsNotNone(report["stages"][6].get("tile_ledger"))
        self.assertEqual(report["stages"][6]["tile_ledger"]["overall_status"], "PASS")
        self.assertFalse(report["execution_allowed"])
        self.assertFalse(report["edit_permission"])

    def test_mandatory_tile_ledger_missing_blocks_s6(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S6"]["return_audit"].pop("tile_core_halo_ledger", None)
            bundle["S6"]["return_audit"].pop("tile_core_halo_ledger_path", None)
            bundle["S6"]["return_audit"].pop("tile_core_halo_ledger_sha256", None)
            report = self._audit(bundle)
        self.assertEqual(report["stages"][6]["status"], "BLOCKED")
        self.assertEqual(report["stages"][7]["status"], "NOT_RUN")
        self.assertFalse(report["execution_allowed"])
        ledger = report["stages"][6].get("tile_ledger") or {}
        self.assertEqual(ledger.get("overall_status"), "FAIL")
        self.assertIn(CODE_LEDGER_REQUIRED, ledger.get("blockers") or [])
        self.assertTrue(
            any("E_TILE_LEDGER_REQUIRED" in r for r in report["stages"][6].get("reasons") or [])
        )

    def test_tile_ledger_s2_bind_mismatch_blocks_s6(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bad = synthetic_valid_two_tile_ledger(
                coordinate_frame="native_4x_master",
                canvas_sha256="f" * 64,  # not the real S2 canvas sha
            )
            bundle["S6"]["return_audit"]["tile_core_halo_ledger"] = bad
            report = self._audit(bundle)
        self.assertEqual(report["stages"][6]["status"], "BLOCKED")
        ledger = report["stages"][6].get("tile_ledger") or {}
        self.assertEqual(ledger.get("overall_status"), "FAIL")
        self.assertIn(CODE_S2_BIND, ledger.get("blockers") or [])
        self.assertFalse(report["execution_allowed"])

    def test_mandatory_tile_ledger_halo_write_blocks_s6(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            # Halo-write ledger must still carry matching S2 bind fields to reach halo check.
            canvas_sha = bundle["S2"]["geometry_contract"]["canvas_sha256"]
            failing = synthetic_halo_write_ledger()
            failing["coordinate_frame"] = "native_4x_master"
            failing["canvas_sha256"] = canvas_sha
            for tile in failing["tiles"]:
                tile["coordinate_frame"] = "native_4x_master"
            bundle["S6"]["return_audit"]["tile_core_halo_ledger"] = failing
            report = self._audit(bundle)
        self.assertEqual(report["stages"][6]["status"], "BLOCKED")
        self.assertEqual(report["stages"][7]["status"], "NOT_RUN")
        self.assertFalse(report["execution_allowed"])
        ledger = report["stages"][6].get("tile_ledger") or {}
        self.assertEqual(ledger.get("overall_status"), "FAIL")
        self.assertIn("E_TILE_HALO_WRITE", ledger.get("blockers") or [])

    def test_missing_s7_gate_never_accepts(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S7"]["acceptance"]["gate_results"].pop("visual_quality")
            report = self._audit(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["stages"][7]["status"], "BLOCKED")

    def test_soft_mask_and_approved_protected_overlap_block_s3(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            approved_path = Path(bundle["S3"]["permission"]["approved_edit_mask_path"])
            soft = Image.new("L", (16, 16), 0)
            soft.putpixel((0, 0), 128)
            soft.save(approved_path)
            bundle["S3"]["permission"]["approved_edit_mask_sha256"] = file_sha256(approved_path)
            report = self._audit(bundle)
            self.assertEqual(report["stages"][3]["status"], "BLOCKED")

        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            protected_path = Path(bundle["S3"]["permission"]["protected_mask_path"])
            with Image.open(protected_path) as opened:
                protected = opened.convert("L")
            protected.putpixel((0, 0), 255)
            protected.save(protected_path)
            bundle["S3"]["permission"]["protected_mask_sha256"] = file_sha256(protected_path)
            report = self._audit(bundle)
            self.assertEqual(report["stages"][3]["status"], "BLOCKED")

    def test_registry_pinned_model_hash_mismatch_blocks_s5(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S5"]["backend_receipt"]["model_sha256"] = "0" * 64
            report = self._audit(bundle)
        self.assertEqual(report["stages"][5]["status"], "BLOCKED")
        self.assertEqual(report["stages"][6]["status"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
