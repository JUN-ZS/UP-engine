from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from .core import compile_contract, project_subsets, load_json
from .reconcile import apply_logic_gate,reconcile_tiles
from .audit import audit_candidate
from .ttp import positions_from_ttp_tile_dimensions


def image_to_float(path):
    im=Image.open(path).convert('RGB')
    arr=np.asarray(im,dtype=np.float32)/255.0
    return im,arr


def save_float_image(path,arr):
    a=np.clip(np.asarray(arr),0,1)
    if a.ndim==4: a=a[0]
    Image.fromarray(np.round(a*255).astype(np.uint8)).save(path)


def compile_from_files(source_path,geometry_path,policy_path,positions_path,out_dir,iteration_state_path=None):
    source_im,source=image_to_float(source_path)
    geometry=load_json(Path(geometry_path)); policy=load_json(Path(policy_path))
    iteration_state=load_json(Path(iteration_state_path)) if iteration_state_path else None
    srcsha=hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
    comp=compile_contract(source.shape[:2],geometry,policy,srcsha,iteration_state)
    md=json.loads(Path(positions_path).read_text())
    positions=md['positions']; original_size=md['original_size']; grid_size=md['grid_size']
    tile_hw=tuple(md['tile_hw'])
    subsets=project_subsets(comp,positions,original_size,grid_size,tile_hw,len(positions))
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    Image.fromarray(comp['action_map']).save(out/'global_action_map.png')
    Image.fromarray(comp['geometry_guard']*255).save(out/'global_geometry_guard.png')
    for i,e in enumerate(subsets['tiles']):
        Image.fromarray(e['action_map']).save(out/f'tile_{i:04d}_action_map.png')
        Image.fromarray(e['geometry_guard']*255).save(out/f'tile_{i:04d}_geometry_guard.png')
        Image.fromarray(e['core_mask']*255).save(out/f'tile_{i:04d}_core_mask.png')
        (out/f'tile_{i:04d}_task.json').write_text(json.dumps(e['task'],ensure_ascii=False,indent=2))
    # Persist machine-readable metadata; large arrays are recreated from PNGs on load.
    save={"contract":comp['contract'],"positions":positions,"original_size":original_size,
          "grid_size":grid_size,"tile_hw":tile_hw,"tile_count":len(positions),
          "geometry_guard_pixels":int(comp['geometry_guard'].sum()),
          "action_counts":comp['contract']['action_counts']}
    (out/'compiled_contract.json').write_text(json.dumps(save,ensure_ascii=False,indent=2))
    return save,subsets


def run_reconcile(source_path,geometry_path,policy_path,positions_path,tile_paths,out_dir,observations=None):
    source_im,source=image_to_float(source_path)
    geometry=load_json(Path(geometry_path)); policy=load_json(Path(policy_path))
    md=json.loads(Path(positions_path).read_text())
    srcsha=hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
    comp=compile_contract(source.shape[:2],geometry,policy,srcsha)
    boxes=md['positions']; tile_hw=tuple(md['tile_hw'])
    subsets=project_subsets(comp,boxes,md['original_size'],md['grid_size'],tile_hw,len(boxes))
    ims=[]
    for p in tile_paths:
        im,a=image_to_float(p); ims.append(a)
    # Subset entries carry the canonical TTP box at task.tile.position_xyxy.
    # Reconstruct each source tile from the exact projected global position;
    # do not infer offsets from tile order or assume a fixed grid layout.
    orig_tiles=[]
    for entry in subsets['tiles']:
        box=entry['task']['tile']['position_xyxy']
        left,top,right,bottom=map(int,box)
        orig_tiles.append(source[top:bottom,left:right])
    orig_tiles=np.stack(orig_tiles)
    cand=np.stack(ims)
    gated,gate_report=apply_logic_gate(orig_tiles,cand,subsets)
    merged,rr=reconcile_tiles(source,gated,subsets)
    subsets['reconcile_report']=rr
    audit=audit_candidate(source,merged,subsets,observations or {})
    audit['logic_gate']=gate_report
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    save_float_image(out/'global_reconciled_candidate.png',merged)
    save_float_image(out/'source_reference.png',source)
    (out/'reconcile_report.json').write_text(json.dumps(rr,ensure_ascii=False,indent=2))
    (out/'audit_report.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    return merged,rr,audit
