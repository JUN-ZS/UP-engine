import json
import unittest

from ige.read.reasoning import ReasoningOutputError, parse_reasoning_response


def valid_payload():
    return {
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
    }


class ReasoningParserTests(unittest.TestCase):
    def test_valid_relation_is_forced_to_candidate(self):
        parsed = parse_reasoning_response(
            json.dumps(valid_payload()),
            provider_id="test.vlm",
            model_id="test-model",
        )
        data = parsed.to_dict()
        self.assertEqual(data["status"], "unreviewed_model_proposals")
        self.assertEqual(data["relations"][0]["status"], "candidate")
        self.assertFalse(data["relations"][0]["geometry_lock"])
        self.assertFalse(data["nodes"][0]["edit_permission"])
        self.assertEqual(data["confidence_semantics"],
                         "uncalibrated_model_self_assessment_not_probability")

    def test_invalid_box_coordinates_rejected(self):
        raw = valid_payload()
        raw["nodes"][0]["bbox_xyxy_norm"] = [-0.1, 0.2, 0.4, 0.8]
        with self.assertRaises(ReasoningOutputError):
            parse_reasoning_response(json.dumps(raw), provider_id="x", model_id="y")

    def test_unknown_node_reference_rejected(self):
        raw = valid_payload()
        raw["relations"][0]["object_id"] = "not-a-node"
        with self.assertRaisesRegex(ReasoningOutputError, "unknown proposed node"):
            parse_reasoning_response(json.dumps(raw), provider_id="x", model_id="y")

    def test_contacts_at_requires_surface_types(self):
        raw = valid_payload()
        raw["relations"][0]["details"] = {"subject_surface": "end_face"}
        with self.assertRaisesRegex(ReasoningOutputError, "object_surface"):
            parse_reasoning_response(json.dumps(raw), provider_id="x", model_id="y")

    def test_invalid_json_is_not_repaired(self):
        with self.assertRaises(ReasoningOutputError):
            parse_reasoning_response("Here is the JSON: {}", provider_id="x", model_id="y")

    def test_non_positive_bbox_rejected(self):
        raw = valid_payload()
        raw["relations"][0]["evidence_bbox_xyxy_norm"] = [0.5, 0.5, 0.5, 0.8]
        with self.assertRaises(ReasoningOutputError):
            parse_reasoning_response(json.dumps(raw), provider_id="x", model_id="y")
