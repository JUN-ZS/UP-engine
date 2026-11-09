# SHQ · 回車大炮（HUI_CHE_DA_PAO）技憲總稱

**formal:** `SHQ_HUI_CHE_DA_PAO_V1`  
**write_id:** `01445`  
**zh:** 回車大炮  
**en:** Return-Vehicle Cannon · 3-Subject Relative Hierarchy Return  
**alias:** 三主體相對回 · S2 GENERIC 戰場回 · 紅坦克炮管鏈  
**LOCK:** `CONSTITUTION_LOCK_01445.json`  
**STICK:** `STICK_HUI_CHE_DA_PAO`  
**金案:** `SETS/PROJ_SHQ_HUI_CHE_DA_PAO_01445/` · `references/HUI_CHE_DA_PAO_GOLD_SHA.json`  
**parents:** 01407 L1_GENERIC_3SUBJ · 01408 S2_GENERIC_RELATIVE · 階層合眾 · MULTI_RETURN  
**sibling 分枝:** 機炸回 01441（單機 PARTMAP）· 新畫女 01443（臉）· 換涯人 01439（人崖 peep）

---

## 0. 一句

> **回車大炮** = 雨戰場上 **機甲｜人｜坦克** 三主體，用**相對座標**拆 18 件、建階層 \(T\) 樹，再 EMPTY×升清×硬回；  
> 大炮 = 紅坦克炮管 peep 所象徵的 **件級 elev 回位**；回車 = **MULTI-RETURN 合眾回景**。

適用：任意新 3 主體共景（不限坦克），只要 L0 得 3 CC；金錨是泥地紅坦克三子圖。  
**不是** scene 絕對關節常數；**不是** 單機機炸回冒充；**不取代** BF_S1/S2 金案。

---

## 1. 總稱涵蓋（技能樹）

```text
回車大炮 HUI_CHE_DA_PAO
├── L0  SRC 全景 + m_hole 3 CC（左→右）
├── L1  L1_GENERIC_3SUBJ_RELATIVE_V0     (01407)
│       · local (u,v) · 每主體 6 件 ×3 = 18
├── S2  S2_GENERIC_RELATIVE_HIERARCHY_V0 (01408)
│       · T_scene←leaf = T_scene←subj · T_subj←part
│       · chain 誤差 ≤ 0.5 px · model_scale 分離
├── EMPTY × S*  合眾空場
├── 件 peep elev（炮管／臂／頭…）· LOCAL_OBJECT_SR 可接
└── MULTI-RETURN 硬貼回景
```

執行默認：先 `run_l1_generic_3subj` → `run_s2_generic` → 合眾回位。

---

## 2. 主流水（金板 7 圖）

| # | 板 | 憲步驟 |
|---|-----|--------|
| A | FULL L0 | 三主體全景凍結 |
| D | INSTANCE | 3 CC 實心色（主體層） |
| C | L1 PARTMAP | 18 相對分件彩圖 |
| B | S2_GENERIC | bbox+關節樹 · **chain=0.0 PASS** |
| E | EMPTY | 去主體空場 |
| G | TANK PEEP | 大炮件 peep elev HD |
| F | RETURN | 合眾回位全景 |

公式：

```text
subjects = sort_cc(m_hole, left→right)   # 恰好 3
∀ s: local (u,v) ∈ [0,1]² · joints relative
parts = 18 · overlap=0 · union≈m_hole
T_scene←leaf = T_scene←subject · T_subject←part
model_scale ≠ object_transform ≠ tile_size
elev_remap = FALSE
return = MULTI_RETURN(EMPTY, S*_elev peep)
```

---

## 3. 硬約束

| ID | 約束 |
|----|------|
| R1 | 恰好 3 個 area≥min 的 CC（G0） |
| R2 | 關節**只**相對 (u,v)；禁 scene 絕對常數（如 y=192） |
| R3 | 18 parts 非空 · pairwise overlap=0 · union≈hole |
| R4 | 每 leaf 有 \(T_{scene\leftarrow leaf}\)；往返／鏈誤差 ≤ 0.5 px |
| R5 | `model_scale` 不得偷偷改部件幾何 |
| R6 | 不與 `BF_S1_*` / `BF_S2_*` 混同一 ACCEPT |
| R7 | `elev_remap=false`；禁 feather 救空件 |
| R8 | `ACCEPT_FULL_HD=false` 除非 C5 Gold+CI |
| R9 | 與機炸回分枝：本總稱=**3 主體 GENERIC 相對樹**，非單機四角 PARTMAP 本體 |
| R10 | production_claim=false（草案升總稱，仍非 C5） |

---

## 4. 金案 SHA（不得替換冒充）

見 `GOLD_SHA.json`。主錨 7 asset 如上表 A–G。  
工程：`PROJ_SHQ_L1_GENERIC_3SUBJ_01407/run_new3` · `PROJ_SHQ_S2_GENERIC_01408/run_new3`  
報告：L1/S2 gates 全 PASS · chain_error=0。

---

## 5. 調用卡（10 秒）

```text
STICK: STICK_HUI_CHE_DA_PAO
讀: SHQ_HUI_CHE_DA_PAO.md
    + docs_SHQ_L1_GENERIC_3SUBJ.md
    + docs_SHQ_S2_GENERIC_RELATIVE.md

python3 l1_generic_3subj_relative.py …   # 或 run_l1_generic_3subj
python3 s2_generic_relative_hierarchy.py …  # run_s2_generic
# 再 MULTI_RETURN / peep elev
```

閘：G0–G5 · H0–H5 · chain≈0 · method_id 顯式。

---

## 6. E 碼（回車大炮）

| 碼 | 名 | 治 |
|----|-----|-----|
| E-HCD-01 | NOT_3_CC | 重 L0 m_hole |
| E-HCD-02 | ABSOLUTE_JOINTS | 改相對 (u,v) |
| E-HCD-03 | PART_OVERLAP | 重 band／mask |
| E-HCD-04 | CHAIN_ERROR | 重 T 樹 |
| E-HCD-05 | SCALE_GEOM_HACK | 參數分離 |
| E-HCD-06 | MIX_BF_ACCEPT | 分 formal |
| E-HCD-07 | CONFUSED_JI_ZHA_HUI | 3 主體≠單機四角 |
| E-HCD-08 | GOLD_SHA_MISMATCH | WARN |

---

## 7. 宣稱

| 級 | 何時 |
|----|------|
| C2_HUI_CHE_DA_PAO | L1+S2 gates PASS · 金 7 圖可對 · method_id 顯式 |
| C3 | 有 peep elev + MULTI_RETURN 產物 |
| C5 / ACCEPT_FULL_HD | Gold+CI only · **本總稱不自動開** |

---

## 8. 金句

> **回車大炮：三體相對拆件，階層樹回景；大炮 peep 是件，回車是合眾。**  
> **禁寫死 scene 關節；chain=0 才算 GENERIC PASS。**  
> **機炸回炸一機，回車大炮回三車（機·人·炮）。**

---

## 9. 狀態

`ACCEPT_FULL_HD=false`  
`production_claim=false`  
`implementation_status=constitution_umbrella_gold_anchored`  
執行仍 01407/01408 PY；本 write = **總稱入憲 + 金 SHA 凍結**。
