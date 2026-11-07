# SHQ 四技能宣稱契約（write 01397）

> 洞只界定「哪裡可以改」，不規定「用甚麼方法生成高清內容」。  
> INPAINT 降級為可選；主鏈 = **A SR → B Material → C Detail → D Alpha Guard**。

## 公理

| ID | 內容 |
|----|------|
| AX-HOLE | 洞 = 可改區域；方法由 Router 狀態選擇 |
| AX-01380 | 凍結幾何邊界，不凍結洞邊解析度；禁止 feather 冒充 |
| AX-FREQ | \(RGB = L_{base} + M_{material} + H_{detail}\)；\(α = α_{orig,4×}\) |
| AX-D | Skill D 是 A/B/C 共同不變條件，不是可選風格 |
| AX-INPAINT | INPAINT ≠ 主升清；不得一人分飾 A/B/C/D |

## 四技能

| 鍵 | method_id | 負責 | 禁止 |
|----|------------|------|------|
| **A** | `SKILL_A_NEURAL_SR_BASE_4X` | 真升像素 / L_base | 改輪廓、α、姿態；Lanczos 冒充 |
| **B** | `SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN` | 凍 α 內材質 RGB / M | 決定輪廓/位置/尺度 |
| **C** | `SKILL_C_MULTISCALE_DETAIL_SYNTHESIS` | 微細節層 / H residual | 重畫整件、修外形 |
| **D** | `SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD` | M_hole、α_xor=0、洞外 bit-exact | 被跳過；soft-α 瞞錯 |

## 執行序（升清內容鏈）

```
S0 EDIT 四向 → M_hole SHA
S1 Geometry Lock (4× 座標)
S2 Skill A  → L_base
S3 Skill B  → M_material
S4 Skill C  → H_detail
S5 Skill D composite（硬 α）
S6 Reverse QA（失敗退回對應層）
S7 Independent ACCEPT
```

## 狀態 → 技能（Router）

| 狀態 | 優先 | 封鎖 |
|------|------|------|
| 形態清但像素少 | A → B | — |
| 材質糊、缺質感 | B → C | — |
| 網絲/裂紋/接縫缺 | C2 → C | — |
| **外形本身錯** | 回 EDIT/OTL0 | **A/B/C** |
| 高頻噪點過多 | C3 降 H | 動幾何 |

## 宣稱等級（Claim Level）

| Level | 可宣稱 | ACCEPT_FULL_HD |
|-------|--------|----------------|
| C0 | 只寫了規約／選了 method | false |
| C1 | D 幾何鏈 DIAG | false |
| C2 | A + backend log | false |
| C3 | A+B 或 densify under D + 消融 L vs L+M | false |
| C4 | L+M+H 可獨立控制／回退 | false |
| **C5** | Gold+CI 全閘 | **true（唯一）** |

### 可宣稱 vs 不宣稱（摘要）

**可：** 分層產出、α 不變、洞外 bit-exact、某 skill 有 adapter 收據、消融板。  
**不可：** 無後端仍稱 gen-level；INPAINT=主鏈；feather=鎖邊；DIFF=edit_permission；下採樣=原生 4×。

## 與 PR#12 / Agent Driver

- PR#12：規約 + fossils（`shq_4skill_frequency_layer_engine.py`）  
- 執行：`route_skill_by_state` + `shq_agent_driver` + Registry  
- **Skill D 永遠是 A/B/C 共同閘**，不是四選一裝飾

## 禁止清單（失憶）

- INPAINT 同時負責 A+B+C+D
- feather / soft-alpha 冒充邊界正確
- Lanczos+unsharp 冒充 gen-level / Skill A
- 無 backend adapter log 宣稱 gen-level detail
- DIFF mask 自動授予 edit_permission
- coverage 高但 peep 幾乎全圖 → outside_diff 假 PASS
- 用 A 方案腳位結果簽 B 方案 ACCEPT（cross-model acceptance）
- 把 delivery 下採樣圖宣稱未修改原生 4×
- 外形錯仍跑 DETAIL 補救
- 邊界低清保護區（違反 01380）

---
*write_id {WRITE} · asof {ASOF}*
