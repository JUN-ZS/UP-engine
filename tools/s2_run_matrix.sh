#!/usr/bin/env bash
# S2 tile/halo matrix runner — single-process reference per cell + SPM-approx diag
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 TORCH_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2

BASE=runs/fair_e283/BASE.jpg
CKPT=models/4x_NMKD-Siax_200k.pth
ROOT=runs/siax_validation_r2/S2
MASTER_128_8=runs/siax_validation_r2/S1C/r1_single/OUT.png
MASTER_SHA=3289e3e02928ac688002adc621124ac73d3730f67a5a0d0a5cabe351a6cfd181

mkdir -p "$ROOT"

run_cell() {
  local ts=$1 tp=$2
  local cell="${ts}x${tp}"
  local dir="$ROOT/${ts}_${tp}"
  mkdir -p "$dir"
  local out="$dir/OUT.png"
  local report="$dir/run.json"
  local diag="$dir/spm_diag.json"

  echo "=== S2 cell $cell ==="
  if [[ "$ts" == "128" && "$tp" == "8" && -f "$MASTER_128_8" ]]; then
    # reuse proven master
    cp -f "$MASTER_128_8" "$out"
    cp -f "${MASTER_128_8%.png}.upscale.json" "$dir/OUT.upscale.json" 2>/dev/null || true
    python3 - <<PY
import json, time, hashlib
from pathlib import Path
p=Path("$out")
h=hashlib.sha256(p.read_bytes()).hexdigest()
rec={
  "cell":"$cell","tile_size":$ts,"tile_pad":$tp,
  "mode":"reuse_S1C_r1_single_master",
  "wall_s":0.0,
  "output_sha256":h,
  "match_r1_master": h=="$MASTER_SHA",
  "output":str(p),
}
Path("$report").write_text(json.dumps(rec,indent=2)+"\n")
print(json.dumps(rec,indent=2))
PY
  else
    t0=$(date +%s.%N)
    # taskset full 2 cores for fair single-process quality ref
    taskset -c 0,1 python3 -m ige.cli upscale-siax "$BASE" \
      --checkpoint "$CKPT" \
      --out "$out" \
      --tile-size "$ts" --tile-pad "$tp" \
      --device cpu \
      --confirm-model-license-review
    t1=$(date +%s.%N)
    python3 - <<PY
import json, hashlib
from pathlib import Path
p=Path("$out")
h=hashlib.sha256(p.read_bytes()).hexdigest()
side=p.with_suffix('.upscale.json')
meta=json.loads(side.read_text()) if side.is_file() else {}
rec={
  "cell":"$cell","tile_size":$ts,"tile_pad":$tp,
  "mode":"single_process_upscale_siax",
  "wall_s": round(float("$t1")-float("$t0"),3),
  "output_sha256":h,
  "match_r1_master_128_8": h=="$MASTER_SHA",
  "runtime_meta": meta.get("runtime"),
  "output":str(p.resolve()),
}
Path("$report").write_text(json.dumps(rec,indent=2)+"\n")
print(json.dumps(rec,indent=2))
PY
  fi

  python3 tools/s2_spm_diag.py --image "$out" --tile-size "$ts" --tile-pad "$tp" --out "$diag" > "$dir/spm_diag.stdout.json"
  echo "DONE $cell"
}

# order: baseline first (reuse), then more context, then larger tiles
run_cell 128 8
run_cell 128 16
run_cell 256 16
run_cell 256 32

echo S2_MATRIX_INFERENCE_DONE
