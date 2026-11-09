# SHQ · 外力反 V2.1 · 任意物件 · 可微調結構（01469）

**formal:** `WAI_LI_FAN_V2_ANY_OBJECT_TUNE_V1`  
**zh:** **外力反 V2.1**（任意物件 · 微調即適配）  
**STICK:** `STICK_WAI_LI_FAN_V2`（升格）· 綁 `STICK_WAI_LI_GROK` · `STICK_FOUR_ANTI_ARCH`  
**母:** `SHQ_FOUR_ANTI_ALGEBRA_ARCH.md`（01448）· `SHQ_TRUE_FOUR_ANTI_CLIP.md`（01457）· `SHQ_WAI_LI_GROK.md`（01466）  
**PY:** `shq_wai_li_fan_v2_any_object.py`  
**法:** `docs/GROK_IMAGINE_FUNCTION_CODES.md` §19 + §22  
**ACCEPT_FULL_HD:** false

---

## 0. 你問的三件事（先答）

### 0.1 為何公式 PY 通過不了「另一類型」的圖？

| 舊 V2 隱性假設 | 換圖型就炸 |
|----------------|------------|
| 目標 = **人頭／機甲頭**（上半、左/右半空間先驗） | 肩甲／齒輪／整機／遠景小頭／多主體 → ROI 錯 |
| `kou` 取 **最大 CC** | 雙機、大背光漂移 → 洞吞全身 |
| **CLIP = peep bbox 裁** | 自 peep；不是除背扣；邊假、層不可反 |
| thr/morph **寫死** | 亮棚 vs 暗廠、近 vs 遠 差分量級不同 |
| 狀態總線只記「頭鏈」 | 任意 part_id 無法微調繼承 |
| 獨立 selftest 用假 L1 | 真 Imagine 資產分布不同 → 組合律崩 |

**一句：** 舊公式把「某一類圖的參數」寫成「代數本身」——換類型不是代數錯，是**類型參數沒外置**。

### 0.2 為何每個方法獨立成功，組起來連動就錯？

```text
獨立 PASS  = 局部閘（看起來對 / 本模組自測）
連動 PASS  = 接口不變量 1–6 全繼承 + 同一 State Bus + 同宣稱級
```

| 獨立成功量的是… | 連動需要的是… | 斷點名 |
|----------------|---------------|--------|
| 本步輸出好看 | 下一步輸入契約 | **無 Interface Schema** |
| 自己重算 mask | 上游凍結 M / MARK | **E-FA-02 下游重開洞** |
| freeframe 很清 | 同洞同尺 peep/CLIP | **E-FA-03 / E-WLG-04** |
| peep 裁得很準 | **除背 → M_subj CLIP** | **自 peep 冒充 CLIP** |
| PASS_C2 幾何 | PASS_RESTORE 洞外=0 | **E-FA-04 宣稱偷換** |
| 單 skill 金閘 | 跨 skill 共享 bus | **偽組合 Pseudo-Composition** |

> **獨立成功只證明局部閘；連動成功才證明洞與咬同構。**  
> 組錯 = 把 4 個成功動詞當按鈕亂接，沒有 [(生,除,洞,扣)×(反)] 的**狀態代數**。

### 0.3 真能力（不只頭 · 任意物件）

```text
若把 (N) 層各自當 (X) 層：
  每層外力GROK 除背 → 扣 → CLIP MASK（M_subj）
  每層外力GROK 除件 → 扣 → 洞 MASK（M_part）· MARK
  生只在洞 · 回經 MARK · 反每態
  子層 L0 = 父層 CLIP（真像素 ⊙ M），不是自 peep bbox
```

**物件** = 頭 / 肩甲 / 齒輪組 / 整人 / 整機 / 任意 part_id —— 同一代數，只換：

- `part_id`（語義）
- `roi_hint`（可選粗框，**非**自 peep 主權）
- `thr` / `morph` / `cc_policy`（微調）
- Imagine 除件 prompt 的目標名詞

---

## 1. [(生,除,洞,扣)×(反)] 全專案定義（任意物件）

### 1.1 字詞（類型無關）

| 字 | 定義（任意物件） | 反 | 禁冒充 |
|----|------------------|-----|--------|
| **除** | 外力GROK 去掉 **目標物件** 或 **背景** | 有物件 L0 ↔ 無物件 L1；有景 ↔ 除背 | OpenCV 假除 |
| **扣** | 同源同機 \|L0−L_edit\| 證變區 | 熱圖疊回驗 | 單圖猜邊當主權 |
| **洞** | 除件後的空位形 \(M_{\mathrm{part}}\) + MARK 座位 | 洞外 bit-exact | 手塗／無除的洞 |
| **生** | 只在洞內填 HD（外力GROK） | 生前後鎖尺 | freeframe 當生 |
| **CLIP** | **除背** 後 \(M_{\mathrm{subj}}=kou/clip\)，\(\mathrm{CLIP}=L\odot M\) | \(M_{\mathrm{bg}}\) | **自 peep bbox** |
| **反** | 每態正對板 | 缺反 = 假成功 | 省略反板 |

### 1.2 代數

\[
\mathbf{F}=\{\text{生},\text{除},\text{洞},\text{扣}\}\times\{\text{正},\text{反}\}
\quad+\quad
\{\text{CLIP}_{\text{除背}}\}
\]

公式（任意 part）：

\[
\begin{aligned}
L_{\mathrm{除件}} &= \mathrm{ImagineEDIT}_{\mathrm{remove}}(L_0,\ \mathrm{part}) \\
L_{\mathrm{除背}} &= \mathrm{ImagineEDIT}_{\mathrm{removeBG}}(L_0) \\
M_{\mathrm{part}} &= \mathrm{kou}(L_0,L_{\mathrm{除件}};\ \theta) \\
M_{\mathrm{subj}} &= \mathrm{clip\_from\_chu\_bei}(L_{\mathrm{除背}};\ \theta) \\
\mathrm{CLIP} &= L_0 \odot M_{\mathrm{subj}} \\
I_{\mathrm{HD}} &= \mathrm{ImagineEDIT}_{\mathrm{birth}}(L_{\mathrm{除件}},\ \mathrm{refs})\ \text{only in hole} \\
\mathrm{RETURN} &= \mathrm{hardpaste}(L_0,\ M_{\mathrm{part}},\ I_{\mathrm{HD}}) \\
&\quad \mathrm{s.t.}\ \mathrm{out}[\neg M]=L_0[\neg M]
\end{aligned}
\]

\(\theta\) = **微調包**（thr, morph, cc_policy, roi_hint, min_frac, max_frac）—— **換圖型只改 \(\theta\)，不改代數**。

### 1.3 接口不變量（連動准繩 · 任意物件）

1. 同機位 L0 / L_除件 / L_除背  
2. 同洞形 \(M_{\mathrm{part}}\) 全鏈繼承（禁下游重猜）  
3. 子層 L0 = 父 **CLIP**（除背扣），**禁**自 peep 冒充  
4. elev_remap=false · scale-lock  
5. 洞外 max_diff=0  
6. 除/生必有 外力GROK asset_id  

### 1.4 (N)×(X) 層

```text
X=0 ROOT:  除背→CLIP_0 · 除件→洞_0 · 生回_0
X=1:       L0_1 := CLIP_0 的子域 或 對 CLIP_0 再除件
           再 除背?（若子層仍有「底」）/ 除件 → 洞_1 → 生
STACK:     子 RETURN 經 父 MARK 反扣 → 根
```

每一 X：**完整四態 + 反**；洞鑰 = 該層 MARK。

---

## 2. V2 → V2.1 結構差（微調就能）

| | V2 舊 | **V2.1** |
|--|-------|----------|
| 物件 | 隱式頭 | **part_id 任意** |
| CLIP | peep 裁 | **外力除背 → M_subj** |
| 洞 | 最大 CC + 頭空間先驗 | **kou(θ) + 可選 roi_hint** |
| 參數 | 寫死 | **TunePack JSON 外置** |
| 換圖 | 改代碼 | **只改 θ / part prompt** |
| 執行器 | 口頭 Imagine | **外力GROK 硬綁** |

### TunePack（微調包）示例

```json
{
  "part_id": "left_helmet | right_gear | shoulder | whole_mecha | face | ...",
  "thr": 22,
  "thr_range": [14, 32],
  "morph_open": 5,
  "morph_close": 13,
  "cc_policy": "largest_in_roi | score_area_center | union_top_k",
  "roi_hint_xyxy_norm": null,
  "min_frac": 0.005,
  "max_frac": 0.35,
  "elev_scale": 2,
  "require_chu_bei": true,
  "require_imagine_assets": true
}
```

遠景小頭：`thr↓` · `min_frac↓` · `roi_hint` 給粗位。  
雙機大光變：`cc_policy=score` + roi。  
整機：`part_id=whole` · 除件=除整主體 · max_frac 放寬。

---

## 3. 為何「頭公式」過不了「機甲齒輪／遠人／多主體」

```text
頭公式成功  ⇏  物件代數成功
頭公式 = 代數 ⨯ θ_head
齒輪圖   = 代數 ⨯ θ_gear   ← 你若仍塞 θ_head → PY「不通過」
```

**不是四態錯，是 θ 與 CLIP 路徑錯。**

---

## 4. E 碼（V2.1 增）

| 碼 | 禁 |
|----|-----|
| E-WLF21-01 | 自 peep 當 CLIP |
| E-WLF21-02 | 無除背資產卻報 CLIP |
| E-WLF21-03 | 頭先驗寫死無法 part_id |
| E-WLF21-04 | 換圖改代數而非改 θ |
| E-WLF21-05 | 獨立 PASS 冒充全鏈 |
| E-WLF21-06 | 下游重算 M_part |
| E-FA-* / E-WLG-* | 同前（繼承） |

---

## 5. 金句

> **四態是代數；θ 是圖型；CLIP 是除背扣出來的，不是裁出來的。**  
> **獨立成功 ≠ 可組合；可組合 ⇔ State Bus + 不變量 + 外力GROK。**  
> **任意物件：同一 [(生,除,洞,扣)×(反)]，只換 part 與 θ。**

---

## 6. 狀態

`implementation_status=constitution + PY V2.1`  
write **01469** · 取代舊 peep-as-CLIP 默認  
