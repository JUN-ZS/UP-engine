import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import os

from PIL import Image

from ige.read.skill_diagnosis import GrokSkillDiagnoser, SkillDiagnosisError, SKILL_DIAGNOSIS_OBSERVATIONS


def diagnosis_payload():
    names = (
        *SKILL_DIAGNOSIS_OBSERVATIONS,
    )
    observations = {}
    for name in names:
        observations[name] = {
            "state": "unknown",
            "evidence": "Not enough visible evidence for a confident judgement.",
            "uncertainty": "high",
        }
    observations["metal_detail_low"] = {
        "state": "present",
        "evidence": "The gold mesh weave is visibly unresolved in the upper torso region.",
        "bbox_xyxy_norm": [0.2, 0.1, 0.7, 0.8],
        "confidence": 0.76,
        "uncertainty": "medium",
    }
    observations["identity_drift"] = {
        "state": "present",
        "evidence": "The visible face differs from the supplied canonical reference.",
        "bbox_xyxy_norm": [0.4, 0.05, 0.6, 0.25],
        "confidence": 0.6,
        "uncertainty": "high",
    }
    return json.dumps({"observations": observations})


class GrokSkillDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "base.png"
        self.identity = self.root / "a8b.png"
        Image.new("RGB", (64, 48), color=(20, 30, 40)).save(self.base)
        Image.new("RGB", (64, 64), color=(80, 70, 60)).save(self.identity)

    def tearDown(self):
        self.temp.cleanup()

    def test_requires_api_key(self):
        env = {k: v for k, v in os.environ.items() if k != "XAI_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "XAI_API_KEY"):
                GrokSkillDiagnoser(api_key="")

    def test_returns_candidate_only_diagnosis_and_forces_identity_unknown_without_ref(self):
        captured = {}

        def transport(url, payload):
            captured["payload"] = payload
            return {"output_text": diagnosis_payload(), "id": "response-1"}, {"x-request-id": "req-1"}

        diagnoser = GrokSkillDiagnoser(api_key="test-key", transport=transport)
        report = diagnoser.diagnose(self.base)
        self.assertEqual(report["diagnosis_version"], "1.0")
        self.assertEqual(report["observations"]["metal_detail_low"]["state"], "present")
        self.assertEqual(report["observations"]["metal_detail_low"]["source"], "grok_vision")
        self.assertEqual(report["observations"]["metal_detail_low"]["verification"], "candidate")
        self.assertEqual(report["observations"]["metal_detail_low"]["bbox_xyxy_norm"], [0.2, 0.1, 0.7, 0.8])
        self.assertEqual(report["observations"]["identity_drift"]["state"], "unknown")
        self.assertIn("No identity reference", report["observations"]["identity_drift"]["evidence"])
        self.assertFalse(report["final_acceptance"])
        self.assertEqual(report["diagnosis_meta"]["request_id"], "req-1")
        self.assertEqual(len(captured["payload"]["input"][0]["content"]), 2)

    def test_identity_reference_is_sent_as_second_image_but_still_candidate(self):
        captured = {}

        def transport(url, payload):
            captured["payload"] = payload
            return {"output_text": diagnosis_payload()}, {}

        diagnoser = GrokSkillDiagnoser(api_key="test-key", transport=transport)
        report = diagnoser.diagnose(
            self.base,
            identity_reference=self.identity,
            identity_reference_id="a8b78fe5-2654-4f6f-84e3-c1dfbee61004",
        )
        content = captured["payload"]["input"][0]["content"]
        self.assertEqual(content[0]["type"], "input_image")
        self.assertEqual(content[1]["type"], "input_image")
        self.assertEqual(content[-1]["type"], "input_text")
        self.assertEqual(report["observations"]["identity_drift"]["state"], "present")
        self.assertEqual(report["observations"]["identity_drift"]["verification"], "candidate")
        self.assertEqual(report["references"][0]["asset_id"], "a8b78fe5-2654-4f6f-84e3-c1dfbee61004")

    def test_malformed_json_is_rejected_without_repair(self):
        diagnoser = GrokSkillDiagnoser(
            api_key="test-key",
            transport=lambda url, payload: ({"output_text": "not JSON"}, {}),
        )
        with self.assertRaises(SkillDiagnosisError):
            diagnoser.diagnose(self.base)

    def test_invalid_bbox_is_rejected(self):
        value = json.loads(diagnosis_payload())
        value["observations"]["metal_detail_low"]["bbox_xyxy_norm"] = [0.8, 0.2, 0.1, 0.9]
        diagnoser = GrokSkillDiagnoser(
            api_key="test-key",
            transport=lambda url, payload: ({"output_text": json.dumps(value)}, {}),
        )
        with self.assertRaisesRegex(SkillDiagnosisError, "bbox"):
            diagnoser.diagnose(self.base)

    def test_missing_observations_are_unknown_not_guessed(self):
        diagnoser = GrokSkillDiagnoser(
            api_key="test-key",
            transport=lambda url, payload: ({"output_text": json.dumps({"observations": {}})}, {}),
        )
        report = diagnoser.diagnose(self.base)
        self.assertEqual(
            set(report["observations"]),
            set(SKILL_DIAGNOSIS_OBSERVATIONS),
        )
        self.assertTrue(all(item["state"] == "unknown" for item in report["observations"].values()))

if __name__ == "__main__":
    unittest.main()
