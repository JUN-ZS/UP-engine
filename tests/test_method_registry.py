from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ige.method_registry import MethodRegistry, MethodRegistryError, evaluate_s0_s7, validate_registry_payload

REGISTRY = Path(__file__).parents[1] / "src" / "ige" / "data" / "method_registry.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MethodRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = MethodRegistry.load(REGISTRY)
        cls.payload = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_registry_validates_and_resolves_existing_skills(self):
        self.assertEqual(validate_registry_payload(self.payload), [])
        self.assertEqual(self.registry.resolve_skill("SIAX4X")["method_id"], "SIAX4X_TILE_CORE_SR")
        self.assertEqual(self.registry.resolve_skill("DETAIL6")["method_id"], "DETAIL6_MATERIAL_RESIDUAL")

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
        canvas_sha = sha(b"native-4x-coordinate-canvas")
        approved, protected = root / "approved.bin", root / "protected.bin"
        approved.write_bytes(b"approved-mask")
        protected.write_bytes(b"protected-mask")
        output_sha = sha(b"candidate-output")
        return {
            "S0": {"source_path": str(base), "source_sha256": source_sha, "source_frozen": True, "immutable": True},
            "S1": {"read_receipt": {"source_sha256": source_sha, "candidate_only": True, "observations": {
                "topology_error": {"state": "absent", "verification": "human_verified"}
            }}},
            "S2": {"geometry_contract": {
                "source_sha256": source_sha, "canvas_sha256": canvas_sha, "coordinate_frame": "native_4x_master",
                "geometry_human_verified": True, "model_scale": 4,
                "object_transform": {"kind": "identity"}, "tile_size": 256, "tile_context": 8,
                "delivery_resampled": False,
            }},
            "S3": {"permission": {
                "human_reviewed": True, "permission_granted": True, "base_sha256": source_sha,
                "coordinate_canvas_sha256": canvas_sha, "approved_edit_mask_path": str(approved),
                "approved_edit_mask_sha256": sha(approved.read_bytes()), "protected_mask_path": str(protected),
                "protected_mask_sha256": sha(protected.read_bytes()), "target_regions": ["metal_mesh"],
            }},
            "S4": {"method_id": "SIAX4X_TILE_CORE_SR", "method_context": {
                "checkpoint_sha_verified": True, "license_acknowledged": True,
                "tile_plan_verified": True, "backend_adapter_available": True,
            }},
            "S5": {"backend_receipt": {
                "real_backend_call": True, "receipt_verified": True, "backend_id": "spandrel_siax_4x",
                "model_id": "4x_NMKD-Siax_200k", "model_sha256": sha(b"model"),
                "parent_source_sha256": source_sha, "input_sha256s": [source_sha, sha(b"tile")],
                "output_sha256": output_sha, "request_id": "fixture-run-1",
                "parameters": {"scale": 4, "tile_size": 256, "tile_pad": 8},
            }},
            "S6": {"return_audit": {
                "source_sha256": source_sha, "output_sha256": output_sha, "core_only_writes": True,
                "halo_write_pixels": 0, "core_overlap_pixels": 0, "coverage_gap_pixels": 0,
                "outside_authorized_changed_pixels": 0, "implicit_resize": False, "implicit_flip": False,
            }},
            "S7": {"acceptance": {
                "independent_reloaded": True, "source_sha256": source_sha, "saved_output_sha256": output_sha,
                "human_visual_review": "PASS", "visual_review_source": "human",
                "gate_results": {k: "PASS" for k in (
                    "identity", "pose", "topology", "geometry", "coverage",
                    "permission", "protected_region", "provenance", "visual_quality",
                )},
            }},
        }

    def test_complete_s0_s7_evidence_bundle_passes_as_audited_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            report = evaluate_s0_s7(self._bundle(Path(directory)), self.registry)
        self.assertEqual(report["status"], "ACCEPTED_CANDIDATE")
        self.assertTrue(all(stage["status"] == "PASS" for stage in report["stages"]))
        self.assertFalse(report["edit_permission"])

    def test_invalid_source_freeze_blocks_s0(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S0"]["source_sha256"] = "0" * 64
            report = evaluate_s0_s7(bundle, self.registry)
        self.assertEqual(report["stages"][0]["status"], "BLOCKED")
        self.assertEqual(report["stages"][1]["status"], "NOT_RUN")

    def test_wrong_root_mask_blocks_s3_and_invalidates_downstream(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S3"]["permission"]["base_sha256"] = "f" * 64
            report = evaluate_s0_s7(bundle, self.registry)
        self.assertEqual(report["stages"][3]["status"], "BLOCKED")
        self.assertTrue(all(stage["status"] == "NOT_RUN" for stage in report["stages"][4:]))

    def test_halo_write_or_outside_pixel_change_blocks_s6(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S6"]["return_audit"]["halo_write_pixels"] = 1
            report = evaluate_s0_s7(bundle, self.registry)
        self.assertEqual(report["stages"][6]["status"], "BLOCKED")
        self.assertEqual(report["stages"][7]["status"], "NOT_RUN")

    def test_missing_s7_gate_never_accepts(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = self._bundle(Path(directory))
            bundle["S7"]["acceptance"]["gate_results"].pop("visual_quality")
            report = evaluate_s0_s7(bundle, self.registry)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["stages"][7]["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
