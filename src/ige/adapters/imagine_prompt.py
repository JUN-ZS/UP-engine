"""Shared constrained Imagine prompt builders for HERE and xAI API backends.

Prompt text is not a permission system. Pixel protection is enforced later by
the UP-engine compositor. Geometry locks remain human-verified packet fields.
"""

from __future__ import annotations

from typing import Any


def format_targets(targets: Any) -> str:
    if not isinstance(targets, list) or not targets:
        return "human-approved editable regions from generation packet"
    parts = []
    for item in targets:
        if not isinstance(item, dict):
            continue
        rid = item.get("region_id") or "?"
        label = item.get("label") or rid
        semantic = item.get("semantic_type") or "object"
        parts.append(f"{rid} ({label}, type={semantic})")
    return "; ".join(parts) if parts else "human-approved editable regions"


def format_geometry_locks(relations: Any) -> str:
    if not isinstance(relations, list) or not relations:
        return "None supplied beyond the packet's protected-region complement."
    lines = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        lines.append(
            f"- {relation.get('subject_id')} {relation.get('predicate')} "
            f"{relation.get('object_id')}; evidence={relation.get('evidence') or relation.get('visual_evidence') or 'n/a'}"
        )
    return "\n".join(lines) if lines else "None."


def build_constrained_imagine_prompt(
    *,
    objective: str,
    target_text: str,
    protected_region_ids: list[str],
    geometry_lock_text: str,
    target_state: str | None = None,
) -> str:
    protected = ", ".join(protected_region_ids) if protected_region_ids else "all non-target pixels"
    state = target_state or f"apply only the objective: {objective}"
    return f"""Use the supplied BASE image as the authoritative visual reference. This is a controlled image-editing task, NOT a free redesign.

TASK
* Objective: {objective}
* Editable regions: {target_text}
* Protected regions: {protected}
* Human-verified geometry constraints:
{geometry_lock_text}
* Required visual state: {state}

STRICT PRESERVATION RULES
1. Preserve the original camera position, viewing angle, perspective, framing, and composition.
2. Preserve the identity, silhouette, topology, proportions, and material identity of every object unless the task explicitly authorizes a change.
3. Do not redesign, replace, duplicate, merge, remove, or invent objects.
4. Do not modify protected content intentionally. The final pixel-level protection will be enforced separately by the UP-engine compositor.
5. Do not treat uncertain or model-inferred relationships as confirmed geometry.
6. Do not introduce extra objects, decorative elements, text, labels, watermarks, borders, or a collage.
7. Return one full-frame candidate image. Do not return a contact sheet or multiple alternative designs.

GEOMETRY RULES
* Follow every human-verified geometry constraint exactly.
* Physical contact must occur only at the specified surfaces.
* Do not create false contact between nearby or crossing objects.
* Preserve rigid-object geometry. Do not bend, melt, stretch, fuse, or deform rigid parts.
* Do not change the camera to hide a geometry error.
* If a requested edit cannot be represented without violating a locked constraint, prioritize the locked constraint.

OUTPUT
* Produce a single candidate image for this request.
* Do not claim that the output is pixel-aligned, geometrically validated, or pixel-preserving.
* The output is an unverified candidate for UP-engine registration and audit.
"""


def prompt_from_packet(packet: dict[str, Any], *, prompt_override: str | None = None) -> str:
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()
    objective = str(packet.get("objective") or "").strip()
    if not objective:
        raise ValueError("generation packet objective is empty and no prompt was supplied")
    geometry_locks = packet.get("geometry_locks", {})
    lock_relations = geometry_locks.get("relations", []) if isinstance(geometry_locks, dict) else []
    protected_ids: list[str] = []
    if isinstance(geometry_locks, dict):
        protected_ids = [str(x) for x in (geometry_locks.get("protected_region_ids") or [])]
    return build_constrained_imagine_prompt(
        objective=objective,
        target_text=format_targets(packet.get("targets")),
        protected_region_ids=protected_ids,
        geometry_lock_text=format_geometry_locks(lock_relations),
    )


def nearest_supported_aspect(width: int, height: int) -> str | None:
    if width <= 0 or height <= 0:
        return None
    value = width / float(height)
    candidates = {
        "1:1": 1.0,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "3:2": 3 / 2,
        "2:3": 2 / 3,
        "2:1": 2.0,
        "1:2": 0.5,
        "21:9": 21 / 9,
        "5:2": 2.5,
    }
    best = min(candidates.items(), key=lambda item: abs(item[1] - value))
    if abs(best[1] - value) / value > 0.08:
        return None
    return best[0]
