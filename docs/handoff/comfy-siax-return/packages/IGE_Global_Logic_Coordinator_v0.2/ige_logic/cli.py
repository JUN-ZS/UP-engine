from __future__ import annotations
import argparse,json
from pathlib import Path
from PIL import Image
import numpy as np
from .core import load_json,compile_contract,project_subsets,make_iteration_feedback
from .ttp import positions_from_ttp_tile_dimensions
from .io import image_to_float,save_float_image,run_reconcile
from .coordinator import summarize_subset_compatibility,write_iteration_state


def main():
    p=argparse.ArgumentParser(description='IGE Global Logic Coordinator')
    sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('emit-ttp-metadata',help='Offline TTP-compatible position fixture builder')
    a.add_argument('--width',type=int,required=True); a.add_argument('--height',type=int,required=True)
    a.add_argument('--tile-width',type=int,required=True); a.add_argument('--tile-height',type=int,required=True)
    a.add_argument('--out',required=True)
    c=sub.add_parser('compile',help='Compile global rules and project them to actual TTP tile metadata')
    c.add_argument('--source',required=True);c.add_argument('--geometry',required=True);c.add_argument('--policy',required=True)
    c.add_argument('--positions',required=True);c.add_argument('--out-dir',required=True);c.add_argument('--state',default=None)
    c2=sub.add_parser('reconcile',help='Logic-gated, overlap-consensus tile reconstruction')
    c2.add_argument('--source',required=True);c2.add_argument('--geometry',required=True);c2.add_argument('--policy',required=True)
    c2.add_argument('--positions',required=True);c2.add_argument('--tiles',nargs='+',required=True);c2.add_argument('--out-dir',required=True)
    c3=sub.add_parser('state',help='Write next iteration feedback without promoting rules')
    c3.add_argument('--contract',required=True);c3.add_argument('--audit',required=True);c3.add_argument('--out',required=True)
    args=p.parse_args()
    if args.cmd=='emit-ttp-metadata':
        pos,grid=positions_from_ttp_tile_dimensions(args.width,args.height,args.tile_width,args.tile_height)
        obj={'positions':pos,'original_size':[args.width,args.height],'grid_size':grid,'tile_hw':[args.tile_height,args.tile_width]}
        Path(args.out).write_text(json.dumps(obj,indent=2))
        print(json.dumps({'status':'PASS','tile_count':len(pos),'grid_size':grid,'out':args.out},indent=2));return
    if args.cmd=='compile':
        from .io import compile_from_files
        saved,subs=compile_from_files(args.source,args.geometry,args.policy,args.positions,args.out_dir,args.state)
        compat=summarize_subset_compatibility(subs)
        Path(args.out_dir,'subset_compatibility.json').write_text(json.dumps(compat,indent=2))
        print(json.dumps({'status':'PASS_COMPILE_ONLY','contract_id':saved['contract']['contract_id'],'tile_count':saved['tile_count'],'action_counts':saved['action_counts'],'note':'No diffusion/GPU inference executed.'},indent=2));return
    if args.cmd=='reconcile':
        _,rr,audit=run_reconcile(args.source,args.geometry,args.policy,args.positions,args.tiles,args.out_dir)
        print(json.dumps({'reconcile':rr,'audit_status':audit['status'],'warnings':audit['warnings'],'violations':audit['violations']},indent=2));return
    if args.cmd=='state':
        contract=load_json(Path(args.contract)); audit=load_json(Path(args.audit))
        if isinstance(contract, dict) and "contract" in contract:
            contract = contract["contract"]
        state=write_iteration_state(contract,audit,args.out)
        print(json.dumps(state,indent=2));return

if __name__=='__main__': main()
