import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from ige.read.providers.xai_grok import GrokSpatialReasoner, GrokVisionError
from ige.read.reasoning import ReasoningOutputError


def _valid_json_text():
    return json.dumps({
        "nodes": [
            {
                "id": "left-face",
                "label": "left hammer end face",
                "semantic_type": "cylindrical_end_face",
                "bbox_xyxy_norm": [0.1, 0.2, 0.4, 0.8],
                "visual_evidence": "Circular flat end cap visible on the left hammer head.",
                "uncertainty": "medium"
            },
            {
                "id": "right-face",
                "label": "right hammer end face",
                "semantic_type": "cylindrical_end_face",
                "bbox_xyxy_norm": [0.6, 0.2, 0.9, 0.8],
                "visual_evidence": "Circular flat end cap visible on the right hammer head.",
                "uncertainty": "medium"
            }
        ],
        "relations": [
            {
                "id": "possible-contact",
                "subject_id": "left-face",
                "predicate": "contacts_at",
                "object_id": "right-face",
                "confidence": 0.55,
                "evidence_bbox_xyxy_norm": [0.42, 0.4, 0.58, 0.6],
                "visual_evidence": "The two visible end faces appear to meet at the narrow central boundary.",
                "uncertainty": "high",
                "details": {
                    "subject_surface": "cylindrical_end_face",
                    "object_surface": "cylindrical_end_face"
                }
            }
        ],
        "uncertainties": ["The exact contact boundary is partly occluded."]
    })


class GrokVisionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / "sample.png"
        Image.new("RGB", (64, 48), color=(12, 34, 56)).save(self.image)

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_api_key_fails_clearly(self):
        env = {k: v for k, v in os.environ.items() if k != "XAI_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(GrokVisionError, "XAI_API_KEY"):
                GrokSpatialReasoner(api_key="")

    def test_reads_xai_api_key_from_env(self):
        with mock.patch.dict(os.environ, {"XAI_API_KEY": "test-key-123"}, clear=False):
            reasoner = GrokSpatialReasoner()
            self.assertEqual(reasoner.api_key, "test-key-123")
            self.assertEqual(reasoner.provider_id, "xai.grok.vision")

    def test_mock_transport_parses_responses_api_payload(self):
        captured = {}

        def transport(url, payload):
            captured["url"] = url
            captured["payload"] = payload
            body = {
                "id": "resp_test_001",
                "output_text": _valid_json_text(),
            }
            return body, {"x-request-id": "req-abc"}

        reasoner = GrokSpatialReasoner(api_key="k", transport=transport, model_id="grok-4")
        result = reasoner.propose(self.image)
        data = result.to_dict()
        self.assertEqual(data["provider_id"], "xai.grok.vision")
        self.assertEqual(data["model_id"], "grok-4")
        self.assertEqual(data["status"], "unreviewed_model_proposals")
        self.assertEqual(data["relations"][0]["status"], "candidate")
        self.assertFalse(data["relations"][0]["geometry_lock"])
        self.assertFalse(data["nodes"][0]["edit_permission"])
        self.assertEqual(reasoner.last_request_meta["request_id"], "req-abc")
        content = captured["payload"]["input"][0]["content"]
        self.assertEqual(content[0]["type"], "input_image")
        self.assertEqual(content[0]["detail"], "high")
        self.assertTrue(content[0]["image_url"].startswith("data:image/png;base64,"))
        self.assertNotIn("Qwen", json.dumps(captured["payload"]))

    def test_malformed_json_from_model_is_rejected(self):
        def transport(url, payload):
            return {"output_text": "Here is the JSON: {}"}, {}

        reasoner = GrokSpatialReasoner(api_key="k", transport=transport)
        with self.assertRaises(ReasoningOutputError):
            reasoner.propose(self.image)

    def test_candidate_status_cannot_be_human_verified_by_model(self):
        def transport(url, payload):
            return {"output_text": _valid_json_text()}, {}

        reasoner = GrokSpatialReasoner(api_key="k", transport=transport)
        data = reasoner.propose(self.image).to_dict()
        for relation in data["relations"]:
            self.assertEqual(relation["status"], "candidate")
            self.assertEqual(relation["source"], "model")
            self.assertFalse(relation["geometry_lock"])

    def test_does_not_import_qwen_or_transformers_on_default_path(self):
        import sys
        banned = [name for name in sys.modules if "transformers" in name or "qwen3_vl" in name]
        # Importing this test module may load many things; ensure constructing Grok path
        # does not require transformers.
        with mock.patch.dict(sys.modules, {"transformers": None}):
            def transport(url, payload):
                return {"output_text": _valid_json_text()}, {}
            reasoner = GrokSpatialReasoner(api_key="k", transport=transport)
            result = reasoner.propose(self.image)
            self.assertEqual(len(result.nodes), 2)

    def test_output_text_from_nested_content_blocks(self):
        def transport(url, payload):
            return {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": _valid_json_text()}
                        ],
                    }
                ]
            }, {}

        reasoner = GrokSpatialReasoner(api_key="k", transport=transport)
        self.assertEqual(len(reasoner.propose(self.image).relations), 1)
