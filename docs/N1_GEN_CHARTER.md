# N1.gen · Real Native Tile Generation（章程）

| | |
| --- | --- |
| **Status** | `CHARTER + dual-tile pilot scaffold` |
| **Depends** | `N1_SCAFFOLD_OK` |
| **native_4k_success** | `false` until full canvas QC |
| **≠** | empty canvas · Lanczos structure · 4× Siax · 45 independent AI jobs |

---

## 0. 一句話

N1 地基已有；**N1.gen** 要讓 AI 在 **3840×2160 目標座標** 上**真正生成**內容。  
**禁止**一開始跑滿 45 格互不相關生圖。  
**第一個有價值的實驗：兩格相鄰 + 全局參考 + seam 檢查。**

---

## 1. 為何不能「45 次獨立生圖」

戰錘／雙手／身體跨格時，若 A/B/C 各自生成：

- 槌柄接不上  
- 手勢／盔甲花紋漂移  
- 場景光照不一致  

**Overlap  alone 不夠** → 需要 **全局場景記憶 + 局部座標 + 鄰格約束（日後閉環）**。

---

## 2. 第一個 pilot（強制最小範圍）

| 條件 | 要求 |
| --- | --- |
| 全局參考 | Warrior BASE（`cdc2af97…`）或 `canvas_struct` 僅作 layout 提示 |
| 目標畫布 | 3840×2160 |
| 生成區域 | **兩個相鄰** 512px tiles（含 64px overlap） |
| 座標 | 來自 `plan.json` 的 **目標畫布** box |
| 輸出 | 兩張**真生成** tile PNG（尺寸必須 = box） |
| 拼接 | `n1_stitch --require-tiles idA,idB` · **fail-closed** |
| 驗收拆分 | 見 §4 |

**不**要求一次填滿 45 格。  
**不**把 dual-tile 成功標成 `NATIVE_4K_PILOT_OK`。

---

## 3. 每格生成時必須知道的上下文（契約）

每格 job 至少帶：

1. **global_ref**：整圖構圖參考（BASE 或 structure canvas）  
2. **tile_id / box / core** 在 3840×2160 上的座標  
3. **neighbor_ids** 與 overlap 幾何  
4. **scene_lock 文字／prompt**：人物、戰錘、接觸關係（不變項）  
5. **output 契約**：像素尺寸 = (x1-x0, y1-y0)，否則 stitch **拒絕**（默認不 resize）

日後（非 v0）：鄰格已生成結果作 **continuation ref**（閉環修正）。

---

## 4. 標籤（必須分開）

| 標籤 | 含義 |
| --- | --- |
| **N1_GEN_PILOT_OK** | 至少兩相鄰格 **真生成** 完成且尺寸／SHA 收據齊 |
| **N1_SEAM_CONTINUITY_OK** | 拼接後相鄰 seam 人眼／指標可接受（單獨驗） |
| **NATIVE_4K_PILOT_OK** | 完整畫布產品級驗收（遠後） |
| N1_SCAFFOLD_OK | 僅帳本／空畫布／合成色塊（**已達成**） |

---

## 5. stitch fail-closed（已實作 v1.1）

- 缺格 → **不**當 complete；默認不寫「成功」退出  
- 尺寸錯 → **默認拒絕**（`--allow-resize` 僅 debug）  
- `--allow-partial` 僅 debug  
- 子集拼接：`--require-tiles a,b` 只要求這兩格齊

---

## 6. 非目標

| ❌ |
| --- |
| 重跑 Siax 4× 當 N1.gen |
| 再優化空畫布／格數計算 |
| 45 格並行無關生圖當里程碑 |
| CI 缺 pytest 當成 N1 通過 |

---

## 7. CLI（pilot）

```powershell
# 選兩相鄰格（例：從 plan 取水平相鄰）
python tools/n1_gen_dual_pilot.py --plan runs/n1/plan.json --list-pairs
python tools/n1_gen_dual_pilot.py --plan runs/n1/plan.json --pair 0 `
  --global-ref packages/spm_here/warrior_mud_hammer/warrior_BASE.jpg `
  --out-dir runs/n1/gen_dual

# 生成器後端就緒後填 tiles，再：
python tools/n1_stitch.py --plan runs/n1/plan.json `
  --tiles-dir runs/n1/gen_dual/tiles `
  --require-tiles <idA>,<idB> `
  --out runs/n1/gen_dual/OUT_DUAL.png
```

**v0 dual pilot tool** 產出 **job JSON + 裁切 global_ref 到 tile 窗作 ref 圖**；  
**真正 AI 填色** 接 Imagine／本機生成 API 後才標 `N1_GEN_PILOT_OK`。
