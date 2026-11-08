from __future__ import annotations

from typing import Any
import numpy as np
from .core import ACTIONS, ACTION_NAMES, ContractError


def apply_logic_gate(original_tiles: np.ndarray, refined_tiles: np.ndarray, subsets: dict) -> tuple[np.ndarray, dict]:
    """Restore source pixels in PRESERVE/REJECT zones; leave REFINE/GENERATE candidates intact.

    Arrays are BHWC float images in [0,1]. Geometry is not inferred from RGB values here.
    """
    src=np.asarray(original_tiles, dtype=np.float32)
    gen=np.asarray(refined_tiles, dtype=np.float32)
    if src.shape != gen.shape:
        raise ContractError(f"Original/refined tile shape mismatch: {src.shape} vs {gen.shape}")
    if src.ndim != 4 or src.shape[-1] not in (3,4):
        raise ContractError(f"Expected BHWC IMAGE batch, got {src.shape}")
    if src.shape[0] != len(subsets["tiles"]):
        raise ContractError("Tile batch count does not match projected subset count")
    out=gen.copy()
    restored=0
    counts={k:0 for k in ACTIONS}
    for i,entry in enumerate(subsets["tiles"]):
        action=entry["action_map"]
        if action.shape != src[i].shape[:2]:
            raise ContractError(f"Action map size for tile {i} does not match tile IMAGE")
        blocked=np.isin(action, [ACTIONS["PRESERVE"], ACTIONS["REJECT"]])
        out[i][blocked]=src[i][blocked]
        restored += int(blocked.sum())
        for name,value in ACTIONS.items():
            counts[name] += int((action==value).sum())
    return np.clip(out,0,1), {"blocked_source_pixels_restored":restored,"tile_action_pixels":counts,
                             "geometry_enforced_by_pixel_gate":False}


def reconcile_tiles(source: np.ndarray, candidate_tiles: np.ndarray, subsets: dict,
                    mean_abs_threshold: float | None = None,
                    p95_abs_threshold: float | None = None) -> tuple[np.ndarray, dict]:
    """Reconcile TTP tile outputs against their global coordinate map.

    - Non-overlap pixels: use the single covering tile if action permits.
    - Overlap pixels: average only where all candidate tiles agree; otherwise abstain to source.
    - PRESERVE/REJECT always fall back to the source.
    - Pixels outside all TTP tiles remain byte/value-identical to source.
    """
    src=np.asarray(source, dtype=np.float32)
    tiles=np.asarray(candidate_tiles, dtype=np.float32)
    if src.ndim == 4:
        if src.shape[0] != 1: raise ContractError("source_image must be a single full-frame image")
        src=src[0]
    if src.ndim != 3 or src.shape[-1] not in (3,4):
        raise ContractError(f"Expected source HWC, got {src.shape}")
    h,w,c=src.shape
    if tiles.ndim != 4 or tiles.shape[0] != len(subsets["tiles"]):
        raise ContractError(f"Candidate tile batch does not match subset list: {tiles.shape}")
    contract=subsets["contract"]
    recon_cfg=contract.get("reconciliation",{})
    threshold=float(mean_abs_threshold if mean_abs_threshold is not None else recon_cfg.get("overlap_mean_abs_difference_threshold",0.05))
    p95_threshold=float(p95_abs_threshold if p95_abs_threshold is not None else recon_cfg.get("overlap_p95_abs_difference_threshold",0.20))
    if (w,h) != tuple(subsets["original_size"]):
        raise ContractError(f"source canvas {(w,h)} != TTP ORIGINAL_SIZE {subsets['original_size']}")
    action_map=np.full((h,w),ACTIONS["PRESERVE"],dtype=np.uint8)
    # contract maps are retained in projected subset object as global arrays.
    if "global_action_map" in subsets:
        action_map=subsets["global_action_map"]
    else:
        # Rebuild from tile-local maps; overlapping pixels must agree on policy.
        best=np.full((h,w),255,dtype=np.uint8)
        for entry,box in zip(subsets["tiles"],subsets["boxes"]):
            l,t,r,b=box["position_xyxy"]
            am=entry["action_map"]
            patch=best[t:b,l:r]
            # Restrictive order is implemented by precedence below.
            rank={ACTIONS['REJECT']:0,ACTIONS['PRESERVE']:1,ACTIONS['REFINE']:2,ACTIONS['GENERATE']:3}
            # assign restrictive where each local map overlaps
            for val in np.unique(am):
                patch[am==val]=np.minimum(patch[am==val],rank[int(val)])
        inverse={0:ACTIONS['REJECT'],1:ACTIONS['PRESERVE'],2:ACTIONS['REFINE'],3:ACTIONS['GENERATE']}
        for rnk,val in inverse.items(): action_map[best==rnk]=val
    sum_canvas=np.zeros((h,w,c),dtype=np.float64)
    min_canvas=np.full((h,w,c),np.inf,dtype=np.float32)
    max_canvas=np.full((h,w,c),-np.inf,dtype=np.float32)
    cover=np.zeros((h,w),dtype=np.uint16)
    for i,box in enumerate(subsets["boxes"]):
        l,t,r,b=box["position_xyxy"]
        patch=tiles[i]
        if patch.shape[:2] != (b-t,r-l):
            raise ContractError(f"Candidate tile {i} shape {patch.shape[:2]} != position size {(b-t,r-l)}")
        sl=np.s_[t:b,l:r]
        sum_canvas[sl]+=patch
        min_canvas[sl]=np.minimum(min_canvas[sl],patch)
        max_canvas[sl]=np.maximum(max_canvas[sl],patch)
        cover[sl]+=1
    covered=cover>0
    overlap=cover>1
    mean=np.zeros_like(src,dtype=np.float32)
    mean[covered]=(sum_canvas[covered]/cover[covered,None]).astype(np.float32)
    spread=np.zeros((h,w),dtype=np.float32)
    if overlap.any():
        spread[overlap]=np.mean(max_canvas[overlap]-min_canvas[overlap],axis=-1)
    agree=overlap & (spread<=threshold)
    conflict=overlap & ~agree
    output=src.copy()
    # Single tile pixels use that tile candidate. Multi-tile pixels require consensus.
    single=cover==1
    output[single]=mean[single]
    output[agree]=mean[agree]
    # Overlap conflict and blocked action classes abstain to original.
    blocked=np.isin(action_map,[ACTIONS['PRESERVE'],ACTIONS['REJECT']])
    output[blocked]=src[blocked]
    # Any area outside tile coverage also remains source.
    output[~covered]=src[~covered]
    ov_vals=spread[overlap]
    conflict_fraction=float(conflict.sum()/max(int(overlap.sum()),1))
    max_conflict_fraction=float(recon_cfg.get("maximum_overlap_conflict_fraction",0.05))
    # Attribute every overlap conflict to each participating TTP subset.
    # A conflict shared by N tiles is visible in all N tile diagnostics; this is
    # intentional because each participant must be considered during retry planning.
    subset_diagnostics=[]
    failed_subsets=[]
    for i,box in enumerate(subsets["boxes"]):
        l,t,r,b=box["position_xyxy"]
        local_overlap=overlap[t:b,l:r]
        local_conflict=conflict[t:b,l:r]
        n_overlap=int(local_overlap.sum())
        n_conflict=int(local_conflict.sum())
        frac=float(n_conflict/max(n_overlap,1))
        passed=bool(n_overlap==0 or frac<=max_conflict_fraction)
        tile_id=f"tile_{i:04d}"
        diag={
          "tile_id":tile_id,"tile_index":i,
          "position_xyxy":[l,t,r,b],
          "overlap_pixels":n_overlap,
          "overlap_conflict_pixels":n_conflict,
          "overlap_conflict_fraction":frac if n_overlap else 0.0,
          "overlap_conflict_fraction_limit":max_conflict_fraction,
          "overlap_pass":passed,
          "failure_reasons":[] if passed else ["tile_overlap_conflict_fraction_above_configured_limit"]
        }
        subset_diagnostics.append(diag)
        if not passed:
            failed_subsets.append({"tile_id":tile_id,"tile_index":i,
                                   "reasons":diag["failure_reasons"],
                                   "overlap_conflict_fraction":frac})
    report={
      "status":"RECONCILED_WITH_ABSTENTION",
      "canvas_wh":[w,h],"tile_count":int(tiles.shape[0]),
      "covered_pixels":int(covered.sum()),"uncovered_pixels":int((~covered).sum()),
      "overlap_pixels":int(overlap.sum()),"overlap_agreement_pixels":int(agree.sum()),
      "overlap_conflict_pixels":int(conflict.sum()),"overlap_conflict_fraction":conflict_fraction,
      "overlap_mean_spread":float(ov_vals.mean()) if ov_vals.size else 0.0,
      "overlap_p95_spread":float(np.percentile(ov_vals,95)) if ov_vals.size else 0.0,
      "overlap_mean_threshold":threshold,"overlap_p95_threshold":p95_threshold,
      "maximum_overlap_conflict_fraction":max_conflict_fraction,
      "subset_overlap_diagnostics":subset_diagnostics,
      "failed_subsets":failed_subsets,
      "fallback_to_source_on_conflict":True,
      "blocked_action_pixels_restored":int(blocked.sum()),
      "outside_tile_coverage_changed_pixels":0,
      "notes":["Overlap pixels are written only when all overlapping tile candidates agree within threshold.",
               "Conflicting overlap pixels revert to the source, not a feather blend.",
               "This is a consistency gate, not a semantic/identity detector."]
    }
    report["overlap_p95_threshold_pass"] = report["overlap_p95_spread"] <= p95_threshold
    report["overlap_conflict_fraction_pass"] = conflict_fraction <= max_conflict_fraction
    report["overlap_consensus_pass"] = bool(report["overlap_p95_threshold_pass"] and report["overlap_conflict_fraction_pass"])
    return np.clip(output,0,1),report
