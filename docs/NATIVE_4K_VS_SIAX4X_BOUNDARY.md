# Native 4K vs 4× Siax — Boundary（研究目標對齊）

| | |
| --- | --- |
| **Status** | `BOUNDARY_LOCKED` |
| **asof** | 2026-11-02 |
| **final_acceptance** | `false` |
| **native_4k_success** | `false`（尚未開驗） |
| **siax_4x_fullframe_observed** | `true`（warrior BASE · 3070 Ti · 見 evidence） |

---

## 0. 一句話

**研究主目標**是：SIAX／SPM 如何協助做出 **原生目標解析度（例如 3840×2160 真 4K 畫布）** 的有效畫面。  
**不能**被「低解像 BASE → 固定 4× ESRGAN 升清」的 Logic-B 式路徑 **取代或冒充**。

```text
Logic B（已有基準）     低解 1792×1008  --4×Siax-->  7168×4032
Native 4K（待做）      直接在 ~3840×2160（或目標畫布）生成／拼細節，不是「先小後放大」
```

---

## 1. 兩種機制（禁止混標）

| | **4× Siax 全圖試跑（現行）** | **原生 4K 路線（研究主線）** |
| --- | --- | --- |
| 輸入 | 已有低／中解 BASE | 目標解析度畫布或分塊原生生成 |
| 模型 | `4x_NMKD-Siax_200k` 固定 **4×** | 生成模 + 約束 + 可選 Siax **細節貢獻** |
| 輸出例 | 1792×1008 → **7168×4032** | **3840×2160**（或書面目標）有效像素 |
| 算不算原生 4K？ | **否** | **是（若通過其驗收）** |
| 角色 | **效能／細節基準**、cell 性價比 | **產品研究主問題** |

**標記規則：**

- 4× 結果 JSON／PNG：**不得**寫 `native_4k=true` / `原生4K成功`
- 原生 4K 實驗：**不得**只交一張 4× 放大圖當完成

---

## 2. 已有 4× 基準（不要當原生 4K）

Package：`warrior_mud_hammer`  
BASE SHA：`cdc2af9738c0ab8d4f121126eeff3dd97959e0b69f486c9242b70d1f52c0e51c` · 1792×1008

| cell | wall_s cold | 輸出 | 證據 |
| --- | ---: | --- | --- |
| 128/8 | 16.531 | 7168×4032 · `72a01792…` | fullframe CUDA pilot |
| 256/16 | 15.631 | 7168×4032 · `58301c0d…` | commercial matrix |
| 256/32 | 26.856 | 7168×4032 · `9e1f7d31…` | commercial matrix |

見：`docs/evidence/S_SPM_HERE_WARRIOR_FULLFRAME_CUDA.json`、`S_SPM_COMMERCIAL_CELL_MATRIX_WARRIOR.json`  
**全部：`native_4k_success=false` · `quality_qualified=false` · `e3_speed_claim=false`**

`.\tools\spm_run_warrior_pilot.ps1` 現在預設 **cell 256/16**（商用候選）；仍是 **4× 路徑**。

---

## 3. 真正的原生 4K 三線（另開實驗 · 不篡改 BASE 4× 包）

| 線 | 名稱 | 要驗證的核心 |
| --- | --- | --- |
| **N1** | **Native Canvas Tiling** | 直接建 **3840×2160**（或目標）畫布；重疊區在**目標解析度**生成細節；不是先出小圖再 4× |
| **N2** | **Local Generative SPM** | 本機生成模做原生尺寸局部生成／補繪；鎖主體、武器、接觸等幾何 |
| **N3** | **Siax Detail Contribution** | Siax 只作**局部材質／高頻**來源（對齊 `SPM_DISTILL_CHARTER` 殘差層方向），**不是**把固定 4× ESRGAN 叫成原生 4K 生成器 |

三線計算機制不同；可對照、**不可**用 4× 分數冒充 N1–N3 通過。

---

## 4. 與 SPM 角色

| 物件 | 在 4× 基準 | 在原生 4K |
| --- | --- | --- |
| SPM-A | 可選事後指紋 | 可量「細節是否真的在目標畫布上」 |
| SPM Distill charter | 未實作 | 與 **N3** 同族（殘差／高頻），**不是** N1 本體 |
| 原生 Siax cell | 4× 熱路徑 | N3 的可能工具之一 |

---

## 5. 建議工作序（不混線）

1. **保留** warrior 4× 為 **Logic-B 基準**（已跑可不再強制重跑）  
2. **新開** `docs`／分支里程碑：`native4k-*`，只做 N1 最小畫布實驗  
3. 驗收口令分開：`SIAX4X_BASELINE_OK` vs `NATIVE_4K_PILOT_OK`  
4. 任何報告標題必須二選一標註機制  

---

## 6. 變更

| 版本 | 日期 | 說明 |
| --- | --- | --- |
| 1.0 | 2026-11-02 | 鎖定：4× 基準 ≠ 原生 4K；三線 N1–N3 |


---

## 7. N1 status

See **[N1_NATIVE_CANVAS_TILING.md](./N1_NATIVE_CANVAS_TILING.md)**.  
Scaffold tools: `tools/n1_plan.py`, `n1_init_canvas.py`, `n1_stitch.py`, `n1_scaffold_smoke.py`.  
Evidence smoke: `docs/evidence/N1_SCAFFOLD_SMOKE.json` · **`native_4k_success=false`**.
