"""Disk-capture receipt tests — tiny temp files only (CI never reads PC weights)."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ige.cli import build_parser, main
from ige.comfy.model_inventory import (
    EVIDENCE_GRADE_DECLARED,
    EVIDENCE_GRADE_DISK,
    backend_model_inventory_verified,
    load_model_inventory,
    validate_declared_inventory,
)
from ige.comfy.model_inventory_capture import (
    CAPTURE_SCHEMA,
    CAPTURE_TOOL,
    CaptureInventoryError,
    RECEIPT_KIND,
    capture_model_inventory,
    load_capture_receipt,
    rehash_capture_receipt,
    sha256_file_chunked,
    siax_matches_registry_pin,
    validate_capture_receipt,
    write_capture_receipt,
)
from ige.comfy.workflow_static_audit import audit_comfy_workflows
from ige.method_registry import MethodRegistry

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "comfy"
DECLARED = FIXTURES / "backend_model_inventory_pc_dev_fp8_v0.1.json"
UI = FIXTURES / "workflow_ige_v03_dev_fp8.json"
API = FIXTURES / "workflow_cloud_api_prompt_v0.5.json"


def _write_weight(root: Path, relative: str, payload: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


class ModelInventoryCaptureTests(unittest.TestCase):
    def test_sha256_file_chunked_matches_hashlib(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob.bin"
            data = b"ige-capture-test-" + (b"x" * 100_000)
            path.write_bytes(data)
            size, digest = sha256_file_chunked(path, chunk_size=4096)
            self.assertEqual(size, len(data))
            self.assertEqual(digest, hashlib.sha256(data).hexdigest())

    def test_capture_writes_correct_sha_and_size(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "models"
            blobs = {
                "upscale_models/4x_NMKD-Siax_200k.pth": b"siax-tiny",
                "vae/ae.safetensors": b"ae-tiny",
                "clip/clip_l.safetensors": b"clip-l-tiny",
                "clip/t5xxl_fp16.safetensors": b"t5-tiny",
                "diffusion_models/flux1-dev.safetensors": b"flux-tiny",
            }
            for rel, data in blobs.items():
                _write_weight(root, rel, data)

            receipt = capture_model_inventory(root)
            self.assertEqual(receipt["schema"], CAPTURE_SCHEMA)
            self.assertEqual(receipt["receipt_kind"], RECEIPT_KIND)
            self.assertEqual(receipt["evidence_grade"], EVIDENCE_GRADE_DISK)
            self.assertEqual(receipt["capture_tool"], CAPTURE_TOOL)
            self.assertEqual(receipt["algorithm"], "sha256")
            self.assertEqual(len(receipt["assets"]), 5)
            self.assertFalse(receipt.get("execution_allowed", False))

            by_rel = {a["relative_path"]: a for a in receipt["assets"]}
            for rel, data in blobs.items():
                asset = by_rel[rel]
                self.assertEqual(asset["size_bytes"], len(data))
                self.assertEqual(asset["sha256"], hashlib.sha256(data).hexdigest())
                self.assertTrue(asset["hashed_at"])

            out = Path(tmp) / "receipt.json"
            write_capture_receipt(receipt, out)
            loaded = load_capture_receipt(out)
            self.assertEqual(loaded["assets"][0]["sha256"], receipt["assets"][0]["sha256"])

    def test_capture_fail_closed_on_missing_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "models"
            root.mkdir()
            with self.assertRaises(CaptureInventoryError) as ctx:
                capture_model_inventory(root)
            self.assertIn("missing", str(ctx.exception).lower())

    def test_capture_fail_closed_on_expected_size_mismatch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "models"
            _write_weight(root, "vae/ae.safetensors", b"ae-tiny")
            manifest = {
                "assets": [
                    {
                        "asset_id": "FLUX_AE",
                        "role": "vae",
                        "relative_path": "vae/ae.safetensors",
                        "expected_size_bytes": 999,
                    }
                ]
            }
            with self.assertRaises(CaptureInventoryError) as ctx:
                capture_model_inventory(root, manifest=manifest)
            self.assertIn("size mismatch", str(ctx.exception).lower())

    def test_tampered_receipt_fails_validation_and_rehash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "models"
            _write_weight(root, "vae/ae.safetensors", b"ae-tiny")
            receipt = capture_model_inventory(
                root,
                expect_relative=["vae/ae.safetensors"],
            )
            bad = copy.deepcopy(receipt)
            bad["assets"][0]["sha256"] = "0" * 64
            # schema/provenance still structurally valid
            self.assertFalse(validate_capture_receipt(bad))
            # but live rehash against disk fails
            result = rehash_capture_receipt(bad, models_root=root)
            self.assertFalse(result["matched"])
            self.assertTrue(result["mismatches"])

            # missing capture_tool fails provenance
            bad2 = copy.deepcopy(receipt)
            bad2["capture_tool"] = "not-the-tool"
            self.assertTrue(validate_capture_receipt(bad2))

    def test_declared_inventory_alone_not_live_verified(self):
        inventory = load_model_inventory(DECLARED)
        declared = validate_declared_inventory(inventory)
        self.assertEqual(declared["status"], "DECLARED_RECORD_VALID")
        self.assertEqual(declared["evidence_grade"], EVIDENCE_GRADE_DECLARED)
        self.assertTrue(declared["inventory_declared_ok"])
        self.assertFalse(declared["inventory_live_verified"])
        self.assertFalse(declared["execution_allowed"])

        verified = backend_model_inventory_verified(
            inventory,
            static_audit_report=audit_comfy_workflows(ui_path=UI, api_path=API),
        )
        self.assertTrue(verified["inventory_declared_ok"])
        self.assertFalse(verified["inventory_capture_present"])
        self.assertFalse(verified["inventory_live_verified"])
        self.assertFalse(verified["verified"])  # live alias
        self.assertEqual(verified["evidence_grade"], EVIDENCE_GRADE_DECLARED)
        self.assertFalse(verified["execution_allowed"])

    def test_capture_receipt_siax_matches_registry_pin(self):
        registry = MethodRegistry.load()
        pinned = registry.resolve("SIAX4X_TILE_CORE_SR")["model_sha256"]
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "models"
            # Craft bytes whose sha equals the registry pin? Impossible without
            # brute force. Instead plant the pin string into a receipt-shaped
            # object after capture of tiny bytes, then compare helper path;
            # for true pin match, mutate asset sha to pin (string compare).
            _write_weight(root, "upscale_models/4x_NMKD-Siax_200k.pth", b"siax-tiny")
            receipt = capture_model_inventory(
                root,
                expect_relative=["upscale_models/4x_NMKD-Siax_200k.pth"],
            )
            # Without pin match → FAIL
            miss = siax_matches_registry_pin(receipt, registry=registry)
            self.assertFalse(miss["matched"])
            # Plant registry pin (string compare path used by helper)
            receipt["assets"][0]["sha256"] = pinned
            hit = siax_matches_registry_pin(receipt, registry=registry)
            self.assertTrue(hit["matched"])
            self.assertEqual(hit["status"], "PASS")

    def test_audit_with_declared_keeps_flux_blocked_and_not_live(self):
        report = audit_comfy_workflows(
            ui_path=UI,
            api_path=API,
            model_inventory_path=DECLARED,
        )
        self.assertFalse(report["execution_allowed"])
        self.assertEqual(report["maturity_remains"], "workflow_candidate")
        backend = report["backend_model_inventory"]
        self.assertEqual(backend["evidence_grade"], EVIDENCE_GRADE_DECLARED)
        self.assertFalse(backend["inventory_live_verified"])
        self.assertTrue(backend["inventory_declared_ok"])

    def test_audit_with_capture_receipt_sets_disk_grade(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "models"
            # Filenames must match workflow declarations
            blobs = {
                "upscale_models/4x_NMKD-Siax_200k.pth": b"siax-tiny",
                "vae/ae.safetensors": b"ae-tiny",
                "clip/clip_l.safetensors": b"clip-l-tiny",
                "clip/t5xxl_fp16.safetensors": b"t5-tiny",
                "diffusion_models/flux1-dev.safetensors": b"flux-tiny",
            }
            for rel, data in blobs.items():
                _write_weight(root, rel, data)
            receipt = capture_model_inventory(root)
            # Align Siax sha to registry pin for workflow check PASS
            pinned = MethodRegistry.load().resolve("SIAX4X_TILE_CORE_SR")["model_sha256"]
            for asset in receipt["assets"]:
                if asset["asset_id"] == "SIAX4X":
                    asset["sha256"] = pinned
            out = Path(tmp) / "receipt.json"
            write_capture_receipt(receipt, out)

            report = audit_comfy_workflows(
                ui_path=UI,
                api_path=API,
                capture_receipt_path=out,
            )
            self.assertFalse(report["execution_allowed"])
            self.assertEqual(report["maturity_remains"], "workflow_candidate")
            backend = report["backend_model_inventory"]
            self.assertEqual(backend["evidence_grade"], EVIDENCE_GRADE_DISK)
            self.assertTrue(backend["inventory_capture_present"])
            self.assertTrue(backend["inventory_live_verified"])
            method = MethodRegistry.load().resolve("FLUX_HR_TILE_IMG2IMG")
            self.assertEqual(method["maturity"], "workflow_candidate")
            self.assertIs(method["edit_permission"], False)

    def test_cli_capture_model_inventory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "models"
            _write_weight(root, "vae/ae.safetensors", b"ae-cli")
            out = Path(tmp) / "receipt.json"
            old = sys.argv
            sys.argv = [
                "ige",
                "capture-model-inventory",
                "--models-root",
                str(root),
                "--out",
                str(out),
                "--expect-relative",
                "vae/ae.safetensors",
            ]
            try:
                code = main()
            finally:
                sys.argv = old
            self.assertEqual(code, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["evidence_grade"], EVIDENCE_GRADE_DISK)
            self.assertEqual(payload["assets"][0]["sha256"], hashlib.sha256(b"ae-cli").hexdigest())

    def test_cli_parser_registers_capture(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "capture-model-inventory",
                "--models-root",
                "/tmp/models",
                "--out",
                "/tmp/out.json",
            ]
        )
        self.assertEqual(args.command, "capture-model-inventory")
        args2 = parser.parse_args(
            [
                "audit-comfy-workflow",
                "--ui",
                str(UI),
                "--capture-receipt",
                "/tmp/receipt.json",
            ]
        )
        self.assertEqual(args2.capture_receipt, Path("/tmp/receipt.json"))


if __name__ == "__main__":
    unittest.main()
