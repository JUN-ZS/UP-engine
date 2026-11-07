from __future__ import annotations

import unittest
from pathlib import Path

from ige.comfy.global_noise_contract import (
    EVIDENCE_GRADE_LIVE,
    EVIDENCE_GRADE_STATIC,
    EVIDENCE_GRADE_SYNTHETIC,
    FAILURE_NOISE,
    FIELD_KIND_COORDINATE_INDEXED,
    FIELD_KIND_INDEPENDENT_SEED_PER_TILE,
    FIELD_KIND_SHARED_SEED_ONLY,
    FIELD_KIND_UNKNOWN,
    MECHANISM_COORDINATE_INDEXED_GENERATOR,
    MECHANISM_GLOBAL_LATENT_CROP,
    MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT,
    MECHANISMS,
    RECEIPT_SCHEMA,
    TEST_ID_NOISE,
    build_live_capture_receipt_template,
    build_synthetic_mechanism_receipt,
    build_unverified_shared_seed_receipt,
    classify_noise_evidence,
    evaluate_all_mechanism_synthetic_acceptances,
    evaluate_mechanism_synthetic_acceptance,
    fill_tile_coordinate_indexed,
    fill_tile_independent_rng,
    mechanism_contract_specs,
    overlap_region,
    probe_overlap_equality,
    synthetic_coordinate_indexed_overlap_proof,
    synthetic_global_latent_crop_overlap_proof,
    synthetic_global_then_local_refinement_acceptance,
    synthetic_identical_local_arrays_seam_counterexample,
    synthetic_shared_seed_independent_draws_counterexample,
    validate_receipt_payload,
)
from ige.comfy.workflow_static_audit import audit_comfy_workflows

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "comfy"
UI = FIXTURES / "workflow_ige_v03_dev_fp8.json"
API = FIXTURES / "workflow_cloud_api_prompt_v0.5.json"
SCHEMA = ROOT / "schemas" / "global_noise_field_receipt.schema.json"
FIXTURE_SEED = 909424749197426


class GlobalNoiseContractTests(unittest.TestCase):
    def test_schema_file_exists(self):
        self.assertTrue(SCHEMA.is_file())
        raw = SCHEMA.read_text(encoding="utf-8")
        self.assertIn("noise_synthetic_ok", raw)
        self.assertIn("noise_live_verified", raw)
        self.assertIn("live_capture", raw)
        self.assertIn("global_then_local_refinement", raw)

    def test_coordinate_indexed_overlap_equality(self):
        proof = synthetic_coordinate_indexed_overlap_proof(seed=FIXTURE_SEED)
        self.assertEqual(proof["field_kind"], FIELD_KIND_COORDINATE_INDEXED)
        self.assertEqual(proof["mechanism"], MECHANISM_COORDINATE_INDEXED_GENERATOR)
        self.assertEqual(proof["evidence_grade"], EVIDENCE_GRADE_SYNTHETIC)
        self.assertTrue(proof["verified_synthetic"])
        self.assertTrue(proof["noise_synthetic_ok"])
        self.assertFalse(proof["noise_live_verified"])
        self.assertTrue(proof["overlap_probe"]["all_equal"])
        self.assertGreater(proof["overlap_probe"]["overlap_count"], 0)

    def test_global_latent_crop_overlap_equality(self):
        proof = synthetic_global_latent_crop_overlap_proof(seed=FIXTURE_SEED)
        self.assertEqual(proof["mechanism"], MECHANISM_GLOBAL_LATENT_CROP)
        self.assertTrue(proof["noise_synthetic_ok"])
        self.assertFalse(proof["noise_live_verified"])
        self.assertTrue(proof["overlap_probe"]["all_equal"])
        self.assertEqual(proof["global_latent_shape"], [4, 8, 1])

    def test_global_then_local_refinement_architectural(self):
        proof = synthetic_global_then_local_refinement_acceptance(seed=FIXTURE_SEED)
        self.assertEqual(proof["mechanism"], MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT)
        self.assertTrue(proof["architectural_vs_seed_tweak"])
        self.assertTrue(proof["noise_synthetic_ok"])
        self.assertFalse(proof["noise_live_verified"])
        self.assertTrue(proof["global_stage"]["overlap_probe"]["all_equal"])
        self.assertTrue(proof["local_refinement_stage"]["overlap_probe"]["all_equal"])
        self.assertTrue(proof["seed_tweak_counterexample"]["demonstrates_not_architecture"])

    def test_shared_seed_independent_draws_mismatch(self):
        counter = synthetic_shared_seed_independent_draws_counterexample(seed=FIXTURE_SEED)
        self.assertEqual(counter["field_kind"], FIELD_KIND_SHARED_SEED_ONLY)
        self.assertTrue(counter["demonstrates_not_global"])
        self.assertFalse(counter["noise_synthetic_ok"])
        self.assertFalse(counter["noise_live_verified"])
        self.assertGreater(counter["overlap_probe"]["mismatch_count"], 0)
        self.assertFalse(counter["overlap_probe"]["all_equal"])

    def test_identical_local_arrays_seam_without_coord_indexing(self):
        counter = synthetic_identical_local_arrays_seam_counterexample(seed=FIXTURE_SEED)
        self.assertTrue(counter["identical_local_arrays"])
        self.assertTrue(counter["demonstrates_seam_without_coord_indexing"])
        self.assertGreater(counter["overlap_probe"]["mismatch_count"], 0)
        self.assertFalse(counter["noise_synthetic_ok"])
        self.assertFalse(counter["noise_live_verified"])

    def test_manual_fills_agree_on_coordinate_field_disagree_on_independent_rng(self):
        tile_a = ((0, 0), (4, 4))
        tile_b = ((2, 0), (4, 4))
        coords = overlap_region(tile_a[0], tile_a[1], tile_b[0], tile_b[1])
        self.assertEqual(len(coords), 8)  # 2x4 overlap

        ca = fill_tile_coordinate_indexed(seed=7, origin_xy=tile_a[0], size_wh=tile_a[1])
        cb = fill_tile_coordinate_indexed(seed=7, origin_xy=tile_b[0], size_wh=tile_b[1])
        self.assertTrue(probe_overlap_equality(ca, cb, coords)["all_equal"])

        ia = fill_tile_independent_rng(seed=7, origin_xy=tile_a[0], size_wh=tile_a[1])
        ib = fill_tile_independent_rng(seed=7, origin_xy=tile_b[0], size_wh=tile_b[1])
        self.assertFalse(probe_overlap_equality(ia, ib, coords)["all_equal"])

    def test_mechanism_specs_cover_three_contracts(self):
        specs = mechanism_contract_specs()
        self.assertEqual(set(specs), set(MECHANISMS))
        self.assertFalse(specs[MECHANISM_GLOBAL_LATENT_CROP]["architectural_vs_seed_tweak"])
        self.assertFalse(
            specs[MECHANISM_COORDINATE_INDEXED_GENERATOR]["architectural_vs_seed_tweak"]
        )
        self.assertTrue(
            specs[MECHANISM_GLOBAL_THEN_LOCAL_REFINEMENT]["architectural_vs_seed_tweak"]
        )
        for spec in specs.values():
            self.assertGreaterEqual(len(spec["acceptance_criteria"]), 3)
            self.assertTrue(spec["cost_notes"])

    def test_all_mechanism_synthetic_acceptances_pass_live_unverified(self):
        catalog = evaluate_all_mechanism_synthetic_acceptances()
        self.assertTrue(catalog["noise_synthetic_ok"])
        self.assertFalse(catalog["noise_live_verified"])
        self.assertEqual(catalog["synthetic_status"], "PASS")
        self.assertEqual(catalog["live_status"], "UNVERIFIED")
        for mid in MECHANISMS:
            row = catalog["mechanisms"][mid]
            self.assertEqual(row["synthetic_status"], "PASS")
            self.assertFalse(row["noise_live_verified"])
            self.assertEqual(row["live_status"], "UNVERIFIED")

    def test_classify_shared_seed_only_from_static_bits(self):
        result = classify_noise_evidence(
            workflow_static_bits={
                "models": {"noise_seed": FIXTURE_SEED},
                "noise_nodes": [{"id": "25", "noise_seed": FIXTURE_SEED}],
            }
        )
        self.assertEqual(result["field_kind"], FIELD_KIND_SHARED_SEED_ONLY)
        self.assertEqual(result["evidence_grade"], EVIDENCE_GRADE_STATIC)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["noise_synthetic_ok"])
        self.assertFalse(result["noise_live_verified"])
        self.assertEqual(result["synthetic_status"], "FAIL")
        self.assertEqual(result["check"]["code"], FAILURE_NOISE)
        self.assertEqual(result["evidence"]["test_id"], TEST_ID_NOISE)
        self.assertIn("same seed", result["detail"].lower())

    def test_classify_no_seed_unknown(self):
        result = classify_noise_evidence(workflow_static_bits={"inventories": []})
        self.assertEqual(result["field_kind"], FIELD_KIND_UNKNOWN)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["noise_synthetic_ok"])
        self.assertFalse(result["noise_live_verified"])

    def test_classify_independent_seed_per_tile(self):
        result = classify_noise_evidence(
            workflow_static_bits={
                "field_kind": FIELD_KIND_INDEPENDENT_SEED_PER_TILE,
                "observed_seeds": [1, 2],
            }
        )
        self.assertEqual(result["field_kind"], FIELD_KIND_INDEPENDENT_SEED_PER_TILE)
        self.assertEqual(result["status"], "FAIL")

    def test_synthetic_receipt_passes_synthetic_not_live_gate(self):
        """Synthetic PASS must not clear E_NOISE live gate / noise_live_verified."""
        receipt = build_synthetic_mechanism_receipt(
            mechanism=MECHANISM_COORDINATE_INDEXED_GENERATOR
        )
        self.assertEqual(validate_receipt_payload(receipt), [])
        self.assertTrue(receipt["noise_synthetic_ok"])
        self.assertFalse(receipt["noise_live_verified"])
        self.assertEqual(receipt["evidence_grade"], EVIDENCE_GRADE_SYNTHETIC)

        result = classify_noise_evidence(receipt=receipt)
        self.assertEqual(result["field_kind"], FIELD_KIND_COORDINATE_INDEXED)
        self.assertTrue(result["noise_synthetic_ok"])
        self.assertFalse(result["noise_live_verified"])
        self.assertEqual(result["synthetic_status"], "PASS")
        self.assertEqual(result["live_status"], "UNVERIFIED")
        # Live gate for E_NOISE remains FAIL
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("synthetic", result["detail"].lower())
        self.assertIn("live", result["detail"].lower())

    def test_legacy_verified_synthetic_receipt_does_not_claim_live(self):
        proof = synthetic_coordinate_indexed_overlap_proof(seed=FIXTURE_SEED)
        receipt = {
            "schema": "ige-global-noise-field-receipt/0.1",
            "field_kind": FIELD_KIND_COORDINATE_INDEXED,
            "coordinate_frame": "global_canvas_xy",
            "seed": FIXTURE_SEED,
            "tile_origins": proof["tile_origins"],
            "tile_sizes": proof["tile_sizes"],
            "overlap_probe": proof["overlap_probe"],
            "verified": True,
            "synthetic": True,
            "failure_code": FAILURE_NOISE,
            "test_id": TEST_ID_NOISE,
            "non_claims": ["Synthetic proof only."],
        }
        # 0.1 legacy still structurally OK (evidence_grade optional on 0.1)
        self.assertEqual(validate_receipt_payload(receipt), [])
        result = classify_noise_evidence(receipt=receipt)
        self.assertTrue(result["noise_synthetic_ok"])
        self.assertFalse(result["noise_live_verified"])
        self.assertEqual(result["status"], "FAIL")  # live gate

    def test_synthetic_cannot_set_live_verified_in_validation(self):
        receipt = build_synthetic_mechanism_receipt(
            mechanism=MECHANISM_GLOBAL_LATENT_CROP
        )
        receipt["noise_live_verified"] = True
        errors = validate_receipt_payload(receipt)
        self.assertTrue(any("noise_live_verified" in e for e in errors))

    def test_live_template_stays_unverified(self):
        tmpl = build_live_capture_receipt_template(
            mechanism=MECHANISM_COORDINATE_INDEXED_GENERATOR,
            host_id="DESKTOP-EXAMPLE",
        )
        self.assertEqual(tmpl["evidence_grade"], EVIDENCE_GRADE_LIVE)
        self.assertFalse(tmpl["noise_live_verified"])
        self.assertFalse(tmpl["verified"])
        # Incomplete live proof → classify as not live PASS
        result = classify_noise_evidence(receipt=tmpl)
        self.assertFalse(result["noise_live_verified"])
        self.assertEqual(result["status"], "FAIL")

    def test_unverified_shared_seed_receipt_fails_validation_when_verified_true_wrong_kind(self):
        bad = build_unverified_shared_seed_receipt(seed=FIXTURE_SEED, tile_origins=[[0, 0]])
        bad["verified"] = True
        errors = validate_receipt_payload(bad)
        self.assertTrue(any("coordinate_indexed" in e for e in errors))

    def test_build_unverified_receipt_valid(self):
        receipt = build_unverified_shared_seed_receipt(
            seed=FIXTURE_SEED,
            tile_origins=[[0, 0], [2, 0]],
        )
        self.assertEqual(validate_receipt_payload(receipt), [])
        self.assertFalse(receipt["verified"])
        self.assertFalse(receipt["noise_synthetic_ok"])
        self.assertFalse(receipt["noise_live_verified"])
        self.assertEqual(receipt["field_kind"], FIELD_KIND_SHARED_SEED_ONLY)
        self.assertEqual(receipt["evidence_grade"], EVIDENCE_GRADE_STATIC)

    def test_each_mechanism_builds_valid_synthetic_receipt(self):
        for mech in sorted(MECHANISMS):
            receipt = build_synthetic_mechanism_receipt(mechanism=mech)
            self.assertEqual(validate_receipt_payload(receipt), [], msg=mech)
            self.assertTrue(receipt["noise_synthetic_ok"], msg=mech)
            self.assertFalse(receipt["noise_live_verified"], msg=mech)
            acc = evaluate_mechanism_synthetic_acceptance(mech)
            self.assertEqual(acc["synthetic_status"], "PASS", msg=mech)

    def test_fixture_audit_reports_shared_seed_only_and_surface_split(self):
        report = audit_comfy_workflows(ui_path=UI, api_path=API)
        self.assertEqual(report["noise_field_kind"], FIELD_KIND_SHARED_SEED_ONLY)
        self.assertEqual(report["noise_evidence_grade"], EVIDENCE_GRADE_STATIC)
        self.assertFalse(report["noise_synthetic_ok"])
        self.assertFalse(report["noise_live_verified"])
        self.assertEqual(report["noise_synthetic_status"], "FAIL")
        self.assertEqual(report["noise_live_status"], "UNVERIFIED")
        self.assertIsNotNone(report["noise_field_reason"])
        noise = next(c for c in report["checks"] if c["code"] == FAILURE_NOISE)
        self.assertEqual(noise["status"], "FAIL")
        self.assertEqual(noise["evidence"]["field_kind"], FIELD_KIND_SHARED_SEED_ONLY)
        self.assertEqual(noise["evidence"]["test_id"], TEST_ID_NOISE)
        self.assertFalse(noise["evidence"]["noise_synthetic_ok"])
        self.assertFalse(noise["evidence"]["noise_live_verified"])
        # Mechanism catalog: Synthetic PASS while workflow Live remains false
        catalog = report["noise_mechanism_contracts"]
        self.assertTrue(catalog["noise_synthetic_ok"])
        self.assertFalse(catalog["noise_live_verified"])
        self.assertEqual(catalog["synthetic_status"], "PASS")
        self.assertEqual(catalog["live_status"], "UNVERIFIED")
        for mid in MECHANISMS:
            self.assertEqual(catalog["mechanisms"][mid]["synthetic_status"], "PASS")
            self.assertFalse(catalog["mechanisms"][mid]["noise_live_verified"])
        self.assertFalse(report["execution_allowed"])
        self.assertEqual(report["maturity_remains"], "workflow_candidate")
        self.assertEqual(report["overall_status"], "BLOCKED_WORKFLOW_CANDIDATE")
        non_claims = " ".join(report["non_claims"])
        self.assertIn("noise_synthetic_ok", non_claims)
        self.assertIn("noise_live_verified", non_claims)


if __name__ == "__main__":
    unittest.main()
