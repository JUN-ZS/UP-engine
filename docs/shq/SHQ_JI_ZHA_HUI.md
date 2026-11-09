# SHQ · 機炸回（JI_ZHA_HUI）技憲總稱

**formal:** `SHQ_JI_ZHA_HUI_V1`  
**write_id:** `01441`  
**zh:** 機炸回  
**en:** Mecha Explode-Return  
**alias:** PARTMAP 爆炸回位 · 結構鎖材質四角回 · MATLOCK guided return  
**LOCK:** `CONSTITUTION_LOCK_01441.json`  
**STICK:** `STICK_JI_ZHA_HUI`（總稱；執行默認釘 `STICK_PARTMAP_4CORNER_MAT_GUIDED`）  
**金案 SHA:** `SETS/PROJ_SHQ_JI_ZHA_HUI_01441/GOLD_SHA.json`  
**parents:** 01329 PARTMAP · 01338 RESTART 雙4角 · 01335 邊整體 · 01327/01328 金包  
**sibling（不同枝）:** 01439 換涯人（人崖 peep，非機甲爆炸）

---

## 0. 一句

> **機炸回** = 機甲（或可分件剛體）**先炸清教學 → 結構鎖升材 → 四角硬貼／引導對位回原景**。  
> 框=**圖邊** corners_4，不是機甲 AABB；**elev_remap=false**；**α XOR=0**；  
> 炸開為了定義件，回為了把 HD 材質鎖回原姿。

適用：單機 scrapyard／戰場／室內機甲；8 件默認（可擴）；非「人崖換人」。

---

## 1. 總稱涵蓋（技能集樹）

```text
機炸回 JI_ZHA_HUI
├── 主幹 formal  PARTMAP_4CORNER_MAT_GUIDED_V1   (write 01329)
│   ├── PARTMAP_EXPLODE_4CORNER_V1               爆炸+四角契約
│   └── PARTMAP_MAT_GUIDED_RETURN_V1             材質鎖+引導回
├── 定位前置     RESTART_DUAL_4CORNER_V1          (01338)
├── 邊／整體     EDGE_WHOLE_PART_ELEV             (01335)
├── 結構樹       shq_part_structure / pixel_structure
└── 材質同族     Skill B MAT fill (01410) · STRUCTURE_LOCK_DENSIFY
```

**調用時說「機炸回」= 走這整枝，不走換涯人。**

---

## 2. 六步（金板標號 1–6）

| # | 板標 | 憲步驟 |
|---|------|--------|
| 1 | MAT structure-lock 8 parts | 8 件結構鎖（HEAD…LEG_L） |
| 2 | EXPLODE MAT densify | 爆炸圖 + 升材質清晰 |
| 3 | 4corner hardpaste MATLOCK | 四角硬貼 MATLOCK |
| 4 | guided pose SRC × FULL_MAT | 引導姿態 × 全材 |
| 5 | guided align MATLOCK | 引導對位 MATLOCK |
| 6 | structure fix hole | 結構補洞（peep 中間態） |

前置（憲權威鏈 01329）：

```text
0  SRC 全機凍結
0b 教學 PARTMAP（圖邊 4 角 X + 件名）
0c 爆炸圖分件
0d corners_4 抽件 + TUIDI 退地
```

公式：

```text
frame_parent = image edge {TL,TR,BR,BL}
part_i.return_key = part_id + corners_4
elev_remap = FALSE
structure_lock: HD_RGB 只進凍結 α；α_xor == 0
return_A = hardpaste @ home corners_4
return_B = guided reference(SRC pose + FULL_MAT | MATLOCK)
```

---

## 3. 硬約束（違者不得報 機炸回 SUCCESS）

| ID | 約束 |
|----|------|
| J1 | 框=**圖邊**四角，禁機甲外形 AABB 當 frame（E-63） |
| J2 | `elev_remap=false` — elev 不改 corners／位姿 |
| J3 | structure_lock：`alpha_xor==0` |
| J4 | hardpaste native：洞外／α 外不偷改；禁 warp donor 救 coverage（E-43） |
| J5 | 爆炸圖=**教學定義**，不得當 freeframe 構圖主權 |
| J6 | 8 件默認語義固定；擴件必須 part_id+corners_4+tuidi SHA |
| J7 | 引導回鎖 **SRC pose**；禁 donor 底承 soft peep 冒硬貼 |
| J8 | `ACCEPT_FULL_HD=false` 除非 C5 Gold+CI |
| J9 | 與 **換涯人** 分枝：人崖 peep ≠ 機炸回 |

---

## 4. 8 件默認語義

```text
#1 HEAD  #2 CHEST  #3 BACKPACK  #4 ARM_R
#5 ARM_L #6 WAIST  #7 LEG_R     #8 LEG_L
```

---

## 5. 金案資產（原 SHA · 不得替換冒充）

見 `GOLD_SHA.json` / `references/JI_ZHA_HUI_GOLD_SHA.json`。

主錨：

- SRC `b32bd2ef` scrapyard 全機  
- EXPLODE `af20a0cb`（孿生 `359af77f`）  
- 板 1–3 `a2289860`  
- 三聯 4–5–6 `4daf0007`  
- 洞中間 `166e7923`  

工程金包路徑（歷史）：

- `SETS/PROJ_SHQ_REALTEX_MIX_MECHA/SHQ_RUN_RT1/PARTMAP_*`  
- `SETS/PROJ_BOUNDARY_WALKER_PARTMAP`

---

## 6. 調用卡（10 秒）

```text
STICK: STICK_JI_ZHA_HUI
  → 執行默認 STICK_PARTMAP_4CORNER_MAT_GUIDED
讀: SHQ_JI_ZHA_HUI.md + SHQ_PARTMAP_4CORNER_MAT.md + DO_NOT_REPEAT.md

流水:
  SRC → PARTMAP教學 → EXPLODE → TUIDI/corners_4
  → MAT densify structure-lock → hardpaste 4corner
  → guided FULL_MAT / MATLOCK → structure fix hole 可選
```

```bash
# 契約／報告（金跑）
cat SETS/PROJ_SHQ_REALTEX_MIX_MECHA/SHQ_RUN_RT1/PARTMAP_EXPLODE_4CORNER_V1/PART_4CORNER_CONTRACT.json
cat SETS/PROJ_SHQ_REALTEX_MIX_MECHA/SHQ_RUN_RT1/PARTMAP_MAT_GUIDED_RETURN_V1/REPORT.json
```

---

## 7. E 碼（機炸回）

| 碼 | 名 | 治 |
|----|-----|-----|
| E-JZH-01 | FRAME_IS_MECHA_AABB | 改圖邊 corners_4 |
| E-JZH-02 | ELEV_REMAP_ON | 強制 false |
| E-JZH-03 | ALPHA_XOR_NE_0 | 重退地／重 structure_lock |
| E-JZH-04 | EXPLODE_AS_FREEFRAME | 爆炸只教學 |
| E-JZH-05 | GUIDED_DROPS_SRC_POSE | 重釘 SRC pose |
| E-JZH-06 | GOLD_SHA_MISMATCH | WARN |
| E-JZH-07 | CONFUSED_WITH_HUAN_YA_REN | 分枝：人≠機 |

繼承 E-63/64/65 · E-43。

---

## 8. 宣稱

| 級 | 何時 |
|----|------|
| C2_PARTMAP | 六步／權威鏈齊 + α_xor0 + elev_remap false + 金 SHA 可對 |
| C3 | 有 backend densify log |
| C5 / ACCEPT_FULL_HD | Gold+CI only · 本總稱不自動開 |

---

## 9. 金句

> **機炸回：先炸清件，再鎖材硬回；框在圖邊，不在機殼。**  
> **爆炸是教學，回位是主權；MATLOCK 對 SRC，不對 freeframe。**  
> **換涯人換人，機炸回換甲；兩枝勿混。**

---

## 10. 狀態

`ACCEPT_FULL_HD=false`  
`production_claim=false`  
`implementation_status=constitution_umbrella_gold_anchored`  
主執行仍 01329 PARTMAP；本 write = **總稱入憲 + 金 SHA 凍結 + 與換涯人分枝**。
