# NFE MIX ALL · 一鍵混試

把既有資源混進 **同一條 NFE 一鍵**，不混淆「生成 G」與「驗收／補播」。

## 混入的來源

| 來源 | 角色 |
|------|------|
| NFE C0–C0.4 | TemporalState · Motion · I2I G · Accept/Reject |
| STICK | 進化下一幀 prompt 附件 |
| DDXX 圖方法（GT anchors / sim vs homo residual） | **C0.3.1** 相鄰幀靜態相機閘 |
| Continuous frame + multi-grid verify 圖 | frontier/MAE 趨勢序列 |
| FRAMEBACK | 相鄰靜圖光流中間幀 · **只補播** |
| still_sequence / f2f_verify | C1–C5 組片與 F2F 量測 |

## 禁止當 G

- I2V / image_to_video
- 光流 morph 當 next-frame 生成
- 空間 EXTEND 當時間 NEXT FRAME

## CLI

```bash
# 新 job
python tools/nfe_one_click.py --master F0.png --job-id mix1 --out-dir runs/nfe/mix1 --mix-all

# 已有 accepted 鏈（如 c60）只跑 MIX
python tools/nfe_one_click.py --mix-only --job-dir runs/nfe/nfe_p0_c60_x30 --frameback 1 --out-dir runs/nfe/nfe_p0_c60_x30

# 純 MIX 工具
python tools/nfe_mix_verify.py --job-dir runs/nfe/nfe_p0_c60_x30 --out-dir runs/nfe/mix_c60 --frameback 1 --encode
```

## 輸出

- `mix/DDXX_CHAIN.json` — 相鄰 DDXX 閘
- `mix/MIX_VERIFY_RESULT.json` — 總表 + frontier 序列
- `mix/frameback_m*/` — 補播幀 + mp4
- `ONE_CLICK_RESULT.json` flags.mix_all

`quality_qualified=false` · `final_acceptance=false` · `cinematic_product=false`
