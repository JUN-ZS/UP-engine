# 技法 · 大大清（DA_DA_QING）

**asof:** `2026-10-31T22:50:28Z`  
**status:** `TECHNIQUE_RECORDED_SUCCESS_PARTIAL`  
**final_acceptance:** `false`（硬規則 · 未 human gold）

## 一句話

**大大清** = 真 **Siax 4×**（釘死權重 + SHA）→ **DETAIL6 區域 residual**（face/skin/eye_white 保護 + metal 細節）→ q98/q100 交付。  
成功指 **技術鏈 execution_complete**；**不是** 創作全鏈完成，**不是** final_acceptance。

## 成功案例（本輪）

| 步 | 內容 | 結果 |
| --- | --- | --- |
| 0 | HERE 原生 `83fd0872…` 雨中狠打 1792×1008 | 候選 master |
| 1 | Siax `4x_NMKD-Siax_200k` → 7168×4032 · ~43MB PNG | **成功** · asset `b5d3864d…` |
| 2 | DETAIL6 metal residual · protect face/skin/eye | **execution_complete=true** · q100 ~29.5MB |

### 關鍵閘（step2）

```json
{
  "exact_4x": true,
  "protected_pixels_preserved_on_png": true,
  "minimum_delivery_bytes": true
}
```

### 像素 audit

```json
{
  "changed_outside_effective_detail_mask": 0,
  "changed_inside_protected_masks": 0
}
```

### metal HF（診斷 only）

```json
{
  "metal": {
    "hf_before": 2.424393,
    "hf_after": 2.752565,
    "hf_delta": 0.328172
  }
}
```

## 食譜（可重跑）

1. HERE 鎖 a8b 原生 still（16:9）
2. 下載 `4x_NMKD-Siax_200k.pth`，SHA = `560424d9…fd127e`
3. `ige upscale-siax … --confirm-model-license-review`；若 OOM → 同權重分塊 mem-efficient
4. `masks.json` v1.0：protect face/skin/eye_white + detail metal（或 stone/text/fire）
5. `ige detail6` 或 strip-mmap residual · gain≈0.15
6. 出 `DETAIL6_WORKING.png` + q98/q100 · 寫 REPORT
7. **停** 在 `HUMAN_GOLD_PENDING` · **禁止** 自證 final_acceptance

## 明確不宣稱

- human gold mask / 身份 / 觀感
- GRID_CLEAN · BEAT · PATH1E 全棧
- PRE/MID/POST 同鏡認證
- 幾何 / H2 contact
- 與 LANCZOS 假升清等同

## 引擎邊界

- Repo: `JUN-ZS/UP-engine`
- Branch: `feat/ref-skill-router-detail6-v0.1` @ `8d5cee93…`
- PR: [#5](https://github.com/JUN-ZS/UP-engine/pull/5) draft · **未 merge main**

## 檔案

- 技法 JSON: `docs/TECHNIQUE_DA_DA_QING.json`
- Siax hub: https://grok.com/imagine/post/b5d3864d-ee46-487a-9afe-6053d6f58ba8?source=agent
- DETAIL6 q100 hub: https://grok.com/imagine/post/a7e53a77-ecda-4dda-bb7a-78cb8c7c871c?source=agent

## 別名

`大大清` · `DA_DA_QING` · `DaDaQing` · `Siax+DETAIL6 delivery`


---

## 架構修正對齊（2026-10-31T22:53:43Z）

三層不可混：

| 層 | 是什麼 | 大大清裡對應 |
| --- | --- | --- |
| L1 升清機制 | SR / re-detail family | CNN/GAN SR + ROI residual |
| L2 執行模型 | checkpoint / generator | Siax 4x_NMKD + DETAIL6 runner |
| L3 品質策略 | 身份／mask／閘 | face/skin/eye protect · final_acceptance=false |

**三路 HERE 升清** = 同一大類 `NATIVE_GENERATIVE_REDETAIL`（+ hybrid ROI），**唔係** 三種獨立超解像。

**12 方法家族** = 策略規劃範圍（`strategy_portfolio` @ HEAD `4474415`），**唔係** 12 個已安裝執行器。

大大清 = 已驗證嘅 **可執行組合**（Siax+DETAIL6 partial），**唔** 代表 portfolio 全通。
