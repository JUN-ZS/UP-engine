# SPM Distill Charter（一頁定界）

| | |
| --- | --- |
| **Status** | `CHARTER_ONLY` · 無訓練碼 · 無模型權重交付 |
| **asof** | 2026-11-02 |
| **Branch surface** | `feat/upscale-s3-heterogeneous-runner-v0.1`（文件可跟主線；**不**併入 S2.1 品質決定） |
| **final_acceptance** | `false` |
| **quality_qualified** | `false` |
| **e3_speed_claim** | `false` |

---

## 0. 一句話

**SPM Distill** 若開做，目標是：在**鎖定結構底圖**之上，學習／推一個**只負責高頻／殘差（細節感）**的輕量層；  
**現有 SPM-A** 只負責**量測指紋**，**不是** distill，也**尚未**逼 Siax 變成「只做噪點」的學生模。

```text
[底：結構／粗 4×]  +  [殘差層：高頻／局部細節]  =  合成輸出
        ↑                      ↑
   非 Siax 全模重畫      未來 distill 的對象（若開）
```

---

## 1. 範圍（In scope · 若開階段）

僅當**另開隔離分支／里程碑**且書面批准後，下列才算「SPM Distill 工作」：

| ID | 範圍 | 說明 |
| --- | --- | --- |
| D1 | **殘差定義** | 教師 = 凍結全模 Siax（同 checkpoint SHA）輸出；底 = 明示的一種（預設 Lanczos 4× 或書面指定的輕量 4×）；殘差 = 教師 − 底（空間／色彩域書面固定） |
| D2 | **探針監督面** | 沿用或擴充**固定 48×64 SPM-A bank**（或後代 bank SHA 鎖定）作 **train/val 窗**，不拿全圖當唯一 loss |
| D3 | **學生契約** | 學生只預測殘差（或高頻帶）；**禁止**默認整圖 RGB 重建當唯一目標（除非 charter 修訂） |
| D4 | **合成契約** | `out = clamp(base + student_residual)`（或書面定義的頻域合成）；輸出須可重算 SHA |
| D5 | **對照義務** | 同 BASE：全模 Siax vs 底 alone vs 底+學生；報 wall_s、VRAM、SPM-A delta、seam 抽樣；**不**自動 quality PASS |
| D6 | **授權／權重** | 教師 Siax 條款、學生權重授權、HF 鏡像 vs 上游，**用戶書面確認**後才可訓練或公開權重 |

**本 charter 本身不啟動 D1–D6 實作。**

---

## 2. 非目標（Out of scope · 明確不做／不算 SPM Distill）

| 非目標 | 說明 |
| --- | --- |
| ❌ 把現有 SPM-A 重命名成 Distill | 名稱汙染；A = 診斷 |
| ❌ 不經訓練、只改 tile/pad 就稱 Distill | 那是**原生 Siax cell**（128/8、256/16…） |
| ❌ 用 SPM-A 分數「微調」全模 Siax 權重 | 未開 RL／finetune 全模里程碑前禁止 |
| ❌ 宣稱 Distill 後 quality_qualified / E3 | 須獨立驗收；預設 false |
| ❌ 替代 Nested / S3 / 雙機 | Distill 是**模型契約**；分散式是**執行契約** |
| ❌ 替代 400% 目視與 seam | 探針不能單獨放行 |
| ❌ 在小 RAM 主機上用 Distill 故事重開 256/32 OOM 實驗 | OOM 議題已用 host class + cell 分開處理 |
| ❌ 無教師 SHA／無底定義的「噪點模型」 | 不可復現則不算本 charter 產物 |
| ❌ 商用預設自動切到學生模 | 須書面 default 變更；現預設仍為**原生全模 + cell**（證據上 256/16 為本機商用候選） |

---

## 3. 與現有 SPM-A 的邊界

| | **SPM-A（已有 · 凍結角色）** | **SPM Distill（本 charter · 未實作）** |
| --- | --- | --- |
| 本質 | **儀表** | **學習／推殘差層的產品線**（若開） |
| 輸入 | BASE + probe bank +（可）已生成 PNG | 底圖生成器 + 教師全模 + bank |
| 對 Siax 全模 | **完整**跑在小窗上作指紋 | 教師**凍結**；學生**不**等於全模 |
| 改生成結果？ | **否**（只量） | **是**（合成路徑改 out） |
| 加速全圖？ | **否** | **可能**（學生更小）— 須實測，禁止先宣稱 |
| 輸出 | JSON fingerprint / MAE / HF | 學生權重 + 合成 PNG + 對照報告 |
| S2.1 品質決定 | 可作 **INCONCLUSIVE 的診斷輸入** | **不得**回寫推翻 S2.1 freeze，除非新 QC 輪 |
| 與 HERE handoff / grab | 無關加速 | 無關；可選日後 `packages/` 出對照包 |

**邊界規則（硬）：**

1. 檔名／JSON `format` 分開：`ige.spm.a.*` vs `ige.spm.distill.*`  
2. SPM-A 工具**不得**寫入學生權重或改 `run_siax_upscale` 默認行為  
3. Distill 實驗報告必須並列：**全模 SHA**、**底定義**、**學生 SHA**、**合成 SHA**  
4. 任一「SPM」口語若未標 A / Distill / approx，文件審查視為**歧義，退回**

---

## 4. 與原生 Siax cell 的邊界

| | 原生 Siax（現行商用路徑） | SPM Distill |
| --- | --- | --- |
| 例 | 128/8、**256/16**、256/32 on 3070 Ti | 未有 |
| 改的是 | `tile_size` / `tile_pad` / device | 模型職責（殘差層） |
| 證據 | `S_SPM_COMMERCIAL_CELL_MATRIX_WARRIOR.json` 等 | 尚無 |
| 可並存 | 是：Distill 學生仍可用 tile 推論 | 是 |

**現行默認執行路徑保持：原生全模 Siax + 選定 cell。**  
Distill **不**取代該默認，除非另發 `DEFAULT_UPSCALE_PATH` 變更記錄。

---

## 5. 成功／失敗（若未來開階段 · 僅定義）

| 結果 | 條件（草案） |
| --- | --- |
| **DISTILL_PILOT_OK** | 同 BASE 合成可復現；學生參數／算力明顯低於全模；SPM-A 對照有報告；無 OOM 謊稱 |
| **DISTILL_FAIL** | 結構漂移、探針全面變差、無法復現、授權不清 |
| **INCONCLUSIVE** | 有數字無目視、或只在小窗好全圖差 |

**任一結果 ≠ Siax 專案 final_acceptance、≠ E3。**

---

## 6. 啟動條件（Gate · 未滿足則只留本頁）

開碼前必須同時：

- [ ] 本 charter 合併或掛在約定分支且無範圍爭議  
- [ ] 教師 checkpoint SHA 鎖定（現行 `560424d9…fd127e` 或書面後代）  
- [ ] 底生成器定義凍結（演算法 + 版本）  
- [ ] Probe bank SHA 凍結  
- [ ] 授權／條款確認記錄  
- [ ] **不做**與 S3.7／S2.1 品質放行綁票  

未勾完 = **禁止**出現 `distill` 權重目錄當正式交付。

---

## 7. 相關現況（只讀指針）

| 物件 | 角色 |
| --- | --- |
| `tools/s2_spm_a_run.py` 等 | **SPM-A 診斷** |
| `src/ige/upscale/siax.py` | **原生全模**推論 |
| `docs/SIAX_S2_PROTOCOL.md` | SPM-approx 矩陣語意 |
| `docs/evidence/S_SPM_COMMERCIAL_CELL_MATRIX_WARRIOR.json` | 全模 cell 性價比（非 Distill） |
| `docs/SPM_LOCAL_SIAX_BACKEND.md` | HERE／本機出口（非 Distill） |

---

## 8. 變更

| 版本 | 日期 | 說明 |
| --- | --- | --- |
| 1.0 | 2026-11-02 | 初版：範圍／非目標／SPM-A 邊界；無實作 |

**簽署式結語：**  
SPM-A 量尺保留。Distill 是可選未來產品線。  
在 Gate 勾完前，**不**把任何現行速度或 PNG 歸因於「噪點 distill 成功」。
