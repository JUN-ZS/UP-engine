# SHQ / BW · 新畫女（XIN_HUA_NV）技憲總稱

**formal:** `SHQ_XIN_HUA_NV_V1`  
**write_id:** `01443`  
**zh:** 新畫女  
**en:** New-Paint Heroine · Boundary Walker Face Stack  
**alias:** 標準面鎖畫女 · a8b-PATH1E 女主 · 邊界行人女主臉技  
**LOCK:** `CONSTITUTION_LOCK_01443.json`  
**STICK:** `STICK_XIN_HUA_NV`  
**金案:** `SETS/PROJ_SHQ_XIN_HUA_NV_01443/` · `references/XIN_HUA_NV_GOLD_SHA.json`  
**母憲:** `BOUNDARY_WALKER_UNIFIED_RULES.md`（§0.10 · §0.13 · §0.12.14–21 · §5 PATH1E）  
**sibling 分枝:** 換涯人 01439（人崖 peep）· 機炸回 01441（機甲 PARTMAP；可**應用於**新畫女主體，非臉正典）

---

## 0. 一句

> **新畫女** = 以**標準面 a8b** 為唯一身份源，經 **ST1 IP → ST2 全幅鎖臉 → PATH1E plate→ECC** 把「同一女主」畫進每張完成圖；  
> 字／GEO／衣材可疊，**骨相不可漂**。

適用：《邊界行人》全專輯女主、同標準面的 LOOP／FREE／海報。  
**不是** 隨便文生換臉；**不是** 棚拍 a8b 直 ECC；**不是** 換涯人 peep。

---

## 1. 總稱涵蓋（技能樹）

```text
新畫女 XIN_HUA_NV
├── §0.10  STANDARD_FACE_a8b          身份源（唯一）
├── §0.0   ST0 WORLD → ST1 IP 退地多角度（face ref=a8b）
├── §0.13  FULLFRAME_FACE_LOCK        a8b-first + 即 PATH1E
├── §5 / §0.12.17  PATH1E plate→ECC   臉 HD 正典
├── §0.12.14  PIXEL_RATIO / TRUE_FACE 臉格回插 · 真臉鎖
├── §0.12.15  GRID×SIAX · S1HL 一升混鎖
├── §0.12.16  PIXEL_CTRL 眼白鐵律
├── §0.12.18  GRID_CLEAN / BEAT
├── §0.12.20  SKIN_MAT 四參數
├── §0.12.21  FACE_GENMIX 混參重生
├── §0.14   GEO_INDICATOR（字標 · 不改骨相）
└── 應用枝（非臉正典）
    ├── OBA_BW_POSTER_TEX4            甲／裙材質
    └── 機炸回 PARTMAP on BW          分件回位用她當 SRC
```

**調用「新畫女」= 走臉身份+全幅+PATH1E 主鏈；衣材／PARTMAP 另說。**

---

## 2. 主流水（硬順序）

```text
0   讀 STANDARD_FACE_LOCK（a8b）
1   ST0  WORLD_CONCEPT（可無人）
2   ST1  HEROINE_IP：退地 · 多角度 · 槌創意 · face ref = a8b
3   ST2  FULLFRAME_FACE_LOCK：asset_ids[0]=a8b · 即 PATH1E
4   只從 LOCKED MID 抽人／切 matte／建 mask
5   升臉 HD：PATH1E only
      plate = Ref(face_crop_of_base, a8b)
      ECC(plate → base) ≥ 0.85
      hard_paste + eye_white HARD→ST
6   可選：S1HL / PIXEL_CTRL / SKIN_MAT / FACE_GENMIX / GRID_CLEAN
7   ST5 ET 字 + GEO_INDICATOR 疊在已鎖臉上（字不改骨相）
8   ST7 GATE · ST8 FINAL
```

公式：

```text
identity = a8b78fe5…          # 唯一
L0 = FULLFRAME_FACE_LOCK(a8b-first)
face_hd = PATH1E_plate_ECC(L0, a8b)
∀ frame ∈ PRE/MID/POST/FREE: inherit(L0) · no pure-txt identity swap
```

---

## 3. 硬約束（違者不得報 新畫女 SUCCESS）

| ID | 約束 |
|----|------|
| N1 | 標準面**只能** a8b；禁另抽「更好看的臉」當身份源 |
| N2 | ST2 必須 **a8b-first + 即 PATH1E**；禁 scene-first 弱鎖 |
| N3 | PATH1E 必須 **plate→ECC**；棚拍 a8b 直 ECC = E-GS-12 FAIL |
| N4 | 臉 ROI 來自 LOCKED MID，禁無關特寫硬塞 |
| N5 | 眼白 HARD→ST exact（PIXEL_CTRL） |
| N6 | GRID 升景／字／材；**臉格禁止再 FACE_REF**（§0.12.13） |
| N7 | PRE/POST 只改時間 ±δt，禁重抽人 |
| N8 | S1HL 禁二升 |
| N9 | FACE_GENMIX 禁直接拿板貼混（必須 Ref 重生） |
| N10 | FAT_FACE_REF = 實驗，**非**正典 |
| N11 | 與換涯人／純機炸回分枝：新畫女是**女主臉畫法** |

---

## 4. 金案錨（不得替換冒充）

見 `GOLD_SHA.json`。

主錨海報：`c2dc7af4…` · SHA `ba92a8fd…` · GEO_T_H2 · OBSIDIAN_ORBIT  
標準面：`a8b78fe5…` · SHA `f612ec7e…`  
全幅樣板：`2ce5fabe…` · SET-Q `f1d38afd…`  
PATH1E OK：`L-fc0a2fa7b8a9`

母憲路徑：`/workspace/artifacts/BOUNDARY_WALKER_UNIFIED_RULES.md`  
附件：`PATH1E_PLATE_ECC_LAW.md` · `STANDARD_FACE_LOCK.json` · `SIAX_HYBRID_FACELOCK_S1HL_NAME.md`

---

## 5. 調用卡（10 秒）

```text
STICK: STICK_XIN_HUA_NV
讀: SHQ_XIN_HUA_NV.md + BOUNDARY_WALKER_UNIFIED_RULES.md §0.10 §0.13 §0.12.17

流水:
  a8b → ST1 IP → ST2 全幅鎖臉 → PATH1E plate→ECC
  → (可選膚質/S1HL) → ET/GEO 疊字 → FINAL
```

閘：face identity = a8b · ECC cc≥0.85 · eye_white HARD · no pure-txt face swap

---

## 6. E 碼（新畫女）

| 碼 | 名 | 治 |
|----|-----|-----|
| E-XHN-01 | NON_A8B_IDENTITY | 改回 a8b |
| E-XHN-02 | SCENE_FIRST_WEAK_LOCK | 重 ST2 a8b-first |
| E-XHN-03 | BARE_A8B_DIRECT_ECC | 走 plate→ECC |
| E-XHN-04 | FACE_ROI_NOT_FROM_MID | 從 LOCKED MID 重切 |
| E-XHN-05 | EYE_WHITE_BROKEN | PIXEL_CTRL HARD→ST |
| E-XHN-06 | GRID_FACE_REF_AGAIN | 臉格禁 FACE_REF |
| E-XHN-07 | PURE_TXT_FACE_SWAP | 帶 a8b ref 重生 |
| E-XHN-08 | CONFUSED_HUAN_YA_REN | 分枝 peep≠新畫女 |
| E-XHN-09 | GOLD_SHA_MISMATCH | WARN |

繼承 E-GS-08/09/12 · PATH1E 閘。

---

## 7. 宣稱

| 級 | 何時 |
|----|------|
| C2_XIN_HUA_NV | a8b 可溯 · ST2 程序 · PATH1E plate 閘 OK · 金海報可對 |
| C3 | 有 ECC log + eye_white 證明 |
| C5 / ACCEPT_FULL_HD | Gold+CI only · 本總稱不自動開 |

---

## 8. 金句

> **新畫女：先鎖是誰（a8b），再畫進景（全幅），再升清（PATH1E）；字火可燃，骨相不漂。**  
> **plate 對姿再 ECC，裸棚直貼是假 PATH1E。**  
> **換涯人換人位，機炸回換甲件，新畫女換畫同一張臉。**

---

## 9. 狀態

`ACCEPT_FULL_HD=false`  
`production_claim=false`  
`implementation_status=constitution_umbrella_gold_anchored`  
執行仍母憲 BOUNDARY_WALKER_UNIFIED_RULES；本 write = **總稱入憲 + 金 SHA 凍結 + 臉技棧歸名**。
