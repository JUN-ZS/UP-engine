from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
import re
from typing import Any


class RelationStatus(StrEnum):
    CANDIDATE = "candidate"
    HUMAN_VERIFIED = "human_verified"
    REJECTED = "rejected"


RELATION_PREDICATES = frozenset({
    "part_of",
    "occludes",
    "in_front_of",
    "behind",
    "touches",
    "contacts_at",
    "attached_to",
    "aligned_with",
    "opposes",
    "parallel_to",
    "perpendicular_to",
    "same_object_as",
})


@dataclass(frozen=True)
class RelationAnnotation:
    relation_id: str
    subject_region_id: str
    predicate: str
    object_region_id: str
    status: RelationStatus
    source: str
    confidence: float | None
    evidence: str
    evidence_region_id: str | None
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.relation_id,
            "subject_region_id": self.subject_region_id,
            "predicate": self.predicate,
            "object_region_id": self.object_region_id,
            "status": self.status.value,
            "source": self.source,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "evidence_region_id": self.evidence_region_id,
            "details": self.details,
        }


def _reject_part_of_cycles(relations: list[RelationAnnotation]) -> None:
    graph: dict[str, set[str]] = {}
    for relation in relations:
        if relation.predicate == "part_of" and relation.status != RelationStatus.REJECTED:
            graph.setdefault(relation.subject_region_id, set()).add(relation.object_region_id)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError("part_of relations contain a cycle")
        if node in visited:
            return
        visiting.add(node)
        for parent in graph.get(node, ()):
            visit(parent)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def load_relations(
    path: str | Path | None, known_region_ids: set[str]
) -> tuple[RelationAnnotation, ...]:
    if path is None:
        return ()
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict) or raw.get("version") != "0.1.0":
        raise ValueError("relations file must declare version='0.1.0'")
    entries = raw.get("relations")
    if not isinstance(entries, list):
        raise ValueError("relations must be a list")
    result: list[RelationAnnotation] = []
    seen: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ValueError(f"relations[{index}] must be an object")
        relation_id = str(item.get("id", "")).strip()
        if not relation_id or not re.fullmatch(r"[A-Za-z0-9_.-]+", relation_id):
            raise ValueError(f"relations[{index}].id is invalid")
        if relation_id in seen:
            raise ValueError(f"duplicate relation id: {relation_id}")
        seen.add(relation_id)
        subject = str(item.get("subject_region_id", "")).strip()
        object_id = str(item.get("object_region_id", "")).strip()
        if subject not in known_region_ids or object_id not in known_region_ids:
            raise ValueError(f"relations[{index}] references an unknown region")
        if subject == object_id:
            raise ValueError(f"relations[{index}] subject and object must differ")
        predicate = str(item.get("predicate", "")).strip()
        if predicate not in RELATION_PREDICATES:
            raise ValueError(f"relations[{index}].predicate is unsupported: {predicate}")
        try:
            status = RelationStatus(item.get("status"))
        except ValueError as exc:
            raise ValueError(f"relations[{index}].status is invalid") from exc
        source = str(item.get("source", "")).strip()
        if source not in {"human", "model"}:
            raise ValueError(f"relations[{index}].source must be human or model")
        confidence_raw = item.get("confidence")
        confidence = None if confidence_raw is None else float(confidence_raw)
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise ValueError(f"relations[{index}].confidence must be within [0, 1]")
        evidence = str(item.get("evidence", "")).strip()
        if status == RelationStatus.HUMAN_VERIFIED and source != "human":
            raise ValueError("human_verified relations must have source='human'")
        if status == RelationStatus.HUMAN_VERIFIED and not evidence:
            raise ValueError("human_verified relations require evidence")
        details = item.get("details", {})
        if not isinstance(details, dict):
            raise ValueError(f"relations[{index}].details must be an object")
        if predicate == "contacts_at":
            if not str(details.get("subject_surface", "")).strip() or not str(details.get("object_surface", "")).strip():
                raise ValueError("contacts_at requires details.subject_surface and details.object_surface")
        evidence_region_id = item.get("evidence_region_id")
        if evidence_region_id is not None and evidence_region_id not in known_region_ids:
            raise ValueError(f"relations[{index}].evidence_region_id references an unknown region")
        result.append(RelationAnnotation(
            relation_id=relation_id,
            subject_region_id=subject,
            predicate=predicate,
            object_region_id=object_id,
            status=status,
            source=source,
            confidence=confidence,
            evidence=evidence,
            evidence_region_id=evidence_region_id,
            details=details,
        ))
    _reject_part_of_cycles(result)
    return tuple(result)
