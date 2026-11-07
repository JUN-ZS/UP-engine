from __future__ import annotations

import hashlib
import json
import os
import tempfile
import io
from urllib.error import HTTPError
from email.message import Message
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ige.comfy.cloud_client import ComfyCloudClient, ComfyCloudConfig
from ige.comfy.workflow_runtime import (
    REQUIRED_CLASSES,
    audit_api_workflow_live,
    create_comfy_cloud_manifest,
    preflight_comfy_cloud,
    run_comfy_cloud_diagnostic,
)

ROOT = Path(__file__).parents[1]
API_WORKFLOW = ROOT / "fixtures" / "comfy" / "workflow_cloud_api_prompt_v0.5.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fake_live_object_info(workflow: dict) -> dict:
    outputs = {
        "UNETLoader": ["MODEL"],
        "VAELoader": ["VAE"],
        "DualCLIPLoader": ["CLIP"],
        "CLIPTextEncode": ["CONDITIONING"],
        "FluxGuidance": ["CONDITIONING"],
        "BasicGuider": ["GUIDER"],
        "RandomNoise": ["NOISE"],
        "KSamplerSelect": ["SAMPLER"],
        "BasicScheduler": ["SIGMAS"],
        "SamplerCustomAdvanced": ["LATENT"],
        "VAEEncode": ["LATENT"],
        "VAEDecodeTiled": ["IMAGE"],
        "LoadImage": ["IMAGE", "MASK"],
        "SaveImage": [],
    }
    return {
        node["class_type"]: {"output": outputs.get(node["class_type"], [])}
        for node in workflow.values()
    }


def fake_models() -> dict:
    return {
        "folders": [{"name": "diffusion_models"}, {"name": "vae"}, {"name": "clip"}],
        "models_by_folder": {
            "diffusion_models": [{"name": "flux1-dev.safetensors"}],
            "vae": [{"name": "ae.safetensors"}],
            "clip": [{"name": "t5xxl_fp16.safetensors"}, {"name": "clip_l.safetensors"}],
        },
    }


class FakeCloudClient:
    base_url = "https://cloud.comfy.org"

    def __init__(self, workflow):
        self.workflow = workflow

    def health(self):
        return {
            "status": "reachable",
            "node_count": len(fake_live_object_info(self.workflow)),
            "object_info": fake_live_object_info(self.workflow),
            "features": {},
        }

    def model_inventory(self):
        return fake_models()


class ComfyCloudClientTests(unittest.TestCase):
    def test_submit_prompt_uses_cloud_api_payload_and_returns_prompt_id(self):
        client = ComfyCloudClient(ComfyCloudConfig())
        with patch.object(client, "_json", return_value={"prompt_id": "job-123"}) as request:
            prompt_id = client.submit_prompt({"1": {"class_type": "SaveImage", "inputs": {}}})
        self.assertEqual(prompt_id, "job-123")
        request.assert_called_once_with(
            "POST", "/api/prompt",
            {"prompt": {"1": {"class_type": "SaveImage", "inputs": {}}}},
        )

    def test_rejects_node_errors_from_cloud_prompt_validation(self):
        client = ComfyCloudClient(ComfyCloudConfig())
        with patch.object(client, "_json", return_value={"node_errors": {"4": {"errors": ["missing"]}}}):
            with self.assertRaisesRegex(Exception, "rejected workflow"):
                client.submit_prompt({"4": {"class_type": "BadNode", "inputs": {}}})

    def test_wait_for_job_polls_until_completed(self):
        client = ComfyCloudClient(ComfyCloudConfig(), sleeper=lambda _: None, monotonic=lambda: 0.0)
        states = iter([
            {"status": "pending"},
            {"status": "in_progress"},
            {"status": "completed", "outputs": {"8": {"images": [{"filename": "tile.png", "type": "output"}]}}},
        ])
        with patch.object(client, "get_job", side_effect=lambda _: next(states)):
            job = client.wait_for_job("job-456", timeout_seconds=10, poll_interval_seconds=0.01)
        self.assertEqual(job["status"], "completed")

    def test_collect_images_handles_comfy_output_shape_and_deduplicates(self):
        job = {
            "outputs": {
                "128": {"images": [
                    {"filename": "left.png", "subfolder": "", "type": "output"},
                    {"filename": "left.png", "subfolder": "", "type": "output"},
                ]},
                "129": {"images": [
                    {"filename": "right.png", "subfolder": "", "type": "output"}
                ]},
            }
        }
        images = ComfyCloudClient.collect_images(job)
        self.assertEqual([x["filename"] for x in images], ["left.png", "right.png"])
        self.assertEqual([x["node_id"] for x in images], ["128", "129"])

    def test_upload_image_sends_multipart_bytes_without_logging_secret(self):
        client = ComfyCloudClient(ComfyCloudConfig())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tile.png"
            Image.new("RGB", (2, 2), (1, 2, 3)).save(path)
            with patch.dict(os.environ, {"COMFY_CLOUD_API_KEY": "test-secret"}):
                captured = {}
                def fake_request(method, endpoint, **kwargs):
                    captured.update({"method": method, "endpoint": endpoint, **kwargs})
                    return 200, {}, b'{"name":"upload-hash.png","type":"input"}'
                with patch.object(client, "_request", side_effect=fake_request):
                    result = client.upload_image(path)
        self.assertEqual(result["name"], "upload-hash.png")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["endpoint"], "/api/upload/image")
        self.assertIn(b'filename="tile.png"', captured["body"])
        self.assertIn(b'name="type"', captured["body"])
        self.assertNotIn(b"test-secret", captured["body"])

    def test_download_output_validates_image_and_does_not_forward_api_key_to_signed_url(self):
        client = ComfyCloudClient(ComfyCloudConfig())
        with tempfile.TemporaryDirectory() as directory:
            generated = io.BytesIO()
            Image.new("RGB", (7, 5), (3, 4, 5)).save(generated, format="PNG")
            png_bytes = generated.getvalue()
            headers = Message()
            headers["Location"] = "https://signed-storage.example/object?signature=abc"
            captured = {}

            class NoRedirectOpener:
                def open(self, request, timeout):
                    captured["view_api_key"] = request.get_header("X-api-key")
                    raise HTTPError(
                        request.full_url, 302, "Found", headers, io.BytesIO(b"")
                    )

            class SignedResponse:
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc, tb):
                    return False
                def read(self):
                    return png_bytes

            def signed_fetch(request, timeout):
                captured["signed_url"] = request.full_url
                captured["signed_api_key"] = request.get_header("X-api-key")
                return SignedResponse()

            with patch.dict(os.environ, {"COMFY_CLOUD_API_KEY": "test-secret"}):
                with patch("ige.comfy.cloud_client.build_opener", return_value=NoRedirectOpener()):
                    with patch("ige.comfy.cloud_client.urlopen", side_effect=signed_fetch):
                        result = client.download_output(
                            {"filename": "tile.png", "type": "output"},
                            Path(directory) / "downloaded.png",
                        )
            self.assertEqual(captured["view_api_key"], "test-secret")
            self.assertEqual(captured["signed_api_key"], None)
            self.assertIn("signed-storage.example", captured["signed_url"])
            self.assertEqual(result["image_format"], "PNG")
            self.assertEqual((result["width"], result["height"]), (7, 5))
            self.assertEqual(Path(result["path"]).read_bytes(), png_bytes)

    def test_download_output_rejects_non_image_response(self):
        client = ComfyCloudClient(ComfyCloudConfig())
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"COMFY_CLOUD_API_KEY": "test-secret"}):
                with patch("ige.comfy.cloud_client.build_opener") as opener:
                    class NoRedirectOpener:
                        def open(self, request, timeout):
                            return FakeNonImageResponse()
                    class FakeNonImageResponse:
                        status = 200
                        headers = {}
                        def __enter__(self): return self
                        def __exit__(self, *args): return False
                        def read(self): return b"not-an-image"
                    opener.return_value = NoRedirectOpener()
                    with self.assertRaisesRegex(Exception, "not a decodable image"):
                        client.download_output(
                            {"filename": "bad.png", "type": "output"},
                            Path(directory) / "bad.png",
                        )


class ComfyWorkflowRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.workflow = json.loads(API_WORKFLOW.read_text(encoding="utf-8"))

    def test_live_graph_routes_pass_but_noise_and_s6_stay_blocked(self):
        report = audit_api_workflow_live(
            self.workflow,
            object_info=fake_live_object_info(self.workflow),
            model_inventory=fake_models(),
        )
        statuses = {item["code"]: item["status"] for item in report["checks"]}
        self.assertEqual(statuses["E_COMFY_LIVE_NODE_MISSING"], "PASS")
        self.assertEqual(statuses["E_COMFY_API_GRAPH_INVALID"], "PASS")
        self.assertEqual(statuses["E_TILE_CONDITIONING_UNROUTED"], "PASS")
        self.assertEqual(statuses["E_NOISE_FIELD_NOT_GLOBAL"], "FAIL")
        self.assertEqual(statuses["E_TILE_COMPOSITOR_MISSING"], "FAIL")
        self.assertEqual(statuses["E_CLOUD_MODEL_SHA_UNVERIFIED"], "UNKNOWN")
        self.assertEqual(report["overall_status"], "BLOCKED_WORKFLOW_CANDIDATE")
        self.assertFalse(report["execution_allowed"])
        self.assertEqual(report["maturity_remains"], "workflow_candidate")

    def test_missing_live_custom_node_blocks_runtime_preflight(self):
        object_info = fake_live_object_info(self.workflow)
        object_info.pop("VAEDecodeTiled")
        report = audit_api_workflow_live(
            self.workflow,
            object_info=object_info,
            model_inventory=fake_models(),
        )
        check = next(x for x in report["checks"] if x["code"] == "E_COMFY_LIVE_NODE_MISSING")
        self.assertEqual(check["status"], "FAIL")
        self.assertIn("VAEDecodeTiled", check["missing_workflow_classes"])

    def test_missing_model_filename_blocks(self):
        inventory = fake_models()
        inventory["models_by_folder"]["clip"] = [{"name": "clip_l.safetensors"}]
        report = audit_api_workflow_live(
            self.workflow,
            object_info=fake_live_object_info(self.workflow),
            model_inventory=inventory,
        )
        check = next(x for x in report["checks"] if x["code"] == "E_COMFY_MODEL_CONTRACT_MISMATCH")
        self.assertEqual(check["status"], "FAIL")
        self.assertTrue(any(item["input"] == "clip_name1" for item in check["models"] if not item["available"]))

    def test_wrong_but_available_unet_does_not_satisfy_dev_fp8_contract(self):
        workflow = json.loads(json.dumps(self.workflow))
        workflow["77"]["inputs"]["unet_name"] = "another-flux-model.safetensors"
        inventory = fake_models()
        inventory["models_by_folder"]["diffusion_models"].append(
            {"name": "another-flux-model.safetensors"}
        )
        report = audit_api_workflow_live(
            workflow,
            object_info=fake_live_object_info(workflow),
            model_inventory=inventory,
        )
        check = next(x for x in report["checks"] if x["code"] == "E_COMFY_MODEL_CONTRACT_MISMATCH")
        self.assertEqual(check["status"], "FAIL")
        unet = next(x for x in check["models"] if x["input"] == "unet_name")
        self.assertTrue(unet["available"])
        self.assertFalse(unet["matches_contract"])

    def test_broken_conditioning_edge_is_detected(self):
        broken = json.loads(json.dumps(self.workflow))
        broken["5007"]["inputs"]["conditioning"] = ["does-not-exist", 0]
        report = audit_api_workflow_live(
            broken,
            object_info=fake_live_object_info(broken),
            model_inventory=fake_models(),
        )
        graph_check = next(x for x in report["checks"] if x["code"] == "E_COMFY_API_GRAPH_INVALID")
        self.assertEqual(graph_check["status"], "FAIL")
        cond_check = next(x for x in report["checks"] if x["code"] == "E_TILE_CONDITIONING_UNROUTED")
        self.assertEqual(cond_check["status"], "FAIL")

    def test_out_of_range_node_output_slot_is_detected(self):
        broken = json.loads(json.dumps(self.workflow))
        broken["67"]["inputs"]["noise"] = ["70", 1]
        report = audit_api_workflow_live(
            broken,
            object_info=fake_live_object_info(broken),
            model_inventory=fake_models(),
        )
        graph_check = next(x for x in report["checks"] if x["code"] == "E_COMFY_API_GRAPH_INVALID")
        self.assertEqual(graph_check["status"], "FAIL")
        self.assertTrue(any(x["error"] == "output_slot_out_of_range" for x in graph_check["errors"]))

    def test_manifest_generator_computes_hashes_and_binds_load_image_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow_copy = root / "workflow.json"
            workflow_copy.write_text(API_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
            left = root / "left.png"
            right = root / "right.png"
            Image.new("RGB", (8, 8), (1, 2, 3)).save(left)
            Image.new("RGB", (8, 8), (4, 5, 6)).save(right)
            manifest_path = root / "runs" / "cloud_manifest.json"
            result = create_comfy_cloud_manifest(
                workflow_path=workflow_copy,
                tile_bindings=[("233", left), ("5000", right)],
                manifest_path=manifest_path,
                output_dir=root / "runs" / "outputs",
                run_id="generated-manifest-test",
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(result["manifest_sha256"], sha(manifest_path))
            self.assertTrue(manifest["diagnostic_only"])
            self.assertEqual(manifest["run_id"], "generated-manifest-test")
            self.assertEqual([x["node_id"] for x in manifest["tile_inputs"]], ["233", "5000"])
            self.assertEqual(manifest["tile_inputs"][0]["sha256"], sha(left))
            self.assertEqual(manifest["tile_inputs"][1]["sha256"], sha(right))
            self.assertFalse(result["execution_allowed"])

    def test_manifest_generator_rejects_non_load_image_node(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow_copy = root / "workflow.json"
            workflow_copy.write_text(API_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
            tile = root / "tile.png"
            Image.new("RGB", (4, 4)).save(tile)
            with self.assertRaisesRegex(Exception, "not a LoadImage"):
                create_comfy_cloud_manifest(
                    workflow_path=workflow_copy,
                    tile_bindings=[("42", tile)],
                    manifest_path=root / "manifest.json",
                    output_dir=root / "out",
                )

    def test_manifest_preflight_validates_local_tile_hashes_before_api(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow_copy = root / "workflow.json"
            workflow_copy.write_text(API_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
            left = root / "tile_left.png"
            right = root / "tile_right.png"
            Image.new("RGB", (12, 12), (11, 22, 33)).save(left)
            Image.new("RGB", (12, 12), (44, 55, 66)).save(right)
            manifest = {
                "schema": "ige-comfy-cloud-run-manifest/0.1",
                "run_id": "test-run",
                "workflow_path": "workflow.json",
                "tile_inputs": [
                    {"node_id": "233", "path": "tile_left.png", "sha256": sha(left)},
                    {"node_id": "5000", "path": "tile_right.png", "sha256": sha(right)},
                ],
                "output_dir": "out",
                "diagnostic_only": True,
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            fake = FakeCloudClient(self.workflow)
            report = preflight_comfy_cloud(manifest_path, client=fake)
        self.assertEqual(len(report["input_facts"]), 2)
        self.assertEqual(report["runtime_audit"]["overall_status"], "BLOCKED_WORKFLOW_CANDIDATE")
        self.assertFalse(report["execution_allowed"])

    def test_manifest_input_sha_mismatch_fails_before_remote_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow_copy = root / "workflow.json"
            workflow_copy.write_text(API_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
            tile = root / "tile.png"
            Image.new("RGB", (4, 4)).save(tile)
            manifest = {
                "schema": "ige-comfy-cloud-run-manifest/0.1",
                "run_id": "test-run",
                "workflow_path": "workflow.json",
                "tile_inputs": [{"node_id": "233", "path": "tile.png", "sha256": "0" * 64}],
                "output_dir": "out",
                "diagnostic_only": True,
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            fake = FakeCloudClient(self.workflow)
            with self.assertRaisesRegex(Exception, "SHA mismatch"):
                preflight_comfy_cloud(manifest_path, client=fake)

    def test_diagnostic_submit_requires_two_explicit_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow_copy = root / "workflow.json"
            workflow_copy.write_text(API_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
            tile = root / "tile.png"
            Image.new("RGB", (4, 4)).save(tile)
            manifest = {
                "schema": "ige-comfy-cloud-run-manifest/0.1",
                "run_id": "test-run",
                "workflow_path": "workflow.json",
                "tile_inputs": [{"node_id": "233", "path": "tile.png", "sha256": sha(tile)}],
                "output_dir": "out",
                "diagnostic_only": False,
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "diagnostic_only=true"):
                run_comfy_cloud_diagnostic(manifest_path, diagnostic_submit=True, client=FakeCloudClient(self.workflow))
            manifest["diagnostic_only"] = True
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "--diagnostic-submit"):
                run_comfy_cloud_diagnostic(manifest_path, diagnostic_submit=False, client=FakeCloudClient(self.workflow))

    def test_diagnostic_cloud_job_saves_real_output_bytes_but_never_accepts_candidate(self):
        class DiagnosticClient(FakeCloudClient):
            @staticmethod
            def collect_images(job):
                return ComfyCloudClient.collect_images(job)

            def __init__(self, workflow):
                super().__init__(workflow)
                self.uploaded = []
                self.submitted = None

            def upload_image(self, path):
                result = {"name": f"uploaded-{len(self.uploaded)}.png", "type": "input"}
                self.uploaded.append((Path(path), result))
                return result

            def submit_prompt(self, workflow):
                self.submitted = json.loads(json.dumps(workflow))
                return "diagnostic-job-001"

            def wait_for_job(self, prompt_id, **kwargs):
                return {
                    "status": "completed",
                    "outputs": {
                        "128": {"images": [{"filename": "left.png", "type": "output"}]},
                        "5004": {"images": [{"filename": "right.png", "type": "output"}]},
                    },
                }

            def download_output(self, record, destination):
                path = Path(destination)
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (4, 4), (12, 34, 56)).save(path)
                return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha(path), "source_file": record["filename"]}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow_copy = root / "workflow.json"
            workflow_copy.write_text(API_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
            left = root / "tile_left.png"
            right = root / "tile_right.png"
            Image.new("RGB", (4, 4), (10, 20, 30)).save(left)
            Image.new("RGB", (4, 4), (40, 50, 60)).save(right)
            manifest = {
                "schema": "ige-comfy-cloud-run-manifest/0.1",
                "run_id": "test-run",
                "workflow_path": "workflow.json",
                "tile_inputs": [
                    {"node_id": "233", "path": "tile_left.png", "sha256": sha(left)},
                    {"node_id": "5000", "path": "tile_right.png", "sha256": sha(right)},
                ],
                "output_dir": "out",
                "diagnostic_only": True,
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            client = DiagnosticClient(self.workflow)
            receipt = run_comfy_cloud_diagnostic(
                manifest_path, diagnostic_submit=True, client=client,
                timeout_seconds=10, poll_interval_seconds=0.01,
            )
        self.assertEqual(receipt["prompt_id"], "diagnostic-job-001")
        self.assertEqual(receipt["job_status"], "completed")
        self.assertEqual(len(receipt["input_receipts"]), 2)
        self.assertEqual(len(receipt["output_receipts"]), 2)
        self.assertEqual(client.submitted["233"]["inputs"]["image"], "uploaded-0.png")
        self.assertEqual(client.submitted["5000"]["inputs"]["image"], "uploaded-1.png")
        self.assertTrue(receipt["output_tile_mapping_complete"])
        output_bindings = {x["tile_binding"]["tile_id"]: x["output_node_id"] for x in receipt["output_receipts"]}
        self.assertEqual(output_bindings, {"tile_left": "128", "tile_right": "5004"})
        self.assertTrue(receipt["diagnostic_only"])
        self.assertFalse(receipt["candidate_accepted"])
        self.assertFalse(receipt["execution_allowed"])
        self.assertFalse(receipt["edit_permission"])
        self.assertEqual(receipt["maturity_remains"], "workflow_candidate")


if __name__ == "__main__":
    unittest.main()
