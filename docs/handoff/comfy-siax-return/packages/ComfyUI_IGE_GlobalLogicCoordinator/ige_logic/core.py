from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw

ACTIONS = {"PRESERVE": 0, "REFINE": 1, "GENERATE": 2, "REJECT": 3}
ACTION_NAMES = {v: k for k, v in ACTIONS.items()}
# Permission lattice: child scopes cannot acquire more mutation permission than a parent.
PERMISSION = {"PRESERVE": 0, "REFINE": 1, "GENERATE": 2}


class ContractError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(value: str | Path | dict) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, Path):
        return json.loads(value.read_text(encoding="utf-8"))
    value = str(value)
    p = Path(value)
    if p.exists() and p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return json.loads(value)


def validate_action(action: str) -> str:
    a = str(action).upper()
    if a not in ACTIONS:
        raise ContractError(f"Unknown action {action!r}; allowed={sorted(ACTIONS)}")
    return a


def validate_child_action(parent_action: str, child_action: str) -> None:
    """Fail closed if a child subset tries to loosen a parent rule."""
    p, c = validate_action(parent_action), validate_action(child_action)
    if p == "REJECT":
        if c != "REJECT":
            raise ContractError("Child rule cannot override parent REJECT")
        return
    if c == "REJECT":
        return
    if PERMISSION[c] > PERMISSION[p]:
        raise ContractError(f"Child action {c} weakens parent action {p}")


def _polygon_for_rule(rule: dict, geometry: dict) -> list[list[float]] | None:
    shape = rule.get("shape", {})
    if "polygon_xy" in rule:
        return rule["polygon_xy"]
    if shape.get("type") == "polygon":
        return shape.get("polygon_xy")
    if rule.get("scope") == "object" or shape.get("type") == "object_polygon":
        oid = rule.get("object_id") or shape.get("object_id")
        obj = geometry.get("object", {})
        if oid and obj.get("id") == oid:
            return obj.get("polygon_xy")
    if shape.get("type") == "object_bbox":
        oid = shape.get("object_id")
        obj = geometry.get("object", {})
        if oid and obj.get("id") == oid:
            x0, y0, x1, y1 = obj["bbox_xyxy"]
            return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    return None


def rasterize_polygon(width: int, height: int, polygon: list[list[float]]) -> np.ndarray:
    im = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(im)
    pts = [(float(x), float(y)) for x, y in polygon]
    if len(pts) < 3:
        raise ContractError("Polygon needs at least 3 points")
    draw.polygon(pts, fill=255)
    return np.asarray(im, dtype=np.uint8) > 0


def compile_contract(source_shape: tuple[int, int], geometry: dict, policy: dict,
                     source_sha256: str | None = None, iteration_state: dict | None = None) -> dict:
    """Compile global semantic/geometry policy into a versioned, auditable contract.

    source_shape is (height, width) for the full Siax-upscaled canvas.
    """
    h, w = map(int, source_shape)
    if h <= 0 or w <= 0:
        raise ContractError(f"Invalid source dimensions {(w, h)}")
    if geometry.get("schema_version") not in ("ige-object-geometry/1.0", None):
        raise ContractError("Unsupported geometry schema")
    gsrc = geometry.get("source", {})
    gw, gh = gsrc.get("width"), gsrc.get("height")
    if gw is not None and gh is not None and (int(gw), int(gh)) != (w, h):
        raise ContractError(f"Geometry canvas {(gw, gh)} != source canvas {(w, h)}; explicit coordinate transform required")
    if policy.get("schema_version") != "ige-global-logic-policy/0.1":
        raise ContractError("Unsupported policy schema")
    default_action = validate_action(policy.get("default_action", "PRESERVE"))
    if default_action == "GENERATE":
        raise ContractError("default_action cannot be GENERATE; new content requires an explicit operator-confirmed spatial polygon")
    actions = np.full((h, w), ACTIONS[default_action], dtype=np.uint8)
    explicit_mask = np.zeros((h, w), dtype=bool)
    decision_rank = np.full((h, w), -1 if default_action == "REJECT" else PERMISSION.get(default_action, 1), dtype=np.int8)
    geometry_guard = np.zeros((h, w), dtype=np.uint8)
    applied_rules = []
    rule_masks = {}
    rules = list(policy.get("rules", [])) + list(policy.get("operator_regions", []))
    rules_by_id = {r.get("id"): r for r in rules if r.get("id")}
    if len(rules_by_id) != len([r for r in rules if r.get("id")]):
        raise ContractError("Rule IDs must be unique")
    for rule in rules:
        parent_id = rule.get("parent_rule_id")
        if parent_id:
            if parent_id not in rules_by_id:
                raise ContractError(f"Rule {rule.get('id')} references missing parent_rule_id {parent_id}")
            validate_child_action(rules_by_id[parent_id].get("action", default_action), rule.get("action", default_action))
    # Explicit regions must be operator-confirmed before GENERATE can be enabled.
    for rule in sorted(rules, key=lambda r: (int(r.get("priority", 0)), r.get("id", ""))):
        action = validate_action(rule.get("action", default_action))
        if action == "GENERATE" and not bool(rule.get("operator_confirmed", False)):
            raise ContractError(f"GENERATE rule {rule.get('id')} requires operator_confirmed=true")
        polygon = _polygon_for_rule(rule, geometry)
        if polygon is None:
            # A global non-generation rule may describe shared conditioning only.
            # GENERATE always requires a bounded spatial polygon, never a whole-canvas grant.
            if action == "GENERATE":
                raise ContractError(f"GENERATE rule {rule.get('id')} requires an explicit spatial polygon")
            if rule.get("scope") == "global":
                applied_rules.append({"id": rule.get("id"), "action": action, "pixels": w*h})
                continue
            raise ContractError(f"Rule {rule.get('id')} has no resolvable global polygon")
        mask = rasterize_polygon(w, h, polygon)
        # A spatial operator rule may explicitly override the global default.
        # Overlapping explicit rules can only tighten; a child_rule cannot weaken its parent.
        new_rank = -1 if action == "REJECT" else PERMISSION[action]
        first = mask & (~explicit_mask)
        actions[first] = ACTIONS[action]
        decision_rank[first] = new_rank
        overlap_explicit = mask & explicit_mask
        tighten = overlap_explicit & (new_rank < decision_rank)
        actions[tighten] = ACTIONS[action]
        decision_rank[tighten] = new_rank
        explicit_mask[mask] = True
        constraints = rule.get("constraints", {})
        if constraints.get("preserve_silhouette") or constraints.get("preserve_landmarks"):
            geometry_guard[mask] = 1
        rid=rule.get("id") or f"rule_{len(applied_rules)}"
        rule_masks[rid]=mask.astype(np.uint8)
        applied_rules.append({"id": rid, "parent_rule_id": rule.get("parent_rule_id"), "action": action, "pixels": int(mask.sum()),
                              "operator_confirmed": bool(rule.get("operator_confirmed", False)),
                              "constraints": rule.get("constraints", {})})
    # GENERATE pixels can only originate from explicit operator-confirmed spatial rules;
    # default action never creates a generation region by itself.
    from .prompting import build_global_prompt
    if iteration_state:
        if iteration_state.get("schema_version") != "ige-iteration-state/0.1":
            raise ContractError("Unsupported iteration state schema")
        if not iteration_state.get("state_id") or not iteration_state.get("parent_contract_id"):
            raise ContractError("Iteration state must contain state_id and parent_contract_id")
        iteration_number = int(iteration_state.get("iteration", 0))
        if iteration_number < 1:
            raise ContractError("Iteration state iteration must be >= 1")
        inherited_state = {
            "iteration": iteration_number,
            "state_id": iteration_state["state_id"],
            "parent_state_id": iteration_state.get("parent_state_id"),
            "parent_contract_id": iteration_state["parent_contract_id"],
            "previous_status": iteration_state.get("status", "UNKNOWN"),
            "operator_approval_recorded": bool(iteration_state.get("operator_approved", False)),
            "promotion_allowed": False
        }
    else:
        inherited_state = {"iteration": 0, "state_id": None, "parent_state_id": None,
                           "parent_contract_id": None, "previous_status": None,
                           "operator_approval_recorded": False, "promotion_allowed": False}
    contract = {
        "schema_version": "ige-global-logic-contract/0.1",
        "canvas": {"width": w, "height": h, "coordinate_frame": "global_full_frame_px"},
        "source_sha256": source_sha256 or gsrc.get("sha256"),
        "geometry_status": geometry.get("geometry_status", "unknown"),
        "geometry_object_id": geometry.get("object", {}).get("id"),
        "geometry_tolerances": geometry.get("tolerances", {}),
        "geometry_reference": {"bbox_xyxy": geometry.get("object", {}).get("bbox_xyxy"), "landmarks": geometry.get("object", {}).get("landmarks", {})},
        "geometry_operator_confirmation": geometry.get("provenance", {}).get("operator_confirmation", "pending"),
        "source_alignment_status": policy.get("source_alignment_status", "unverified"),
        "policy_id": policy.get("policy_id"),
        "policy_revision": int(policy.get("revision", 1)),
        "default_action": default_action,
        "global_conditioning_prompt": build_global_prompt(policy, geometry),
        "applied_rules": applied_rules,
        "rules_digest": sha256_json({"geometry": geometry, "policy": policy}),
        "state": inherited_state,
        "constraints": {
            "allow_new_semantics_default": bool(policy.get("default_constraints", {}).get("allow_new_semantics", False)),
            "allow_geometry_change_default": bool(policy.get("default_constraints", {}).get("allow_geometry_change", False)),
            "unrecognized_action_fails_closed": True,
            "unknown_region_action": "default_policy_only; no GENERATE without explicit confirmed polygon",
            "provisional_geometry_is_not_operator_lock": geometry.get("geometry_status") != "operator_confirmed"
        },
        "action_counts": {ACTION_NAMES[i]: int((actions == i).sum()) for i in range(4)},
        "geometry_guard_pixels": int(geometry_guard.sum()),
        "reconciliation": policy.get("reconciliation", {}),
        "acceptance": {
            "status": "BLOCKED_PENDING_OBSERVATIONS",
            "requires_operator_geometry_confirmation": geometry.get("geometry_status") != "operator_confirmed",
            "requires_source_coordinate_registration": policy.get("source_alignment_status") != "operator_confirmed",
            "requires_geometry_observations": True
        }
    }
    contract["contract_id"] = sha256_json(contract)[:16]
    return {"contract": contract, "action_map": actions, "geometry_guard": geometry_guard, "rule_masks": rule_masks, "policy": policy}


@dataclass(frozen=True)
class TileBox:
    index: int
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self): return self.right - self.left
    @property
    def height(self): return self.bottom - self.top
    @property
    def center(self): return ((self.left+self.right)/2.0, (self.top+self.bottom)/2.0)

    def to_json(self):
        return {"index": self.index, "position_xyxy": [self.left,self.top,self.right,self.bottom],
                "size": [self.width,self.height], "origin_xy": [self.left,self.top]}


def normalize_ttp_positions(positions: Any, original_size: Any, grid_size: Any, tile_count: int,
                             tile_hw: tuple[int, int]) -> tuple[list[TileBox], tuple[int, int], tuple[int, int]]:
    """Adapter for the actual TTP_Image_Tile_Batch outputs.

    TTP source returns positions as list[(left, upper, right, lower)],
    original_size=(width,height), grid_size=(num_cols,num_rows).
    """
    try:
        ow, oh = map(int, original_size)
        cols, rows = map(int, grid_size)
    except Exception as e:
        raise ContractError(f"TTP metadata must be (width,height)/(cols,rows): {e}")
    if not isinstance(positions, (list, tuple)) or len(positions) != tile_count:
        raise ContractError(f"TTP positions count {len(positions) if hasattr(positions,'__len__') else 'unknown'} != tile batch {tile_count}")
    boxes=[]
    for i, p in enumerate(positions):
        if isinstance(p, dict):
            vals = [p[k] for k in ("left","upper","right","lower")]
        else:
            vals = list(p)
        if len(vals) != 4:
            raise ContractError(f"TTP position[{i}] must have 4 values (left,upper,right,lower)")
        l,t,r,b=map(int, vals)
        if l < 0 or t < 0 or r > ow or b > oh or r <= l or b <= t:
            raise ContractError(f"Invalid TTP position[{i}]={(l,t,r,b)} for canvas {(ow,oh)}")
        if (r-l, b-t) != (tile_hw[1], tile_hw[0]):
            raise ContractError(f"Tile {i} size {(r-l,b-t)} != tile batch size {(tile_hw[1],tile_hw[0])}; variable-size edge tiles not yet supported")
        boxes.append(TileBox(i,l,t,r,b))
    if cols*rows != tile_count:
        raise ContractError(f"grid_size {cols}x{rows} does not equal tile_count {tile_count}")
    return boxes, (ow,oh), (cols,rows)


def project_subsets(compiled: dict, positions: Any, original_size: Any, grid_size: Any,
                    tile_hw: tuple[int,int], tile_count: int) -> dict:
    contract=compiled["contract"]
    action_map=compiled["action_map"]
    guard=compiled["geometry_guard"]
    h,w=action_map.shape
    boxes,(ow,oh),(cols,rows)=normalize_ttp_positions(positions,original_size,grid_size,tile_count,tile_hw)
    if (ow,oh)!=(w,h):
        raise ContractError(f"TTP original_size {(ow,oh)} does not match contract canvas {(w,h)}")
    # Assign an exclusive core owner to each covered pixel using nearest tile center.
    # Pixels still covered by >1 tile are marked overlap and require multi-tile consensus.
    cover=np.zeros((h,w), dtype=np.uint16)
    owner_dist=np.full((h,w), np.inf, dtype=np.float32)
    owner=np.full((h,w), -1, dtype=np.int16)
    for box in boxes:
        sl=np.s_[box.top:box.bottom,box.left:box.right]
        cover[sl]+=1
        yy,xx=np.mgrid[box.top:box.bottom,box.left:box.right]
        cx,cy=box.center
        d=((xx-cx)/max(box.width,1))**2 + ((yy-cy)/max(box.height,1))**2
        cur=owner_dist[sl]
        better=d < cur
        cur[better]=d[better]
        own=owner[sl]
        own[better]=box.index
    from .prompting import build_local_prompt, build_execution_groups
    tiles=[]
    for box in boxes:
        sl=np.s_[box.top:box.bottom,box.left:box.right]
        am=action_map[sl].copy()
        gm=guard[sl].copy()
        own=(owner[sl] == box.index).astype(np.uint8)
        cov=cover[sl]
        overlap=(cov>1).astype(np.uint8)
        rule_ids=[r["id"] for r in contract["applied_rules"] if r["id"] in compiled.get("rule_masks", {}) and compiled["rule_masks"][r["id"]][sl].any()]
        task={
          "schema_version":"ige-tile-subset/0.1", "tile_id":f"tile_{box.index:04d}",
          "tile_index":box.index,"global_contract_id":contract["contract_id"],
          "rules_digest":contract["rules_digest"],"policy_revision":contract["policy_revision"],
          "parent_state":contract["state"],"global_canvas":contract["canvas"],
          "tile":box.to_json(),"rule_ids_inherited":rule_ids,
          "rule_lineage":[{"id":r["id"],"parent_rule_id":r.get("parent_rule_id"),"action":r["action"]} for r in contract["applied_rules"] if r["id"] in rule_ids],
          "action_counts":{ACTION_NAMES[i]:int((am==i).sum()) for i in range(4)},
          "geometry_guard_pixels":int(gm.sum()),
          "core_pixels":int(own.sum()),"overlap_pixels":int(overlap.sum()),
          "write_policy":"single-owner-core; overlap-only-on-consensus; fallback-to-source-on-conflict",
          "geometry_status":contract["geometry_status"],
          "subset_signature":sha256_json({"rule_ids":rule_ids,"action_counts":{ACTION_NAMES[i]:int((am==i).sum()) for i in range(4)},"rules_digest":contract["rules_digest"]})[:16],
          "hard_geometry_enforced_by_diffusion":False
        }
        task["local_prompt"] = build_local_prompt(contract, task, compiled.get("policy", {}))
        tiles.append({"task":task,"action_map":am,"geometry_guard":gm,"core_mask":own,"overlap_mask":overlap})
    exec_groups=build_execution_groups({"contract":contract,"tiles":tiles}, compiled.get("policy", {}))
    return {"contract":contract,"boxes":[b.to_json() for b in boxes],"original_size":[ow,oh],
            "global_action_map":action_map,"global_geometry_guard":guard,
            "grid_size":[cols,rows],"tiles":tiles,"coverage_count":cover,"owner_map":owner,
            "execution_groups":exec_groups}


def make_iteration_feedback(contract: dict, audit_report: dict, operator_feedback: dict | None = None) -> dict:
    """Create next-state proposal; never silently promotes or changes policy."""
    operator_feedback=operator_feedback or {}
    failed=audit_report.get("failed_subsets", [])
    warnings=audit_report.get("warnings", [])
    return {
      "schema_version":"ige-iteration-state/0.1",
      "state_id":sha256_json({"contract_id":contract.get("contract_id"),"audit":audit_report,"feedback":operator_feedback})[:16],
      "parent_contract_id":contract.get("contract_id"),
      "parent_state_id":contract.get("state",{}).get("state_id"),
      "iteration":int(contract.get("state",{}).get("iteration",0))+1,
      "status":"REVIEW_REQUIRED" if failed or warnings else "READY_FOR_OPERATOR_REVIEW",
      "failed_subsets":failed,"warnings":warnings,
      "operator_feedback":operator_feedback,
      "proposed_changes":[],
      "operator_approved":False,
      "automatic_policy_changes":False,
      "geometry_promotion":False,
      "note":"Feedback is recorded as a proposal only. Recompile may inherit this state for lineage, but it never applies policy/geometry changes; operator approval and an explicit new policy/geometry artifact are required."
    }
