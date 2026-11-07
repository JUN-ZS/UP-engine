from __future__ import annotations

import unittest
from pathlib import Path

from ige.comfy.global_noise_contract import (
    FAILURE_NOISE,
    FIELD_KIND_COORDINATE_INDEXED,
    FIELD_KIND_INDEPENDENT_SEED_PER_TILE,
    FIELD_KIND_SHARED_SEED_ONLY,
    FIELD_KIND_UNKNOWN,
    RECEIPT_SCHEMA,
    TEST_ID_NOISE,
    build_unverified_shared_seed_receipt,
    classify_noise_evidence,
    fill_tile_coordinate_indexed,
    fill_tile_independent_rng,
    overlap_region,
    probe_overlap_equality,
    synthetic_coordinate_indexed_overlap_proof,
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

    def test_coordinate_indexed_overlap_equality(self):
        proof = synthetic_coordinate_indexed_overlap_proof(seed=FIXTURE_SEED)
        self.assertEqual(proof["field_kind"], FIELD_KIND_COORDINATE_INDEXED)
        self.assertTrue(proof["verified_synthetic"])
        self.assertTrue(proof["overlap_probe"]["all_equal"])
        self.assertGreater(proof["overlap_probe"]["overlap_count"], 0)
        self.assertEqual(
            proof["overlap_probe"]["equal_count"],
            proof["overlap_probe"]["overlap_count"],
        )

    def test_shared_seed_independent_draws_mismatch(self):
        counter = synthetic_shared_seed_independent_draws_counterexample(seed=FIXTURE_SEED)
        self.assertEqual(counter["field_kind"], FIELD_KIND_SHARED_SEED_ONLY)
        self.assertTrue(counter["demonstrates_not_global"])
        self.assertGreater(counter["overlap_probe"]["mismatch_count"], 0)
        self.assertFalse(counter["overlap_probe"]["all_equal"])

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

    def test_classify_shared_seed_only_from_static_bits(self):
        result = classify_noise_evidence(
            workflow_static_bits={
                "models": {"noise_seed": FIXTURE_SEED},
                "noise_nodes": [{"id": "25", "noise_seed": FIXTURE_SEED}],
            }
        )
        self.assertEqual(result["field_kind"], FIELD_KIND_SHARED_SEED_ONLY)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["check"]["code"], FAILURE_NOISE)
        self.assertEqual(result["evidence"]["test_id"], TEST_ID_NOISE)
        self.assertIn("same seed", result["detail"].lower())

    def test_classify_no_seed_unknown(self):
        result = classify_noise_evidence(workflow_static_bits={"inventories": []})
        self.assertEqual(result["field_kind"], FIELD_KIND_UNKNOWN)
        self.assertEqual(result["status"], "FAIL")

    def test_classify_independent_seed_per_tile(self):
        result = classify_noise_evidence(
            workflow_static_bits={
                "field_kind": FIELD_KIND_INDEPENDENT_SEED_PER_TILE,
                "observed_seeds": [1, 2],
            }
        )
        self.assertEqual(result["field_kind"], FIELD_KIND_INDEPENDENT_SEED_PER_TILE)
        self.assertEqual(result["status"], "FAIL")

    def test_verified_coordinate_receipt_passes(self):
        proof = synthetic_coordinate_indexed_overlap_proof(seed=FIXTURE_SEED)
        receipt = {
            "schema": RECEIPT_SCHEMA,
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
        self.assertEqual(validate_receipt_payload(receipt), [])
        result = classify_noise_evidence(receipt=receipt)
        self.assertEqual(result["field_kind"], FIELD_KIND_COORDINATE_INDEXED)
        self.assertEqual(result["status"], "PASS")

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
        self.assertEqual(receipt["field_kind"], FIELD_KIND_SHARED_SEED_ONLY)

    def test_fixture_audit_reports_shared_seed_only(self):
        report = audit_comfy_workflows(ui_path=UI, api_path=API)
        self.assertEqual(report["noise_field_kind"], FIELD_KIND_SHARED_SEED_ONLY)
        self.assertIsNotNone(report["noise_field_reason"])
        noise = next(c for c in report["checks"] if c["code"] == FAILURE_NOISE)
        self.assertEqual(noise["status"], "FAIL")
        self.assertEqual(noise["evidence"]["field_kind"], FIELD_KIND_SHARED_SEED_ONLY)
        self.assertEqual(noise["evidence"]["test_id"], TEST_ID_NOISE)
        self.assertFalse(report["execution_allowed"])
        self.assertEqual(report["maturity_remains"], "workflow_candidate")
        self.assertEqual(report["overall_status"], "BLOCKED_WORKFLOW_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
