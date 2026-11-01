#!/usr/bin/env python3
"""RF context sweep with one subprocess per margin (OOM-safe on 1.9Gi)."""
from __future__ import annotations
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

CHILD = r'''
import json,sys,os
os.environ.setdefault("OMP_NUM_THREADS","1")
os.environ.setdefault("MKL_NUM_THREADS","1")
os.environ.setdefault("TORCH_NUM_THREADS","1")
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
import torch
from spandrel import ImageModelDescriptor, ModelLoader
from ige.upscale.siax import MODEL_SHA256, file_sha256
ckpt, base_path, x0,y0,x1,y1, margin, out_png = sys.argv[1:9]
x0,y0,x1,y1,margin=map(int,(x0,y0,x1,y1,margin))
torch.set_num_threads(1)
assert file_sha256(ckpt)==MODEL_SHA256
with Image.open(base_path) as im:
    base=np.asarray(ImageOps.exif_transpose(im).convert("RGB"),dtype=np.uint8)
H,W,_=base.shape
ex0,ey0=max(0,x0-margin),max(0,y0-margin)
ex1,ey1=min(W,x1+margin),min(H,y1+margin)
crop=base[ey0:ey1,ex0:ex1].astype(np.float32)/255.0
t=torch.from_numpy(crop).permute(2,0,1).unsqueeze(0)
d=ModelLoader(device="cpu").load_from_file(ckpt)
assert isinstance(d, ImageModelDescriptor)
d.eval()
with torch.inference_mode():
    o=d(t).float().cpu()[0].permute(1,2,0).numpy()
u8=np.clip(o*255+0.5,0,255).astype(np.uint8)
left=(x0-ex0)*4; top=(y0-ey0)*4
core=u8[top:top+(y1-y0)*4, left:left+(x1-x0)*4]
Image.fromarray(core).save(out_png)
print(json.dumps({"ok":True,"input_wh":[ex1-ex0,ey1-ey0],"core_shape":list(core.shape)}))
'''

def run_margin(ckpt, base, box, margin, out_png, env):
    x0,y0,x1,y1=box
    p=subprocess.run(
        [sys.executable,"-c",CHILD,str(ckpt),str(base),str(x0),str(y0),str(x1),str(y1),str(margin),str(out_png)],
        capture_output=True,text=True,env=env,cwd=str(Path(__file__).resolve().parents[1]),
    )
    if p.returncode!=0:
        return {"ok":False,"margin":margin,"returncode":p.returncode,"stderr":(p.stderr or "")[-400:]}
    lines=[ln for ln in p.stdout.splitlines() if ln.strip()]
    meta=json.loads(lines[-1])
    meta.update({"ok":True,"margin":margin,"out":str(out_png)})
    return meta

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--core", type=int, default=64)
    ap.add_argument("--margins", default="0,8,16,24,32,40,48")
    ap.add_argument("--ref-margin", type=int, default=48)
    args=ap.parse_args()
    margins=sorted(set(int(x) for x in args.margins.split(",")))
    if args.ref_margin not in margins:
        margins.append(args.ref_margin)
        margins=sorted(margins)

    with Image.open(args.base) as im:
        base=ImageOps.exif_transpose(im).convert("RGB")
    W,H=base.size
    C=args.core
    # single center
    cx,cy=W//2,H//2
    x0=max(args.ref_margin, min(W-C-args.ref_margin, cx-C//2))
    y0=max(args.ref_margin, min(H-C-args.ref_margin, cy-C//2))
    box=(x0,y0,x0+C,y0+C)

    work=Path("runs/siax_validation_r2/S2_1/p1/rf_cores")
    work.mkdir(parents=True, exist_ok=True)
    env=os.environ.copy()
    env["PYTHONPATH"]=str(Path(__file__).resolve().parents[1]/"src")
    env["OMP_NUM_THREADS"]=env["MKL_NUM_THREADS"]=env["TORCH_NUM_THREADS"]="1"
    env["LD_LIBRARY_PATH"]=os.environ.get("LD_LIBRARY_PATH","")

    results={}
    for m in margins:
        outp=work/f"core_m{m:02d}.png"
        print(f"margin {m} ...", flush=True)
        results[m]=run_margin(args.checkpoint, args.base, box, m, outp, env)
        print(results[m], flush=True)
        if not results[m].get("ok"):
            continue

    ref_path=work/f"core_m{args.ref_margin:02d}.png"
    if not ref_path.is_file():
        raise SystemExit("ref core missing")
    ref=np.asarray(Image.open(ref_path),dtype=np.uint8)
    rows=[]
    for m in margins:
        if not results[m].get("ok"):
            rows.append({"margin":m,"ok":False,"status":results[m]})
            continue
        core=np.asarray(Image.open(results[m]["out"]),dtype=np.uint8)
        mae=float(np.mean(np.abs(core.astype(np.int16)-ref.astype(np.int16))))
        bh=min(8, core.shape[0]//4)
        border=float(np.mean(np.abs(np.concatenate([
            (core[:bh]-ref[:bh]).ravel(),
            (core[-bh:]-ref[-bh:]).ravel(),
            (core[:,:bh]-ref[:,:bh]).ravel(),
            (core[:,-bh:]-ref[:,-bh:]).ravel(),
        ]).astype(np.int16))))
        inner=float(np.mean(np.abs(core[bh:-bh,bh:-bh].astype(np.int16)-ref[bh:-bh,bh:-bh].astype(np.int16)))) if core.shape[0]>2*bh else mae
        rows.append({"margin":m,"ok":True,"mae_vs_ref":mae,"border_mae":border,"inner_mae":inner,"input_wh":results[m].get("input_wh")})

    # recommend
    rec=None
    finite=[r for r in rows if r.get("ok") and r["margin"]<args.ref_margin]
    min_mae=min((r["mae_vs_ref"] for r in finite), default=9e9)
    for r in finite:
        if r["mae_vs_ref"]<=max(0.35, min_mae*1.15) and r["inner_mae"]<=max(0.35, min_mae*1.15):
            rec=r["margin"]; break
    if rec is None:
        for r in finite:
            if r["mae_vs_ref"]<1.0:
                rec=r["margin"]; break

    report={
        "program":"SIAX_S2_1_P1_RF_MEASURE_SUB",
        "final_acceptance":False,
        "core":C,
        "box":list(box),
        "ref_margin":args.ref_margin,
        "rows":rows,
        "recommended_compute_context":rec,
        "evidence_grade":"OBSERVED",
        "method":"subprocess per margin; single center; MAE vs max-margin core",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"recommended_compute_context":rec,"rows":rows},indent=2))

if __name__=="__main__":
    main()
