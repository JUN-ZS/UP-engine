# SHQ · [(生,除,洞,扣)×(反)] 全專案定義 · 連動失敗架構重整（01448）

**formal:** `SHQ_FOUR_ANTI_ALGEBRA_ARCH_V1`  
**write_id:** `01448`  
**STICK:** `STICK_FOUR_ANTI_ARCH`  
**母憲:** `SHQ_EDIT_HOLE_FOUR_ANTI_DEBUG.md`（01386）· `docs/GROK_IMAGINE_FUNCTION_CODES.md` §19h–§19l  
**PY:** `shq_edit_hole_four_anti_debug.py`  
**範圍首刀:** **只先做頭（大咬）** — EDIT 四態 × 回位四態  
**ACCEPT_FULL_HD:** false · **production_claim:** false

---

## 0. 一句（咬物隱喻 = 硬契約）

```text
把一物「咬」出來  →  一定留下「洞」
把咬出的那塊「升清」→  再放回「洞」
若尺度/形/機位/α 同源  →  一定對得上
```

公式上：

\[
\boxed{
\text{RETURN}
=
\text{hardpaste}\big(
  \text{SRC},\;
  M_{\text{hole}},\;
  \text{scale\_lock}(\text{GEN}(\text{peep}_{M}))
\big)
\quad\text{s.t.}\quad
\text{out}[\neg M]=\text{SRC}[\neg M]
}
\]

**洞是形，除是態，扣是證，生是填；反是每一步的鏡子。**

---

## 1. 全專案字詞（唯一語義 · 來自 01386 + §19）

| 字 | 定義 | 反（必須成對） | 不是 |
|----|------|----------------|------|
| **生 GEN** | 只在洞內刷 HD RGB；座標系=SRC | 生前 peep ↔ 生後 elev | freeframe 特写主權 |
| **除 REMOVE** | EDIT 去掉目標（頭）→ L1 有背無頭 | 有頭 L0 ↔ 無頭 L1 | 手擦、假 empty |
| **洞 HOLE** | 剪影空位 \(M_{\text{hole}}\)（形，非矩形） | 洞 ↔ 反洞 \(1-M\) | peep 框、AABB |
| **扣 DIFF** | 同源同機位差分 Support(\|keep−remove\|) | 扣熱圖 ↔ 反查疊 SRC | 單圖猜邊 |
| **反 ANTI** | 每態必有正/對 | 有背↔無背、洞↔反洞、生前後 | 只生不查 |

### 1.1 代數結構（重整）

\[
\mathbf{F}
=
\{\text{生},\text{除},\text{洞},\text{扣}\}
\times
\{\text{正},\text{反}\}
\]

共 **8 格**（每態正+反），不是 4 個孤立 verb：

| | 正 | 反 |
|--|----|----|
| **除** | L1 無頭（EDIT） | L0 有頭 |
| **扣** | Diff 證洞 | Diff 反查（疊回是否吻合） |
| **洞** | \(M_{\text{hole}}\) | \(M_{\text{anti}}=1-M\) 洞外 bit-exact |
| **生** | 洞內 HD | 生後 peep 反生前 peep（鎖尺 ≤1.15） |

**接口不變量（Interface Invariants）** — 連動唯一准繩：

1. **同機位** L0/L1/EMPTY  
2. **同洞形** 全鏈共用一個 \(M_{\text{hole}}\)（或可證繼承）  
3. **同 bbox peep** 有背/無背同一洞框  
4. **elev_remap=false**  
5. **洞外 max_diff=0**  
6. **scale-lock** 生不改構圖主權  

任一方法若只在自己局部優化而打破 1–6，**獨立 PASS、串聯必錯**。

---

## 2. 兩層四態（你指定的先後）

### Layer A — EDIT 咬頭（大咬）

```text
A0  SRC freeze · RESET_DONOR
A1  除：EDIT 除頭 → L1
A2  扣：|L0−L1| → M_hole_head · 反洞
A3  peep_head @ 洞框（有背；可選無背同框）
A4  反查：有頭/無頭板 · 洞形對頭形
```

### Layer B — 升清回位（放回洞）

```text
B1  生：洞內 INPAINT 或 peep+HF 鎖尺（禁 freeframe 塞洞）
B2  hardpaste → RETURN
B3  反：RETURN vs SRC 洞外=0 · 洞內 NCC/觀感 · size_ok
B4  再反：peep_生後 vs peep_生前 尺度
```

**整條「頭」鏈 = A 的 [(生,除,洞,扣)×反] 接 B 的 [(生,除,洞,扣)×反]**  
注意：A 層「生」可暫空（只咬不升）；B 層「除/扣」可複用 A 的 L1/M，**禁止重開一套洞**。

---

## 3. 核心問：為何「每個方法獨立成功，組起來連動就錯」？

### 3.1 根因一張表

| 獨立成功時量的是… | 連動需要的是… | 斷點 |
|------------------|---------------|------|
| 本方法輸出「看起來對」 | 下一方法輸入契約 | **無 interface schema** |
| PASS_C2 幾何/自測 | PASS_RESTORE 全鏈像素 | **宣稱級別偷換** |
| 自己的 mask/scale | 上游凍結的 M/peep | **重算洞 / 重取 peep** |
| freeframe 很清 | 洞框同構 | **W3/W5 偷步** |
| 爆炸/教學板漂亮 | home corners 回位 | **教學位當回位位** |
| densify 高清 | scale-lock peep 主權 | **構圖主權漂移** |
| SOLO band 有色 | 理解 peep 真像素 | **色帶當 donor** |
| 單 skill 金閘 | 跨 skill 不共享 state | **無 RUN 狀態總線** |

### 3.2 架構名：偽組合（Pseudo-Composition）

```text
獨立 PASS  ≠  可組合
可組合     ⇔  共享 State Bus + 不變量 1–6 + 同宣稱級
```

**State Bus（連動必須寫入同一 RUN）：**

| key | 誰寫 | 誰讀 | 禁 |
|-----|------|------|-----|
| `SRC` / `L0` | freeze | 全鏈 | 中途換 SRC |
| `L1_remove` | 除 | 扣/生 | 另一角度重除 |
| `M_hole` | 扣 | 生/貼/反 | 下游另猜 mask |
| `peep` + `bbox` | 洞框裁 | 生/鎖尺 | freeframe 替 peep |
| `elev` / `HD` | 生 | hardpaste | elev_remap |
| `RETURN` | paste | 反查 | soft alpha 糊洞外 |
| `ANTI_boards` | 每態反 | DEBUG | 省略反 |

### 3.3 連動失敗的典型「假成功」

1. **方法 A PASS**（除頭漂亮）→ **方法 B PASS**（HD 頭漂亮）→ 貼回：**頭變大/錯位**  
   → 因 B 沒用 A 的 \(M\) 與 peep 尺度（W3+W5）。  
2. **L1 GENERIC PASS** + **S2 chain=0 PASS** + **合眾 PASS** → 人臉爛  
   → 幾何閘 ≠ 還原閘（PASS_C2 ≠ PASS_RESTORE）。  
3. **機炸回 EXPLODE PASS** + **hardpaste PASS** → 件漂  
   → explode 位被當 home（E-JZH-04）。  
4. **四態各板都有** 但 **反未做** → 無法發現洞外污染。

### 3.4 重整後的組合律

```text
compose(f, g) 合法  ⇔
  out(f) ⊇ InterfaceRequired(g)
  ∧ invariants(f) ⊆ invariants(g) 可繼承
  ∧ claim_level(f) 不高於 鏈宣稱
  ∧ RESET_DONOR 僅在鏈頭
```

**禁止：** 把「獨立 selftest PASS」自動 OR 成「全鏈 SUCCESS」。

---

## 4. 架構脈絡圖（不斷重整用）

```text
                    ┌─────────────────────────────┐
                    │  STATE BUS (one RUN dir)    │
                    │  SRC L1 M peep elev RETURN  │
                    └─────────────┬───────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
    ┌────▼────┐             ┌─────▼─────┐            ┌─────▼─────┐
    │ Layer A │ 咬頭 EDIT   │ Layer B   │ 升清回位   │ Layer C*  │ 分件/合眾
    │ 除扣洞反│             │ 生貼反    │            │ 機炸/回車 │
    └────┬────┘             └─────┬─────┘            └─────┬─────┘
         │                        │                        │
         └──────────[(生除洞扣)×反] 每層自洽 + 繼承 M/peep ──┘

* C 層（機炸回 / 回車大炮 / 新畫女）= 多洞或多主體；
  每一 leaf 仍必須是「一小咬」= 同一四態代數。
  先鎖頭（大咬），再複製到件。
```

**進化釘順序（重整）：**

1. 字詞鎖（01386）  
2. 頭鏈 A→B 四態（本 write）  
3. 單件 peep 四態（機炸 SOLO）  
4. 多件 MULTI_RETURN  
5. 三主體回車大炮  

不可 5 未穩卻用 1 的 PASS 宣稱 5。

---

## 5. 頭（大咬）最小可跑清單

| 步驟 | 產物 | 反查 |
|------|------|------|
| 1 凍 SRC | L0 | — |
| 2 EDIT 除頭 | L1 | L0↔L1 板 |
| 3 扣 | M_hole_head | 洞疊頭緣 |
| 4 peep | peep_head | 同 bbox |
| 5 生（鎖尺） | elev_head | 生前↔生後面積 |
| 6 hardpaste | RETURN | 洞外 diff=0 |
| 7 DEBUG | REPORT | Q1–Q9 |

**成功定義（頭鏈）：**  
`outside_max_diff==0` ∧ `grow≤1.15` ∧ `M` 來自扣非手畫 ∧ 反板齊。

---

## 6. 與全專案總稱的介面

| 總稱 | 與四態關係 |
|------|------------|
| 換涯人 | 人崖 peep = 一咬一洞一回 |
| 機炸回 | 每 SOLO = 一咬；爆炸只教學 |
| 回車大炮 | 三主體 × 每 leaf 四態 |
| 新畫女 | 臉 ROI 亦應走洞內生，禁裸棚直 ECC 冒充 peep |
| 合眾 MULTI | N×(咬→升→回) 共享 EMPTY |

---

## 7. E 碼（連動）

| 碼 | 名 | 治 |
|----|-----|-----|
| E-FA-01 | SOLO_PASS_AS_CHAIN | 禁獨立 PASS 冒充全鏈 |
| E-FA-02 | RECOMPUTE_HOLE_DOWNSTREAM | 繼承 M_hole |
| E-FA-03 | FREEFRAME_STEAL | 洞內生 / 鎖尺 |
| E-FA-04 | CLAIM_LEVEL_SWAP | C2≠RESTORE |
| E-FA-05 | EXPLODE_AS_HOME | home corners only |
| E-FA-06 | SKIP_ANTI | 每態反板 |
| E-FA-07 | MULTI_HOLE_BEFORE_HEAD | 先頭鏈 |

---

## 8. 金句

> **獨立成功只證明局部閘；連動成功才證明洞與咬同構。**  
> **先咬頭、證洞、升清、放回；再談件、再談三車。**  
> **[(生,除,洞,扣)×(反)] 是狀態代數，不是四個互不往來的按鈕。**

---

## 9. 狀態

implementation: **architecture constitution**（本 write）  
next: 頭鏈 A→B 實跑（EDIT 除頭 + 四態反 + 回位）· 用新圖  
ACCEPT_FULL_HD=false
