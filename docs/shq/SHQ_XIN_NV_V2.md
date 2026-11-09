# SHQ · 新女畫 V2 · 外力返 (N)(X)（01464）

**formal:** `SHQ_XIN_NV_V2_WLF3_TRUE_FOUR_ANTI`  
**zh:** **新女畫 V2**（總稱定稿名）  
**en:** New-Paint Heroine V2 · External-Force True Four-Anti Return  
**alias:** 新畫女V2 · XHN2 · a8b洞座返 · XHN∩WLF3∩TRUE_CLIP  
**STICK:** `STICK_XIN_NV_V2`  
**LOCK:** `CONSTITUTION_LOCK_01464.json`  
**write:** 01462 初裝 · **01464 定稿**（RATIO + 真四態 CLIP）  
**母:** 新畫女 V1（01443）· 外力反 V3（01459）· 真四態 CLIP（01457）· 四態反（01448）· 01463-FIX  
**驗案:** `SETS/PROJ_SHQ_XHN_V2_VERIFY_01463/FIX_TRUE_FOUR_ANTI/`  
**ACCEPT_FULL_HD:** false

---

## 0. 定稿一句

```text
新女畫 V2
  = 身份唯一 a8b
  + [(生,除,洞,扣)×(反)] 真四態（外力除 · 禁自 peep）
  + CLIP = 外力除背 扣 M_subj
  + 洞  = 外力除頭 扣 M_head（同框）
  + PATH1E plate 姿@CLIP臉 · native RATIO（禁硬拉 1:1）
  + 生只在洞座
  + (N)(X) 層層反
  + 無洞回 / 自peep = ERROR_TEXTBOOK
```

> **V1 鎖是誰；V2 鎖座位 + 真四態 + RATIO。**  
> **CLIP 不是裁出來的，是外力除背反扣出來的。**

---

## 1. 為何 01464 再定稿

| 曾犯（01462/01463 初驗） | 改正（01464） |
|--------------------------|----------------|
| face **硬拉 1:1** 破姿比 | **native bbox + letterbox** elev |
| 自 peep / 自 bbox 冒充洞與 CLIP | **CLIP←除背扣；洞←除頭扣** |
| 除背 freeframe 當同框 | 除背目標同框；漂則 WARN，M 仍自除背圖扣 |
| 無洞 freeframe 嵌 a8b 當成功 | **E-XHN2-01** 錯圖必出 |
| 跳層不凍 MARK | **(N)(X)** 每層洞可溯 |

---

## 2. 符號 (N)(X)

| 符 | 義 |
|----|-----|
| **N** | 層數（1=僅臉洞；2=臉+CLIP 全身；…） |
| **X** | 當前層；**X 層 CLIP/CROP = 上層虛擬洞的反扣件** |
| **返還** | elev/plate 經洞座 生/hardpaste 回 X−1…→ROOT |

```text
L0 有景
  X=1  除頭 → 洞1 · plate_a8b 生@洞1 → R1
  X=2  除背 → CLIP2 · （可升清）經洞/反除背回景 → R2
  STACK: 每步 outside 洞外不動
```

---

## 3. 真四態公式（本技核心）

\[
\begin{aligned}
L_{\mathrm{nobg}} &= \mathrm{ImagineEdit}_{\mathrm{除背}}(L_0)\\
M_{\mathrm{subj}} &= \mathrm{clip}(L_{\mathrm{nobg}})\quad\text{（對除背圖扣，非 L0 peep）}\\
\mathrm{CLIP} &= L_{\mathrm{nobg}}\odot M_{\mathrm{subj}}\\
L_{\mathrm{empty}} &= \mathrm{ImagineEdit}_{\mathrm{除头}}(L_0)\\
M_{\mathrm{head}} &= \mathrm{kou}(L_0,L_{\mathrm{empty}})\\
\mathrm{plate} &= \mathrm{PATH1E}\big(\mathrm{face}(\mathrm{CLIP})_{\mathrm{native\,RATIO}},\,a8b\big)\\
R &= \mathrm{Imagine生}\big(L_{\mathrm{empty}},\,\mathrm{plate}|a8b\big)\ \text{只填洞}
\end{aligned}
\]

**反：** 除背↔有景；除頭↔有頭；CLIP↔\(M_{bg}\)；洞↔洞外不動；生@洞↔無洞 freeframe（錯教材）。

---

## 4. 權威鏈（不可跳）

```text
XNV2-0   讀 a8b 標準面（身份唯一）
XNV2-1   L0 freeze（中景／全幅構圖鎖）
XNV2-2   外力除背 → L_nobg → 扣 M_subj → CLIP   【禁自 peep】
XNV2-3   外力除頭 → L_empty → 扣 M_head → 真洞 SEAT 同框
XNV2-4   face@CLIP：native bbox RATIO；elev 僅 letterbox 最長邊
XNV2-5   PATH1E plate = Ref(pose@CLIP臉, a8b)  ※ 禁裸棚直 ECC
XNV2-6   外力生：base=L_empty，ref=plate|a8b，**只填洞**
XNV2-7   hardpaste 可選；洞外 outside=0
XNV2-8   反板：SRC | 自peep錯 | 無洞錯 | 有洞正回
XNV2-9   ERROR_TEXTBOOK 必出（至少一種錯）
XNV2-10  N>1：對 X 重複；STACK 越層返
```

---

## 5. RATIO 鐵律

| 禁 | 要 |
|----|-----|
| face_crop 硬 resize 成方 1:1 再 PATH1E | **保持 native w/h** |
| 方圖拉伸破骨相 | elev 時 **letterbox** 到 1024 最長邊 |
| peep 任意比例當 plate | plate 姿比 = CLIP 臉 bbox 比 |

---

## 6. 與 V1 / 外力反 V3

| 項 | 新畫女 V1 | 外力反 V3 | **新女畫 V2（定稿）** |
|----|-----------|-----------|------------------------|
| 身份 | a8b | 任意 | **a8b only** |
| 回位 | ECC 可 freeframe | 洞座 | **洞座 + a8b plate** |
| CLIP | MID crop 允許 | 禁自 peep | **除背扣 only** |
| RATIO | 未嚴 | — | **native + letterbox** |
| 錯例 | 無 | 必出 | **必出** |
| 多層 | 無 | 有 | **(N)(X) 正式** |

- 僅鎖身份、不強調返還 → V1 `STICK_XIN_HUA_NV`
- **改臉／升清再回 → 默認 `STICK_XIN_NV_V2`**

---

## 7. E 碼

| 碼 | 禁 | 治 |
|----|-----|-----|
| E-XHN-01..09 | V1 | 同 V1 |
| **E-XHN2-01** | 無洞 freeframe 嵌 a8b | 生 on 同框洞 |
| **E-XHN2-02** | 自 peep 冒充 CLIP／洞 | 外力除背／除頭扣 |
| **E-XHN2-03** | plate 後跳洞直貼全圖 | PATH1E 只入洞 |
| **E-XHN2-04** | (N)(X) 跳層不反 MARK | 每層洞可溯 |
| **E-XHN2-05** | 不存錯圖教材 | ERROR_TEXTBOOK |
| **E-XHN2-06** | face 硬拉 1:1 破 RATIO | native + letterbox |
| **E-XHN2-07** | 除背 freeframe 當同框 kou(L0) | M 自除背圖扣 |
| E-WLF3-01..04 | 外力反 V3 | 全繼承 |

---

## 8. 宣稱

| 級 | 條件 |
|----|------|
| C2_XIN_NV_V2 | a8b 可溯 · CLIP←除背 · 洞←除頭 · plate native RATIO · 生經洞 · 錯圖必出 |
| C3 | outside log + 眼白 + 越層 MARK |
| C5 / ACCEPT_FULL_HD | Gold+CI only · 不自動開 |

---

## 9. 金句

> **新女畫 V2：先鎖是誰（a8b），再鎖座位（洞），CLIP 從除背扣，plate 保 RATIO，只坐進洞。**  
> **(N)(X)：每一層 X 都是上一層洞的反件。**  
> **沒洞的改臉是創作；有洞的改臉才是新女畫·外力返。**  
> **自 peep 假洞 = 偷步；外力除扣 = 真四態。**

---

## 10. 狀態

`ACCEPT_FULL_HD=false`  
`production_claim=false`  
`implementation_status=constitution_v2_true_four_anti_ratio_locked`  
`canonical_name=新女畫V2`  
V1 保留；**返還任務默認 STICK_XIN_NV_V2**。
