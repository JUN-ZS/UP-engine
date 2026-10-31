from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
from typing import Any, Protocol

from .relations import RELATION_PREDICATES


class ReasoningOutputError(ValueError):
    """A visual reasoning response is malformed or lacks auditable evidence."""


def _bbox(value: Any, field_name: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ReasoningOutputError(f"{field_name} must be [x1, y1, x2, y2]")
    if any(isinstance(part, bool) or not isinstance(part, (int, float)) for part in value):
        raise ReasoningOutputError(f"{field_name} coordinates must be numeric")
    coords = tuple(float(part) for part in value)
    x1, y1, x2, y2 = coords
    if not all(0.0 <= part <= 1.0 for part in coords):
        raise ReasoningOutputError(f"{field_name} coordinates must be normalized to [0, 1]")
    if x2 <= x1 or y2 <= y1:
        raise ReasoningOutputError(f"{field_name} must have positive width and height")
    return coords


@dataclass(frozen=True)
class RegionProposal:
    proposal_id: str
    label: str
    semantic_type: str
    bbox_xyxy_norm: tuple[float, float, float, float]
    visual_evidence: str
    uncertainty: str


@dataclass(frozen=True)
class RelationProposal:
    proposal_id: str
    subject_id: str
    predicate: str
    object_id: str
    confidence: float | None
    evidence_bbox_xyxy_norm: tuple[float, float, float, float]
    visual_evidence: str
    uncertainty: str
    details: dict[str, Any]


@dataclass(frozen=True)
class ReasoningProposalSet:
    provider_id: str
    model_id: str
    nodes: tuple[RegionProposal, ...]
    relations: tuple[RelationProposal, ...]
    uncertainties: tuple[str, ...]
    raw_response_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "status": "unreviewed_model_proposals",
            "confidence_semantics": "uncalibrated_model_self_assessment_not_probability",
            "nodes": [
                {
                    "id": node.proposal_id,
                    "label": node.label,
                    "semantic_type": node.semantic_type,
                    "bbox_xyxy_norm": list(node.bbox_xyxy_norm),
                    "visual_evidence": node.visual_evidence,
                    "uncertainty": node.uncertainty,
                    "status": "candidate",
                    "source": "model",
                    "edit_permission": False,
                }
                for node in self.nodes
            ],
            "relations": [
                {
                    "id": relation.proposal_id,
                    "subject_id": relation.subject_id,
                    "predicate": relation.predicate,
                    "object_id": relation.object_id,
                    "confidence": relation.confidence,
                    "evidence_bbox_xyxy_norm": list(relation.evidence_bbox_xyxy_norm),
                    "visual_evidence": relation.visual_evidence,
                    "uncertainty": relation.uncertainty,
                    "details": relation.details,
                    "status": "candidate",
                    "source": "model",
                    "geometry_lock": False,
                }
                for relation in self.relations
            ],
            "uncertainties": list(self.uncertainties),
            "raw_response_sha256": self.raw_response_sha256,
            "limitations": [
                "All nodes and relations are proposals, not verified observations.",
                "Model confidence is not calibrated probability.",
                "2D evidence does not establish hidden surfaces or metric 3D geometry.",
            ],
        }


class VisualReasoner(Protocol):
    provider_id: str
    model_id: str

    def propose(
        self,
        image_path: str | Path,
        *,
        focus: str,
    ) -> ReasoningProposalSet:
        """Return structured object/relation proposals; never accept or authorize edits."""
        ...


def parse_reasoning_response(
    text: str,
    *,
    provider_id: str,
    model_id: str,
) -> ReasoningProposalSet:
    """Strictly parse model output. No regex repair or guessed missing fields."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    try:
        raw = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ReasoningOutputError(
            f"reasoner output is not valid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(raw, dict):
        raise ReasoningOutputError("reasoner JSON root must be an object")
    if set(raw) - {"nodes", "relations", "uncertainties"}:
        raise ReasoningOutputError("reasoner JSON contains unsupported top-level keys")
    nodes_raw = raw.get("nodes")
    relations_raw = raw.get("relations")
    uncertainties_raw = raw.get("uncertainties", [])
    if not isinstance(nodes_raw, list) or not isinstance(relations_raw, list):
        raise ReasoningOutputError("nodes and relations must be arrays")
    if not isinstance(uncertainties_raw, list) or any(not isinstance(x, str) for x in uncertainties_raw):
        raise ReasoningOutputError("uncertainties must be an array of strings")

    nodes: list[RegionProposal] = []
    node_ids: set[str] = set()
    for index, item in enumerate(nodes_raw):
        if not isinstance(item, dict):
            raise ReasoningOutputError(f"nodes[{index}] must be an object")
        proposal_id = str(item.get("id", "")).strip()
        label = str(item.get("label", "")).strip()
        semantic_type = str(item.get("semantic_type", "")).strip()
        visual_evidence = str(item.get("visual_evidence", "")).strip()
        uncertainty = str(item.get("uncertainty", "unknown")).strip()
        if not proposal_id or not all(char.isalnum() or char in "_.-" for char in proposal_id):
            raise ReasoningOutputError(f"nodes[{index}].id is invalid")
        if proposal_id in node_ids:
            raise ReasoningOutputError(f"duplicate proposed node id: {proposal_id}")
        node_ids.add(proposal_id)
        if not label or not semantic_type or not visual_evidence:
            raise ReasoningOutputError(
                f"nodes[{index}] requires label, semantic_type and visual_evidence"
            )
        if uncertainty not in {"low", "medium", "high", "unknown"}:
            raise ReasoningOutputError(f"nodes[{index}].uncertainty is invalid")
        nodes.append(RegionProposal(
            proposal_id=proposal_id,
            label=label,
            semantic_type=semantic_type,
            bbox_xyxy_norm=_bbox(item.get("bbox_xyxy_norm"), f"nodes[{index}].bbox_xyxy_norm"),
            visual_evidence=visual_evidence,
            uncertainty=uncertainty,
        ))

    relations: list[RelationProposal] = []
    relation_ids: set[str] = set()
    for index, item in enumerate(relations_raw):
        if not isinstance(item, dict):
            raise ReasoningOutputError(f"relations[{index}] must be an object")
        proposal_id = str(item.get("id", "")).strip()
        subject_id = str(item.get("subject_id", "")).strip()
        object_id = str(item.get("object_id", "")).strip()
        predicate = str(item.get("predicate", "")).strip()
        visual_evidence = str(item.get("visual_evidence", "")).strip()
        uncertainty = str(item.get("uncertainty", "unknown")).strip()
        if not proposal_id or not all(char.isalnum() or char in "_.-" for char in proposal_id):
            raise ReasoningOutputError(f"relations[{index}].id is invalid")
        if proposal_id in relation_ids:
            raise ReasoningOutputError(f"duplicate proposed relation id: {proposal_id}")
        relation_ids.add(proposal_id)
        if subject_id not in node_ids or object_id not in node_ids:
            raise ReasoningOutputError(f"relations[{index}] references an unknown proposed node")
        if subject_id == object_id:
            raise ReasoningOutputError(f"relations[{index}] subject and object must differ")
        if predicate not in RELATION_PREDICATES:
            raise ReasoningOutputError(f"relations[{index}].predicate is unsupported")
        if not visual_evidence:
            raise ReasoningOutputError(f"relations[{index}] requires visual_evidence")
        if uncertainty not in {"low", "medium", "high", "unknown"}:
            raise ReasoningOutputError(f"relations[{index}].uncertainty is invalid")
        confidence_raw = item.get("confidence")
        if confidence_raw is not None and (
            isinstance(confidence_raw, bool) or not isinstance(confidence_raw, (int, float))
        ):
            raise ReasoningOutputError(f"relations[{index}].confidence must be numeric or null")
        confidence = None if confidence_raw is None else float(confidence_raw)
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise ReasoningOutputError(f"relations[{index}].confidence must be within [0, 1]")
        details = item.get("details", {})
        if not isinstance(details, dict):
            raise ReasoningOutputError(f"relations[{index}].details must be an object")
        if predicate == "contacts_at":
            if not str(details.get("subject_surface", "")).strip():
                raise ReasoningOutputError(f"relations[{index}] contacts_at requires subject_surface")
            if not str(details.get("object_surface", "")).strip():
                raise ReasoningOutputError(f"relations[{index}] contacts_at requires object_surface")
        relations.append(RelationProposal(
            proposal_id=proposal_id,
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            confidence=confidence,
            evidence_bbox_xyxy_norm=_bbox(
                item.get("evidence_bbox_xyxy_norm"),
                f"relations[{index}].evidence_bbox_xyxy_norm",
            ),
            visual_evidence=visual_evidence,
            uncertainty=uncertainty,
            details=details,
        ))

    return ReasoningProposalSet(
        provider_id=provider_id,
        model_id=model_id,
        nodes=tuple(nodes),
        relations=tuple(relations),
        uncertainties=tuple(uncertainties_raw),
        raw_response_sha256=digest,
    )
