# SHQ · 換涯人（HUAN_YA_REN）技憲

**formal:** `SHQ_HUAN_YA_REN_V1`  
**write_id:** `01439`  
**zh:** 換涯人  
**en:** Cliff-edge person lock-paste replace  
**alias:** LOCK_PASTE cliff return · 崖人硬貼換回  
**LOCK:** `CONSTITUTION_LOCK_01439.json`  
**STICK:** `STICK_HUAN_YA_REN`  
**金案 SHA:** `SETS/PROJ_SHQ_HUAN_YA_REN_01439/GOLD_SHA.json`  
**parent:** 01386 四態×反 · 01380 full hole · sole-support · IC 光影  
**anti-example:** 01436A metal-HF 毀頭（僅幾何 outside=0 ≠ 視覺成功）

---

## 0. 一句

> **換涯人** = 在「涯／崖／空台」場景上，用 **真 peep 升清 → EMPTY 同機位 → LOCK 硬貼** 把人換回或換上，  
> **頭必須在、洞外 bit-exact、elev_remap=false、sole 可鎖腳**；  
> 禁 freeframe 偷步、禁 donor 材質 HF 洗身份、禁把 outside=0 當肉眼成功。

適用：崖邊／橋邊／峰頂／空台 **單人**（可擴 N 人，每人獨立 peep）。

---

## 1. 五步公式（金板 `9043229b`）

```text
① SRC      原圖凍結（有人·有背·有涯）
② PEEP     洞框 peep（尺度契約載體；退地）
③ HD ELEV  只升 peep 像素（鎖尺；禁改 corners）
④ EMPTY    除人後空涯（盡量同機位；全圖重生會毒扣）
⑤ LOCK_PASTE  peep/elev 硬貼回 EMPTY · 洞外 max_diff=0
```

可選後段：

```text
⑥ IC 光影   對 REF 原光做照明匹配（不改幾何）
⑦ SOLE     腳底 sole-support / 黃線鎖腳（E-SHQ-15/20）
```

對應四態：

| 字 | 在換涯人 |
|----|----------|
| **除** | EMPTY = 去涯上人 |
| **扣** | Support(\|SRC−EMPTY\|) → 人剪影 |
| **洞** | M_hole = 人剪影（非岩台矩形） |
| **生** | HD ELEV 只在 peep／洞內 |
| **反** | 有人↔無人 · 洞↔反洞 · 生前↔生后 · peep↔同框空 |

---

## 2. 硬約束（違者不得報 PASS_RESTORE）

| ID | 約束 |
|----|------|
| H1 | `elev_remap=false` — elev 不改 corners／位姿 |
| H2 | hardpaste：`out=EMPTY; out[M_hole]=HD[M_hole]`；洞外 max_diff=0（記憶體） |
| H3 | **頭在**：洞內 ncc(SRC_peep, RET_peep) ≥ 0.98 或肉眼頭完整 |
| H4 | 洞=人剪影；禁 W1 大框吃岩（E-SHQ-33 退地） |
| H5 | dens/HF 只養清晰，**不得**當 freeframe 構圖主權（W3/W5） |
| H6 | metal/antivirus donor **僅可弱 HF 上身甲**，臉=純 peep |
| H7 | `ACCEPT_FULL_HD=false` 除非 C5 Gold+CI |
| H8 | 宣稱分級：金案可標 **C2_RESTORE**；非 C5 不得生產 SUCCESS |

---

## 3. 走錯（已入憲反例）

| 錯 | 現象 | 治 |
|----|------|-----|
| 01436A metal HF 過重 | 無頭／甲碎晶 | 臉純 peep；身弱 HF |
| Imagine 全圖除 | 扣污染岩／天 | 優先局部除；扣用 skill anti-diff |
| outside=0 當成功 | 幾何假綠 | 必加 H3 頭在／洞內 ncc |
| peep 帶地 | 腳下灰岩塊 | 退地 TUIDI |
| Lanczos 冒充 Skill A | 騙 native | dens=proxy 必標 |

---

## 4. 金案資產（原 SHA · 不得替換冒充）

見 `GOLD_SHA.json`。主錨：

- **五步板** `9043229b` — 公式可視化  
- **FINAL sole** `5a1246fb` / **FINAL clean** `a715a7ee` — 視覺成功  
- **HD elev 白底** `688849c1` — 生段 donor peep  
- **IC 三聯** `4f5d40ce` — 光影後段  
- **SRC** `cf9d9dfa` — 中態銀甲全身  

`after_sole` ↔ `after_clean` ncc≈0.999 → 同 FINAL 族。

---

## 5. 調用卡（10 秒）

```bash
# 字詞／四態
python3 shq_edit_hole_four_anti_debug.py glossary
python3 shq_edit_hole_four_anti_debug.py anti-diff --keep SRC --remove EMPTY --out $RUN/kou
python3 shq_edit_hole_four_anti_debug.py hardpaste --src EMPTY --hd HD_ELEV --hole M_hole --out RETURN.png

# 換涯人 STICK（見 STICK_HUAN_YA_REN）
# 輸入: SRC, (可選 EMPTY), (可選 HD_ELEV peep)
# 輸出: EMPTY, M_hole, PEEP, RETURN, SOLE_AUDIT, REPORT
```

人工最小閉環：

1. 凍 SRC  
2. 產 EMPTY（除涯人）  
3. 扣 → M_hole（人剪影）  
4. peep @ 洞框；退地  
5. elev peep（鎖尺）  
6. hardpaste → RETURN  
7. 反查板 + 頭在閘 + sole 可選  

---

## 6. E 碼

| 碼 | 名 | 默認 |
|----|-----|------|
| E-HYR-01 | HEAD_MISSING_ON_RETURN | BLOCK restore claim |
| E-HYR-02 | HOLE_EATS_CLIFF_ROCK | WARN→strict BLOCK |
| E-HYR-03 | OUTSIDE_ONLY_PASS | 禁單獨當 SUCCESS |
| E-HYR-04 | FREEFRAME_ELEV_STEAL | BLOCK |
| E-HYR-05 | GOLD_SHA_MISMATCH | WARN |

---

## 7. 宣稱

| 級 | 何時 |
|----|------|
| C2_RESTORE | 五步齊 + 頭在 + outside_mem=0 + 金案可對 SHA |
| C3 | 有 backend densify log |
| C5 / ACCEPT_FULL_HD | Gold+CI only · 本憲不自動開 |

---

## 8. 金句

> **換涯人：空涯接人，人要有頭；貼回鎖洞，洞不吃岩。**  
> **五步板是法，sole 是腳，IC 是光；HF 不得奪主權。**  
> **outside=0 是契約，不是美圖證明。**

---

## 9. 狀態

`ACCEPT_FULL_HD=false`  
`production_claim=false`  
`implementation_status=constitution_gold_anchored`  
金案已 SHA 凍結；runner 可後接 `shq_huan_ya_ren.py`（本 write 先憲後碼）。
