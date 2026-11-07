from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from ige.comfy.tile_core_halo_ledger import (
    CODE_CORE_NOT_SUBSET,
    CODE_CORE_OVERLAP,
    CODE_COVERAGE_GAP,
    CODE_HALO_WRITE,
    CODE_LEDGER_REQUIRED,
    CODE_OUTPUT_SHA,
    CODE_S2_BIND,
    CODE_SCHEMA,
    LEDGER_SCHEMA,
    UMBRELLA_FAILURE,
    audit_ledger,
    exact_once_region_coverage,
    ledger_passes,
    load_ledger,
    method_requires_tile_core_halo_ledger,
    missing_ledger_failure,
    parse_bounds,
    resolve_optional_ledger_from_s6,
    synthetic_core_not_subset_read_ledger,
    synthetic_core_overlap_ledger,
    synthetic_coverage_gap_ledger,
    synthetic_halo_write_ledger,
    synthetic_large_canvas_grid_ledger,
    synthetic_missing_output_sha_ledger,
    synthetic_valid_two_tile_ledger,
    union_area,
    validate_ledger_payload,
)
from ige.comfy.workflow_static_audit import audit_comfy_workflows
from ige.method_registry import MethodRegistry

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "tile_core_halo_ledger.schema.json"
FIXTURES = ROOT / "fixtures" / "comfy"
UI = FIXTURES / "workflow_ige_v03_dev_fp8.json"
API = FIXTURES / "workflow_cloud_api_prompt_v0.5.json"


def _status(report: dict, code: str) -> str:
    return next(c["status"] for c in report["checks"] if c["code"] == code)


class TileCoreHaloLedgerTests(unittest.TestCase):
    def test_schema_file_exists(self):
        self.assertTrue(SCHEMA.is_file())
        payload = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(payload["properties"]["schema"]["const"], LEDGER_SCHEMA)
        self.assertIn("canvas_sha256", payload["required"])
        self.assertIn("output_sha256", payload["properties"]["tiles"]["items"]["required"])

    def test_valid_two_tile_passes(self):
        ledger = synthetic_valid_two_tile_ledger()
        self.assertEqual(validate_ledger_payload(ledger), [])
        report = audit_ledger(ledger)
        self.assertTrue(ledger_passes(report))
        self.assertEqual(report["overall_status"], "PASS")
        self.assertEqual(report["umbrella_failure_code"], UMBRELLA_FAILURE)
        self.assertEqual(report["coverage_engine"], "scanline_interval_union")
        for code in (
            CODE_SCHEMA,
            CODE_OUTPUT_SHA,
            CODE_CORE_NOT_SUBSET,
            CODE_HALO_WRITE,
            CODE_CORE_OVERLAP,
            CODE_COVERAGE_GAP,
        ):
            self.assertEqual(_status(report, code), "PASS", code)
        self.assertFalse(report["execution_allowed"])
        self.assertFalse(report["edit_permission"])
        self.assertTrue(report["maturity_unchanged"])

    def test_s2_bind_pass_and_mismatch(self):
        ledger = synthetic_valid_two_tile_ledger(
            coordinate_frame="native_4x_master",
            canvas_sha256="1" * 64,
        )
        ok = audit_ledger(
            ledger,
            s2_geometry={"coordinate_frame": "native_4x_master", "canvas_sha256": "1" * 64},
            require_s2_bind=True,
        )
        self.assertTrue(ledger_passes(ok))
        self.assertEqual(_status(ok, CODE_S2_BIND), "PASS")

        bad_sha = audit_ledger(
            ledger,
            s2_geometry={"coordinate_frame": "native_4x_master", "canvas_sha256": "2" * 64},
            require_s2_bind=True,
        )
        self.assertFalse(ledger_passes(bad_sha))
        self.assertEqual(_status(bad_sha, CODE_S2_BIND), "FAIL")
        self.assertIn(CODE_S2_BIND, bad_sha["blockers"])

        bad_frame = audit_ledger(
            ledger,
            s2_geometry={"coordinate_frame": "other_frame", "canvas_sha256": "1" * 64},
            require_s2_bind=True,
        )
        self.assertFalse(ledger_passes(bad_frame))
        self.assertEqual(_status(bad_frame, CODE_S2_BIND), "FAIL")

        missing_s2 = audit_ledger(ledger, require_s2_bind=True)
        self.assertFalse(ledger_passes(missing_s2))
        self.assertEqual(_status(missing_s2, CODE_S2_BIND), "FAIL")

    def test_missing_output_sha_fails(self):
        report = audit_ledger(synthetic_missing_output_sha_ledger())
        self.assertFalse(ledger_passes(report))
        self.assertEqual(_status(report, CODE_SCHEMA), "FAIL")
        self.assertEqual(_status(report, CODE_OUTPUT_SHA), "FAIL")
        self.assertIn(CODE_OUTPUT_SHA, report["blockers"])

    def test_core_overlap_fails(self):
        report = audit_ledger(synthetic_core_overlap_ledger())
        self.assertFalse(ledger_passes(report))
        self.assertEqual(_status(report, CODE_CORE_OVERLAP), "FAIL")
        self.assertIn(CODE_CORE_OVERLAP, report["blockers"])
        self.assertFalse(report["execution_allowed"])

    def test_coverage_gap_fails(self):
        report = audit_ledger(synthetic_coverage_gap_ledger())
        self.assertFalse(ledger_passes(report))
        self.assertEqual(_status(report, CODE_COVERAGE_GAP), "FAIL")
        self.assertGreater(
            report["stats"]["target_area"] - report["stats"]["core_area_sum"], 0
        )
        self.assertFalse(report["execution_allowed"])

    def test_halo_write_fails(self):
        report = audit_ledger(synthetic_halo_write_ledger())
        self.assertFalse(ledger_passes(report))
        self.assertEqual(_status(report, CODE_HALO_WRITE), "FAIL")
        self.assertIn(CODE_HALO_WRITE, report["blockers"])
        self.assertEqual(_status(report, CODE_CORE_OVERLAP), "PASS")
        self.assertEqual(_status(report, CODE_COVERAGE_GAP), "PASS")

    def test_core_not_subset_read_fails(self):
        report = audit_ledger(synthetic_core_not_subset_read_ledger())
        self.assertFalse(ledger_passes(report))
        self.assertEqual(_status(report, CODE_CORE_NOT_SUBSET), "FAIL")
        self.assertIn(CODE_CORE_NOT_SUBSET, report["blockers"])

    def test_schema_reject_bad_bounds(self):
        bad = synthetic_valid_two_tile_ledger()
        bad["tiles"][0]["core_bounds"] = [0, 0, 0, 4]
        errors = validate_ledger_payload(bad)
        self.assertTrue(any("x1>x0" in e for e in errors))
        report = audit_ledger(bad)
        self.assertEqual(_status(report, CODE_SCHEMA), "FAIL")

    def test_load_roundtrip(self):
        ledger = synthetic_valid_two_tile_ledger()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            loaded = load_ledger(path)
            self.assertEqual(loaded["schema"], LEDGER_SCHEMA)
            self.assertTrue(ledger_passes(audit_ledger(loaded)))

    def test_resolve_optional_from_s6_embedded_and_path(self):
        ledger = synthetic_valid_two_tile_ledger()
        embedded = resolve_optional_ledger_from_s6({"tile_core_halo_ledger": ledger})
        self.assertEqual(embedded["schema"], LEDGER_SCHEMA)
        self.assertIsNone(resolve_optional_ledger_from_s6({}))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            path.write_text(json.dumps(ledger), encoding="utf-8")
            loaded = resolve_optional_ledger_from_s6(
                {"tile_core_halo_ledger_path": str(path)}
            )
            self.assertEqual(loaded["tiles"][0]["tile_id"], "t0")

    def test_method_requires_tile_ledger_and_missing_failure(self):
        self.assertTrue(method_requires_tile_core_halo_ledger("SIAX4X_TILE_CORE_SR"))
        self.assertTrue(method_requires_tile_core_halo_ledger("FLUX_HR_TILE_IMG2IMG"))
        self.assertTrue(method_requires_tile_core_halo_ledger("GEOMETRY_LOCKED_TILE_PLAN_RETURN"))
        self.assertFalse(method_requires_tile_core_halo_ledger("DETAIL6_MATERIAL_RESIDUAL"))
        fail = missing_ledger_failure(method_id="SIAX4X_TILE_CORE_SR")
        self.assertEqual(fail["overall_status"], "FAIL")
        self.assertIn(CODE_LEDGER_REQUIRED, fail["blockers"])
        self.assertFalse(fail["execution_allowed"])

    def test_region_engine_large_8k_grid_passes_quickly(self):
        """8K canvas must audit without expanding to per-pixel sets / OOM."""
        ledger = synthetic_large_canvas_grid_ledger(
            canvas_w=8192, canvas_h=8192, tiles_x=4, tiles_y=4, halo=64
        )
        # Sanity: per-pixel expansion of 8192^2 would be catastrophic (~67M tuples).
        self.assertEqual(union_area([[0, 0, 8192, 8192]]), 8192 * 8192)
        t0 = time.perf_counter()
        report = audit_ledger(ledger)
        elapsed = time.perf_counter() - t0
        self.assertTrue(ledger_passes(report), report.get("blockers"))
        self.assertEqual(report["stats"]["target_area"], 8192 * 8192)
        self.assertEqual(report["stats"]["core_area_sum"], 8192 * 8192)
        self.assertLess(elapsed, 2.0, f"8K region audit too slow: {elapsed:.3f}s")

    def test_region_engine_gap_on_large_canvas(self):
        ledger = synthetic_large_canvas_grid_ledger(
            canvas_w=4096, canvas_h=4096, tiles_x=2, tiles_y=2
        )
        # Drop last tile core coverage → gap.
        ledger["tiles"][-1]["core_bounds"] = [3072, 3072, 3073, 3073]
        report = audit_ledger(ledger)
        self.assertFalse(ledger_passes(report))
        self.assertEqual(_status(report, CODE_COVERAGE_GAP), "FAIL")

    def test_exact_once_helper_direct(self):
        cores = [
            parse_bounds([0, 0, 4, 4], label="c0"),
            parse_bounds([4, 0, 8, 4], label="c1"),
        ]
        assert not isinstance(cores[0], str) and not isinstance(cores[1], str)
        cov = exact_once_region_coverage(cores, [[0, 0, 8, 4]])
        self.assertTrue(cov["ok"])
        gap = exact_once_region_coverage(cores, [[0, 0, 9, 4]])
        self.assertFalse(gap["ok"])

    def test_s0_s7_optional_ledger_blocks_on_halo_write(self):
        failing = synthetic_halo_write_ledger()
        report = audit_ledger(failing)
        self.assertFalse(ledger_passes(report))
        registry = MethodRegistry.load()
        flux = registry.resolve("FLUX_HR_TILE_IMG2IMG")
        self.assertEqual(flux["maturity"], "workflow_candidate")
        self.assertIs(flux["edit_permission"], False)

    def test_flux_static_workflow_still_blocked(self):
        report = audit_comfy_workflows(ui_path=UI, api_path=API)
        self.assertFalse(report["execution_allowed"])
        self.assertEqual(report["maturity_remains"], "workflow_candidate")
        self.assertEqual(report["overall_status"], "BLOCKED_WORKFLOW_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
