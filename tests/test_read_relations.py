import json
import tempfile
import unittest
from pathlib import Path

from ige.read.relations import load_relations


class RelationTests(unittest.TestCase):
    def _write(self, raw):
        temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
        with temp:
            json.dump(raw, temp)
        self.addCleanup(Path(temp.name).unlink, missing_ok=True)
        return Path(temp.name)

    def _relation(self, **overrides):
        relation = {
            "id": "contact-1",
            "subject_region_id": "left",
            "predicate": "contacts_at",
            "object_region_id": "right",
            "status": "human_verified",
            "source": "human",
            "confidence": 1.0,
            "evidence": "Visible face-to-face contact in the source frame.",
            "evidence_region_id": "contact",
            "details": {
                "subject_surface": "cylindrical_end_face",
                "object_surface": "cylindrical_end_face"
            }
        }
        relation.update(overrides)
        return relation

    def test_verified_contact_requires_both_surfaces_and_evidence(self):
        path = self._write({"version": "0.1.0", "relations": [self._relation()]})
        relations = load_relations(path, {"left", "right", "contact"})
        self.assertEqual(relations[0].status.value, "human_verified")
        self.assertEqual(relations[0].details["subject_surface"], "cylindrical_end_face")

    def test_unknown_region_reference_rejected(self):
        path = self._write({"version": "0.1.0", "relations": [self._relation(object_region_id="missing")]})
        with self.assertRaisesRegex(ValueError, "unknown region"):
            load_relations(path, {"left", "right", "contact"})

    def test_contacts_at_requires_surface_names(self):
        path = self._write({"version": "0.1.0", "relations": [self._relation(details={})]})
        with self.assertRaisesRegex(ValueError, "subject_surface"):
            load_relations(path, {"left", "right", "contact"})

    def test_model_cannot_claim_human_verified(self):
        path = self._write({"version": "0.1.0", "relations": [self._relation(source="model")]})
        with self.assertRaisesRegex(ValueError, "source='human'"):
            load_relations(path, {"left", "right", "contact"})

    def test_part_of_cycle_rejected(self):
        first = {
            "id": "part-a", "subject_region_id": "a", "predicate": "part_of",
            "object_region_id": "b", "status": "human_verified", "source": "human",
            "confidence": 1, "evidence": "A is a part of B."
        }
        second = {
            "id": "part-b", "subject_region_id": "b", "predicate": "part_of",
            "object_region_id": "a", "status": "human_verified", "source": "human",
            "confidence": 1, "evidence": "B is a part of A."
        }
        path = self._write({"version": "0.1.0", "relations": [first, second]})
        with self.assertRaisesRegex(ValueError, "cycle"):
            load_relations(path, {"a", "b"})
