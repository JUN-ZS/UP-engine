# NCNN full-frame + PBI · 預設省記憶體

**asof 2026-11-02** · 因 warrior 全圖 7168×4032 在「SR 仍在 RAM 再整幅 PBI」時被 OOM kill（exit 137）。

## 預設（不可改成反序當預設）

1. **NCNN tile 升清 → 立刻寫 `*_RAW.png` 落盤** · 釋放 float canvas  
2. **從磁碟讀 RAW** · 按 **BASE 水平 strip**（預設 256px）做 **PBI luma-only**  
3. 寫 `*_PBI.png` · 再出 preview / half JPEG  

```
tools/ncnn_fullframe_pbi.py
  --input  ...
  --out-dir ...
  --param  general_x4v3_ts.ncnn.param
  --bin    general_x4v3_ts.ncnn.bin
```

- `--pbi-mode luma_only`（預設）| `raw_only`  
- `--unsafe-all-in-ram` **會直接拒絕**（防再 OOM）  
- `quality_qualified=false` · `not_siax=true`

## 與 R6c peep 腳本

`work/scripts/r6c_pbi/run_r6c_ncnn.py` 仍是 peep／probe 鏈。  
**全圖**請用本工具；邏輯 review 鏡像：`run_ncnn_fullframe_pbi.py`。
