# SHQ · 外力反 V2.1 · 任意物件 · 微調結構（01469）

**formal:** `WAI_LI_FAN_V2_1_ANYOBJ_TUNE_V1`  
**總稱:** **外力反 V2.1**（取代實跑默認；V2 01456 為母）  
**STICK:** `STICK_WAI_LI_FAN_V2`（同 stick · 升版契約）  
**母:** 01448 四態代數 · 01456 V2 · 01457 真 CLIP · 01466 外力GROK · §19+§22  
**PY:** `shq_wai_li_fan_multilayer.py`（V2.1 旋鈕）  
**ACCEPT_FULL_HD:** false

---

## 0. 你問的兩件事

### 0.1 為什麼「公式 PY 通過不了另一類型的圖」？

**不是公式錯，是公式把「一類圖的隱含先驗」寫死成常數。**

| 隱含先驗（舊 V2 實跑） | 換圖就斷 |
|----------------------|----------|
| 物件 ≈ **人頭／單頭** | 雙機甲、多頭、肩甲、全身 → kou 最大 CC 選錯 |
| `thr=22` 固定 | 遠景人噪、機甲金屬反光、霓虹 → 洞炸／洞碎 |
| peep = **bbox 裁** | 換類型仍「自 peep」→ 與 01457 真 CLIP 衝突 |
| 最大連通塊 = 洞 | 除後**全圖打光飄** → frac 0.5+ 假洞 |
| 無 `part_role` | 左頭／右頭／胸甲／整機 無選件主權 |
| C2 outside=0 當成功 | 另一類型視覺還原爛仍報 PASS |

\[
\text{TypeA selftest PASS}
\nRightarrow
\text{TypeB chain PASS}
\]

因為 **TypeB 打破了 TypeA 寫死的 interface 常數**，不是四態代數失效。

### 0.2 為什麼「每個方法獨立成功，組起來連動就錯」？（全專案 01448）

見 `SHQ_FOUR_ANTI_ALGEBRA_ARCH.md`。一句：

> **獨立成功量的是局部閘；連動需要的是共享 State Bus + 不變量。**

| 獨立 | 連動斷點 |
|------|----------|
| 除頭好看 | 下游重算洞（E-FA-02） |
| HD 升清好看 | freeframe 偷尺度（E-FA-03） |
| kou 有 mask | 與 Imagine 除 **不同機位** |
| hardpaste outside=0 | 洞形錯 → 貼對了錯洞 |
| 爆炸／教學 PASS | 教學位當 home（E-FA-05） |
| 各 skill 金閘 | **無跨 skill 總線** |

**偽組合：**

```text
獨立 PASS ≠ 可組合
可組合 ⇔ State Bus 共享 ∧ 不變量 1–6 ∧ 同宣稱級 ∧ 外力GROK 除生
```

---

## 1. [(生,除,洞,扣)×(反)] 全專案真定義（再鎖 · 任意物件）

**不是只對頭。頭只是「一咬」的特例。**

| 字 | 任意物件語義 | 反 |
|----|--------------|-----|
| **除** | 外力GROK 去掉 **目標物件**（頭／件／人／機甲／胸甲…）**或** 除背 | 有物件 L0 ↔ 無物件 L1 |
| **扣** | \(\mathrm{kou}(L_0,L_{\mathrm{edit}};\mathrm{tune})\) 證變區；**作證不重寫主權** | 扣熱圖 ↔ 疊回驗 |
| **洞** | 物件剪影空位 \(M\)（形）；**真洞=外力除後像素不在** | \(1-M\) 洞外 bit-exact |
| **生** | 只在洞內填／升清；座標系=該層 L0 | 生前 peep ↔ 生後 elev |
| **CLIP** | **外力除背** → \(M_{\mathrm{subj}}\) → \(L\odot M\)（**禁自 peep**） | \(M_{\mathrm{bg}}\) |
| **反** | 每態正/對板 | 省略反 = E-FA-06 |

### 1.1 (N) 層 × (X) 層 = 真能力（你的更正）

```text
對每一層 X ∈ 0..N-1：
  外力GROK·除背(X) → 扣 → M_subj_X = CLIP MASK_X
  外力GROK·除件(X) → 扣 → M_part_X = 洞_X · MARK_X
  CLIP_X = L0_X ⊙ M_subj_X     ← 子層材料，不是 bbox 自 peep
  子層 L0_{X+1} ← CLIP_X 上再 除件 的 peep 契約 或 整 CLIP 作下一咬
  回：經 MARK_X 反扣，禁止 freeframe
```

> **如果你把 (N) 層用 (X) 各層概念，再調用外力除背，就會有 CLIP MASK。**  
> **不用自 peep。這才是四態真能力。**

### 1.2 任意物件（ANY_OBJECT）

```text
part_role ∈ {
  head, face, helmet, torso, limb, weapon, full_subject,
  mecha_part, prop, custom
}
```

每一 `part_role` 只換 **Tune Pack** 與 **Imagine 提示詞**，**不換代數**。

---

## 2. 接口不變量（連動唯一准繩 · 繼承 01448）

1. 同機位 L0 / L1 / 除背  
2. 同洞形全鏈共用 MARK（或可證繼承）  
3. CLIP 來自 **除背**，非 bbox 自 peep  
4. elev_remap=false  
5. 洞外 max_diff=0  
6. scale-lock 生不改構圖主權  
7. **外力GROK** 除／除背／生必有 asset  
8. **part_role + tune_id** 寫入 State Bus（V2.1 新）

---

## 3. V2.1 新結構：Tune Pack（微調就能換類型）

**原則：代數凍結；旋鈕外置。** 換圖類型 = 換 pack，不改公式骨架。

| 旋鈕 | 鍵 | 作用 | 人像近 | 人像遠 | 雙機甲中 | 單機甲件 |
|------|-----|------|--------|--------|----------|----------|
| 扣閾 | `kou_thr` | absdiff 二值 | 20–24 | 16–22 | 24–32 | 22–28 |
| 最小洞面積 | `min_area` | 濾碎點 | 2k | 500 | 3k | 2k |
| 最大洞 frac | `max_frac` | 防全圖假洞 | 0.25 | 0.12 | 0.20 | 0.30 |
| 空間先驗 | `roi_prior` | left/right/upper/none | upper | center | **part side** | none/side |
| CC 策略 | `cc_mode` | largest / score_roi / multi | largest | largest | **score_roi** | largest |
| 除背 bg 距 | `chu_bei_dist` | CLIP 扣 | 22 | 18 | 20–28 | 22 |
| 生 scale 上限 | `grow_max` | 1.15 | 1.15 | 1.12 | 1.15 | 1.20 |
| 物件提示 | `prompt_part` | 外力GROK 文案 | head | small head | helmet/sensor | armor plate |

```text
TUNE_PACKS = {
  "human_mid_head": {...},
  "human_far_head": {...},
  "mecha_dual_part": {...},
  "mecha_solo_part": {...},
  "generic_object": {...},  # 默認 · 保守
}
```

**換類型失敗時的修法：**

```text
1. 看 REPORT.tune + gates.frac / cc_pick
2. 只改 Tune Pack（thr / roi / max_frac）
3. 禁止為過閘而 OpenCV 假除生
4. 禁止為過閘而自 peep 冒充 CLIP
```

---

## 4. 權威鏈 V2.1（任意物件）

```text
V21-0  SRC freeze · 選 part_role · 載入 Tune Pack
V21-1  外力GROK 除背 → L_nobg · 扣 → M_subj · CLIP   【禁自 peep】
V21-2  外力GROK 除件(part) → L_empty · 真洞
V21-3  扣(tune) → M_part · MARK 凍（corners_4 · parent link）
V21-4  反·除 · 反·洞 · 反·扣
V21-5  外力GROK 生 on L_empty（ref=CLIP/件）→ I_HD
V21-6  放大加清 scale-lock(tune.grow_max)
V21-7  hardpaste · 洞外=0 · 反·生 · 反·回
V21-8  若 N>1：子層 L0 = CLIP 再咬 或 peep 契約；STACK via MARK
V21-9  MULTI_BUS + 類型閘 · 不可把 selftest PASS 升成 FULL
```

---

## 5. 為何機甲 PY「過」人像／另一類型「不過」— 決策樹

```text
FAIL_FRAC_TOO_LARGE  → kou thr↑ 或 roi_prior 開 · 除是否全圖重打光？
FAIL_FRAC_TOO_SMALL  → thr↓ · 遠景 min_area↓
FAIL_WRONG_CC        → cc_mode=score_roi · 指定 part side
FAIL_NEED_IMAGINE    → 補外力GROK asset（正確，不是 bug）
FAIL_OUTSIDE         → MARK 與 生 不同洞 · 禁重算 M
FAIL_VISUAL_ONLY     → C2 幾何過但 RESTORE 不過 · 降宣稱
FAIL_SELF_PEEP       → 改除背 CLIP（E-WLG-02）
```

---

## 6. E 碼（V2.1 增）

| 碼 | 禁 |
|----|-----|
| E-WLF21-01 | 換圖類型不換 Tune 硬扛 |
| E-WLF21-02 | 自 peep 當 CLIP（再申） |
| E-WLF21-03 | 最大 CC 不問 part_role |
| E-WLF21-04 | selftest/TypeA PASS 宣稱 TypeB 全鏈 |
| E-WLF21-05 | 為過 thr 用 OpenCV 假除 |
| E-FA-01..07 | 連動偽組合（01448） |
| E-WLG-* | 外力GROK 偷步（01466） |

---

## 7. 金句

> **四態是代數；Tune Pack 是單位換算。**  
> **獨立 PASS 只證明局部；連動 PASS 才證明洞與咬同構。**  
> **CLIP 從外力除背來，不從 bbox 裁。**  
> **頭只是物件的一種；任意物件同一套 [(生,除,洞,扣)×(反)]。**  
> **公式過不了另一類圖 = 先驗寫死，不是代數死刑。**

---

## 8. 狀態

`implementation_status=constitution_v2_1`  
`next=PY tune packs + dual mecha / human mid dual gate`  
`ACCEPT_FULL_HD=false`
