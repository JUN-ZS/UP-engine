# SHQ_EDIT_HOLE_FOUR_ANTI · 字詞定義 · DEBUG · PY 對應（01386）

**formal:** `SHQ_EDIT_HOLE_FOUR_ANTI_DEBUG_V1`  
**功能碼:** `docs/GROK_IMAGINE_FUNCTION_CODES.md` §19l  
**調用 PY:** `shq_edit_hole_four_anti_debug.py`  
**LOCK:** `CONSTITUTION_LOCK_01386.json`  
**原則:** 質問 **DIAG/WARN 默認不阻運行**；僅 `--strict` 或 production ACCEPT 閘才 BLOCK。

---

## 0. 為何有這份憲

反覆走錯的根因不是「不會算公式」，而是：

1. **字詞未鎖** → 洞／框／peep／freeframe 混用  
2. **態未分** → 除、扣、生偷換成同一張圖  
3. **反未做** → 有頭/無頭、有背/無背沒有成對差分  
4. **尺度未鎖** → 生成級 densify 把頭做成特寫再塞回 → **頭變大**

本憲把字詞、走錯路徑、正確四態、PY 對應、可調試質問一次寫死。

---

## 1. 字詞表（GLOSSARY）· 必須同一語義

| 字詞 | 定義（唯一） | 不是 |
|------|-------------|------|
| **SRC / L0** | 原圖凍結；有背·有頭 | 升清後圖 |
| **除 (REMOVE)** | Imagine EDIT 去掉目標部件（如頭）→ **L1 有背無頭** | 手擦、假 empty |
| **洞 (HOLE)** | 目標在 SRC 上的**剪影空位** `M_hole`（形狀，非矩形） | peep 矩形框、BBox |
| **反洞** | `M_anti_hole = 1 - M_hole`；洞外必須 bit-exact | soft mask |
| **扣 (DIFF)** | 兩張**同源同機位**圖差分：`Support(\|I_keep−I_remove\|)` | 單圖 peep 猜邊 |
| **生 (GEN)** | **只在洞內**生成／升清 RGB；座標系 = SRC | freeframe 整頭特写 |
| **反 (ANTI)** | 每態必有正/反對：有頭↔無頭、有背↔無背、洞↔反洞、生前↔生后 | 只生不反查 |
| **有背 / 無背** | 場景背景保留 vs EDIT 除背；**同一洞框 bbox** | 無背時允許頭放大 |
| **peep** | 洞框 bbox 裁出的小圖；**尺度契約載體** | freeframe donor |
| **clip / M_clip** | 真正可編輯硬剪影 α∈{0,255} | feather 邊 |
| **freeframe** | 生成器自定構圖／尺度／特写 | 洞內同構 INPAINT |
| **scale-lock 鎖尺** | 生後 content 面積 ≤ peep×1.15；wh 綁洞框 | densify 可改構圖 |
| **偷步 (STEAL)** | 扣洞 與 生 斷開：另生 freeframe 再 map 塞洞 | 洞內 INPAINT |
| **RESET_DONOR** | 新鏈禁止沿用舊 freeframe densify map 當 HD 位姿主權 | 可作材質 HF 源（鎖尺後） |
| **硬貼 hardpaste** | `out=SRC; out[M_hole]=HD[M_hole]`；洞外 max_diff=0 | alpha 混合糊邊 |
| **elev_remap** | 升清後改 corners／位姿 → **必須 false** | 用 warp 救對位 |
| **DEBUG_QA** | 逐步質問紀錄；**默認 DIAG 不阻跑** | 當 ACCEPT 的唯一門（需 --strict） |

### 四態一句

```text
洞 = 空位形狀（mask）
除 = 無頭狀態圖（EDIT）
扣 = 有頭/無頭 差分 → 證洞
生 = 只在洞內刷 HD RGB
反 = 以上每一態都有成對反查
```

---

## 2. 走錯過程（WRONG PATH）· 精煉

| ID | 走錯 | 表面像對 | 真傷 | 正解 |
|----|------|----------|------|------|
| W1 | 矩形 peep 當洞 | 有框 | 無剪影 | 扣/色相 → M_hole |
| W2 | 外框 reverse 當鏤空 | 有「洞」字 | 矩形空，非頭形 | 剪影對剪影 |
| W3 | freeframe densify 當 donor | 很清晰 | **頭變大**、姿漂 | 鎖尺：HF 注入 peep |
| W4 | 無背 peep 另裁放大 | 乾淨底 | 與有背尺度分裂 | 同 bbox 有背/無背 peep |
| W5 | 扣完另開 freeframe 再 map | 有「生」 | 偷步錯位 | 洞內 INPAINT 或 peep 鎖尺 HF |
| W6 | ROI 邊弱心強當生產 | 邊不跳 | 盔緣留低清 | 全洞 w=1（尺度已穩時） |
| W7 | 用 A 閘 ACCEPT B 路徑 | 有 PASS | 跨模型驗收 | 同候選同閘 |
| W8 | 舊 donor 不 RESET | 快 | 失憶混鏈 | RESET_DONOR 每新鏈 |
| W9 | DEBUG 全 BLOCK 無法跑 | 嚴 | 迭代死 | 質問 DIAG；strict 才阻 |
| W10 | 手剪影主路徑 | 像 mask | 非 EDIT 認邊 | EDIT 除/色相魔棒優先 |

**01384 實例：** peep densify → 1408 特写 → 塞洞 → 頭變大 → **W3+W5**。  
**01385 修正：** 洞框 peep 鎖尺 + densify 只供 HF + 四態反查。

---

## 3. 正確鏈（RIGHT PATH）

```text
S0  SRC freeze + RESET_DONOR
S1  除背 / 除頭 / 色相   → L 層（EDIT 原生）
S2  扣：有頭反無頭（有背+無背）→ M_hole · 反洞
S3  peep_有背 / peep_無背 @ 同一洞框 bbox
S4  生：
      (a) 洞內 INPAINT @ L1/色相洞，或
      (b) densify 僅 HF → scale_lock_map 進 peep（禁構圖主權）
S5  hardpaste · 洞外 bit-exact · elev_remap=false
S6  反查：生前↔生后 · SRC↔return · size_ok
S7  DEBUG_QA 落盤（默認不阻）
```

---

## 4. PY 對應表（可調用）

| 字詞/步驟 | 模組 | 職責 |
|-----------|------|------|
| 總 DEBUG / 字詞 / selftest | **`shq_edit_hole_four_anti_debug.py`** | glossary · QA · scale gate · 四態反 |
| 一生一除差分 clip | `shq_edit_pair_differential_clip.py` | EDIT pair → M_hole |
| clip elev return | `shq_clip_mask_elev_return.py` | 凍 clip 升清回位 |
| pair reverse | `shq_clip_mask_pair_reverse.py` | reverse 配對 |
| material fill 凍 alpha | `shq_material_fill.py` | 只刷 RGB |
| native hardpaste 驗 | `shq_native_alpha_audit.py` / `verify` 路徑 | 洞外不變 |
| 功能碼全文 | `docs/GROK_IMAGINE_FUNCTION_CODES.md` §19h–§19l | 契約 |
| Imagine EDIT | Grok `image_to_image` / `reference_to_image` | 除背除頭色相 INPAINT |
| 合眾主鏈 | `shq_eval_pipeline.py` | 不替代本洞鏈 |

```bash
# 可調用測試
python3 shq_edit_hole_four_anti_debug.py selftest
python3 shq_edit_hole_four_anti_debug.py glossary
python3 shq_edit_hole_four_anti_debug.py qa-template --out $RUN
python3 shq_edit_hole_four_anti_debug.py check-size --peep $PEEP --densify $DENS --hole-wh W,H
python3 shq_edit_hole_four_anti_debug.py anti-diff --keep $L0 --remove $L1 --out $RUN
python3 shq_edit_hole_four_anti_debug.py scale-lock-map --peep $PEEP --densify $DENS --alpha $A --out elev.png
python3 shq_edit_hole_four_anti_debug.py run-diag --run $RUN   # 質問落盤，exit 0
python3 shq_edit_hole_four_anti_debug.py run-diag --run $RUN --strict  # 失敗才非0
```

---

## 5. DEBUG 質問（留有質問 · 不阻運行）

每條：`status ∈ {PASS, WARN, FAIL, SKIP}`  
- 默認 `run-diag`：**FAIL→WARN 寫入**，進程 **exit 0**  
- `--strict`：FAIL → exit 2（給 CI / ACCEPT 前）

| ID | 質問 | PASS | 默認 |
|----|------|------|------|
| Q0 | RESET_DONOR 聲明？ | true | WARN if missing |
| Q1 | 有 L0 與 L1（除）？ | 雙圖存在 | WARN |
| Q2 | 扣是否同源同機位？ | phase/NCC 背景穩 | WARN |
| Q3 | M_hole 是剪影非整框？ | area/bbox < 0.85 | WARN |
| Q4 | 有背/無背 peep 同 bbox？ | xywh 相等 | WARN |
| Q5 | 生是否鎖尺？ | grow≤1.15 | WARN（strict 可 FAIL） |
| Q6 | 是否偷步 freeframe map？ | 無獨立 freeframe donor 主權 | WARN |
| Q7 | 洞外 max_diff？ | 0 | WARN |
| Q8 | elev_remap？ | false | WARN |
| Q9 | 反查板是否落盤？ | ANTI board 存在 | SKIP ok |

**禁止：** 用質問代替幾何閘去「開 ACCEPT_FULL_HD」。ACCEPT 仍走既有 evaluate_gates。

---

## 6. E 碼（本域）

| 碼 | 名 | 默認 | strict |
|----|-----|------|--------|
| E-99 | RESET_DONOR_VIOLATION | WARN | BLOCK |
| E-100 | HOLE_GENERATE_STEAL | WARN | BLOCK |
| E-105 | HEAD_SCALE_GROW | WARN | BLOCK |
| E-106 | FREEFRAME_PEEP_AS_HOLE | WARN | BLOCK |
| E-107 | ANTI_PAIR_MISSING | WARN | WARN |
| E-108 | DEBUG_QA_INCOMPLETE | SKIP/WARN | WARN |

---

## 7. 金句

> **洞是形，除是態，扣是證，生是填；反是每一步的鏡子。**  
> **頭不得因無背或 densify 變大；尺度在洞框 peep，清晰在 HF。**  
> **質問為燈，不為牆——除非 --strict 或 ACCEPT。**

---

## 8. 狀態

`ACCEPT_FULL_HD=false`（本憲只鎖 DEBUG/字詞/PY，不開 FULL HD）  
金診斷跑次：`FOUR_ANTI_HOLE_01385` · `GO_HOLE_INPAINT_REF_01384`（反例）
