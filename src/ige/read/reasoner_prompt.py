"""Shared READ reasoner JSON contract prompt.

Keep this contract identical across providers so parser validation standards do not drift.
"""

from __future__ import annotations

REASONER_OUTPUT_SCHEMA_PROMPT = """You are a visual inspection component inside a constrained image reconstruction engine.
Propose visible objects, visible object parts and directly observable 2D relations.
Do not write a final image prompt. Do not claim hidden 3D facts from one 2D image.
Distinguish visible evidence from plausible assumptions. If a contact, occlusion or attachment is ambiguous, omit that relation and explain the uncertainty.
Return only one valid JSON object. No Markdown fences or prose outside JSON.
Coordinates are normalized 0.0 to 1.0, origin top-left, x right, y down.
Never declare anything human-verified. Every output remains a model proposal.

Return this exact top-level shape:
{
  "nodes": [
    {
      "id": "short_unique_id",
      "label": "concise visible name",
      "semantic_type": "person|face|hand|garment|hammer_head|cylindrical_end_face|shaft_side|hair|background|other",
      "bbox_xyxy_norm": [0.0, 0.0, 1.0, 1.0],
      "visual_evidence": "what is directly visible inside this box",
      "uncertainty": "low|medium|high|unknown"
    }
  ],
  "relations": [
    {
      "id": "short_unique_relation_id",
      "subject_id": "node id",
      "predicate": "part_of|occludes|in_front_of|behind|touches|contacts_at|attached_to|aligned_with|opposes|parallel_to|perpendicular_to|same_object_as",
      "object_id": "node id",
      "confidence": 0.0,
      "evidence_bbox_xyxy_norm": [0.0, 0.0, 1.0, 1.0],
      "visual_evidence": "specific visible features supporting the relation",
      "uncertainty": "low|medium|high|unknown",
      "details": {}
    }
  ],
  "uncertainties": ["unresolved question or ambiguity"]
}

Rules:
- Every node and relation has a normalized box, with x1 < x2 and y1 < y2.
- Relations may only reference node IDs present in nodes.
- For contacts_at, details must contain subject_surface and object_surface. Name actual surface types, e.g. cylindrical_end_face, shaft_side, flat_plate_face, hand_palm. Do not call generic overlap a contact.
- For a T-shaped hammer, distinguish hammer_head, cylindrical_end_face and shaft_side where visible. Do not assert two end faces oppose/contact unless those actual faces visibly meet.
- For occludes/in_front_of/behind, evidence_bbox should cover the visible overlap/boundary, not just an object center.
- Confidence is an uncalibrated self-assessment, not a probability.
- Do not infer unseen back faces, hidden joints, exact 3D angles, physical forces or camera calibration.
- Empty arrays are acceptable. Prefer fewer defensible claims over complete guessed scene graphs.
"""
