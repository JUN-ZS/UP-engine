# SHQ AI 使用引導（給另一個 AI Agent）

**Audience:** 任何要跟進／實作／驗收「物件導向幾何約束升頻」嘅 AI agent  
**Normative contract:** [`SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md)  
**Latest source:** [`sources/gemini-share-XMyk6HVn2J9S/`](./sources/gemini-share-XMyk6HVn2J9S/)（**20 turns**；+1 vs nutr：戰場自身部件追溯／生除扣洞反 + 方法一對一追溯）  
**Prior sources:** [`nutrRjsw676R`](./sources/gemini-share-nutrRjsw676R/)（19）、[`hC9HlUpskKK9`](./sources/gemini-share-hC9HlUpskKK9/)（17）、[`47yxULPlPy0W`](./sources/gemini-share-47yxULPlPy0W/)（15）  
**Fossils:** [`../research/shq_v9/`](../research/shq_v9/) — **唔係** production runtime（×10）

---

## 0. 對上一包（nutr）新增咗咩

| 項 | 內容 |
|----|------|
| Turn 19 新測 | 複雜人機**戰場圖**：`生→除→扣→洞→自身高清部件三層升級→01380 硬邊回位→反` |
| 新化石 | `shq_battlefield_self_part_traceability_engine.py` |
| 追溯硬規 | 每階段必須 **同一 `method_id` → 同一 `entrypoint` → 同一 `test_id` → 同一 `acceptance_gate_id`**（一對一；唔可以「方法表有、程式另一套」） |
| 宣稱 | 可宣稱「大圖由**自身**高清部件升級組成回去」——前提係上述追溯 + S7 磁碟反扣全 PASS；否則屬越權宣稱 |

nutr 已有、本包延續（務必保留）：**嚴格宣稱邊界**、**Anti-Tautology**、**五參數分離（含 `delivery_transform`）**、**Rule 01380**、**三頻率層 \(L+M+H\)**、**四技能 A/B/C/D（INPAINT 降級）**。

---

## 1. 必讀順序（Read order）

嚴格跟呢個次序；唔好一開始就開 fossil Python「照抄當 production」。

1. **[`SHQ_INDEX.md`](./SHQ_INDEX.md)** — 地圖、sibling PRs、邊份 doc 係契約  
2. **[`SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md)** — 階段閘門、禁令、模組對位（**權威**）  
3. **本檔** — 執行 checklist 同回報格式  
4. **最新 Gemini 源** — `sources/gemini-share-XMyk6HVn2J9S/EXTRACT.md` → `Gemini-完整對話.md`（尤其 **Turn 17–19**：宣稱／頻率層／戰場追溯）  
5. **`research/shq_v9/`** — 設計化石／實驗日誌；對照契約睇，**禁止**把 Lanczos／CLAHE 路徑當可交貨後端

讀完先動手改 code／開 runner／寫驗收。

---

## 2. 一句意圖（唔好偏題）

> 先 **鎖死每個物件嘅幾何**，再喺契約內排 tile／做真生成升頻；**唔係** 加大 tile、Lanczos 銳化、軟 alpha、補邊、或假 inpaint 扮生成。

參數硬分離（**五個**）：

\[
\text{model\_scale}\ne
\text{object\_transform}\ne
\text{tile\_size}\ne
\text{tile\_context}\ne
\text{delivery\_transform}
\]

- Siax 嘅 `model_scale` 係固定 4×；加大 `-t` **唔等於** 物件變大。  
- 下採樣交付圖必須標 `delivery_resampled_…_NOT_unmodified_native_4x`——**唔好宣稱**係「未修改原生 4× 母本」。

---

## 3. 硬閘門／禁止做法（Hard gates）

見到下面任何一項出現喺 **production path** → **BLOCK**，唔好「先交再說」：

| # | Forbidden | Why |
|---|-----------|-----|
| 1 | Lanczos / `INTER_LANCZOS4` + CLAHE + unsharp（或 Gaussian residual）當「generative upscale」 | 假生成；fossil 早期有，已入憲禁止 |
| 2 | 無 Siax / NCNN / Comfy / Imagine 呼叫，卻宣稱 gen-level detail | 必須有真實 backend adapter log |
| 3 | Soft-alpha / feather 掩飾錯位／疊影 | 幾何鎖失敗唔可以用合成瞞 |
| 4 | RETURN 鏈水平翻轉／鏡像貼 | 憲法級 fail（`E_HORIZONTAL_FLIP…`） |
| 5 | Halo／context 雙重貼入 master | 只保留每 tile 嘅 **core** |
| 6 | 用 `INTER_AREA` 縮小預覽「證明」bit-exact | 驗收要用原生像素／契約區 |
| 7 | 根因 mask 錯仲用 inpaint／補邊／亂圈修 | 必須重生 **CLIPPING MASK REVERSE** |
| 8 | `tile_size` 改變 `object_transform` | 參數角色混亂 |
| 9 | empty-BG／DNA 公式變咗仲用舊 polygon donor | 全鏈作廢，由根重生 |
| 10 | 自創 Siax／Lanczos「捷徑」繞過 S0–S7 | **Do not invent shortcuts** |
| 11 | **Rule 01380 違反**：把洞邊留低清／`interior_core` 內縮／Feather 冒充邊界 | 洞內每點都係合法升清範圍；凍結嘅係**邊界幾何**，唔係邊界附近解析度 |
| 12 | **同義反覆（Tautology）**：`m_hole vs m_hole` IoU=1.0、複製源 Alpha 當幾何證明 | 必須有獨立參考（如 GrabCut／磁碟反扣）且 `is_self_comparison_tautology=False` |
| 13 | **越權宣稱**：Registry／追溯鏈未對齊仍宣稱「自身部件升級組成大圖」 | 見 §5 嚴格宣稱邊界 |
| 14 | `DIFF` 差異遮罩自動當 `edit_permission=True` | 必須經 S3 人工核實 |
| 15 | 方法表、程式、測試、驗收 ID **唔一一對應** | 見 §5.3 追溯硬規 |

---

## 4. 階段 checklist：S0–S7 + EDGE→WHOLE→LOCATE→RETURN

### 4.1 Pipeline gates

| Stage | Name | You must produce | Gate (fail-closed) |
|-------|------|------------------|--------------------|
| **S0** | BASE 凍結 + 生／除／扣／洞 | 母圖／empty-BG 尺寸、色域、**SHA-256**；四態證據 | 中途 SHA 漂移 → 停；`(m_hole ^ m_anti_hole)==255` |
| **S1** | OBJECT READ | 物件圖：bbox／剪影／landmarks／遮擋／層級；自身部件分割 | 每主體有閉合剪影；同層互斥；非同義反覆 IoU |
| **S2** | GEOMETRY LOCK | HR 契約 \(B^{HR},M^{HR},P^{HR}\)、四角／5D、DNA；五參數分離 | HR 必須係 LR 嘅精確變換；鏡像 = fail |
| **S3** | 權限／候選標記 | model 輸出標 `candidate`；`edit_permission` 明確 | 未經核實嘅 AI 越權 → 攔截；`edit_mask & preserve_mask == 0` |
| **S4** | TILE／Skill Router／頻率層 | tile core/halo；狀態路由；\(L_{\mathrm{base}}+M_{\mathrm{material}}+H_{\mathrm{detail}}\) | 身份漂移／拓撲錯 → 路由修復 path，擋 DETAIL／SIAX；外形錯 → `OTL0` 硬封鎖 SR／Material／Detail |
| **S5** | 真 AI／Siax 推斷 | 真實 backend 產物；細節只喺閉合 edge 內 | 無 adapter log／合成餘弦網紋扮金絲 → fail |
| **S6** | COMPOSE／RETURN／01380 | 按 locate 硬貼回 master；洞邊亦升清 | 零疊影；`feather_px=0`；`eroded_low_res_border_pixels=0`；契約區 bit-exact |
| **S7** | 獨立 ACCEPT／反扣 | JSON report + boards；磁碟重讀 anti_diff | `--strict`：洞外 `max_rgb_diff=0`、ghost／flip／coverage；反扣 IoU／Boundary F1 |

> Program guidance 正文用 S0–S6 命名；share 強調 **S7 獨立驗收** 同戰場鏈嘅 **反**。實作時兩個編號都要覆蓋：**凍結→讀→鎖→路由→推斷→回位→獨立驗收**。

### 4.2 `EDGE_WHOLE_PART_ELEV`（每個部件）

1. **EDGE** — 二值閉合剪影（`alpha ∈ {0,255}`，`soft_alpha_pixels = 0`）  
2. **WHOLE** — 只喺 edge **內**升清／生成（**含最外 1px 環帶**；Rule 01380）  
3. **LOCATE** — 四角卡或 **Box-Free 5D** 流形 id  
4. **RETURN** — hardpaste／guided return；階層 bottom-up：`L4→L3→L2→L1→L0`

Debug 優先級：**return-chain lock** > 靚 board。

### 4.3 四技能 + 三頻率層（nutr Turn 18；本包延續）

\[
\mathrm{RGB}_{\mathrm{final}} = L_{\mathrm{base}} + M_{\mathrm{material}} + H_{\mathrm{detail}}
\]

| Skill | ID（例） | 做咩 | 唔好做 |
|-------|----------|------|--------|
| **A** | `SKILL_A_NEURAL_SR_BASE_4X` | 神經超分基礎層 \(L\) | 用 Lanczos 頂替 |
| **B** | `SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN` | 幾何鎖定材質 \(M\)（純 RGB） | 改 Alpha／越出洞 |
| **C** | `SKILL_C_MULTISCALE_DETAIL_SYNTHESIS`（+ C2 Normal/Depth、C3 降高頻） | 微細節 \(H\)；噪點過多只降 \(H\) | 模糊掉 \(L\)/\(M\) 黎「去噪」 |
| **D** | `SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD` | 01380 硬邊合成 + 反扣 | Feather／內縮低清邊 |
| （可選） | `INPAINT_HOLE_REPAIR_OPTIONAL` | **只**缺遮擋補洞 | **絕不當**主升清鏈 |

狀態路由（例）：形態清楚但像素少 → A；材質糊 → B；網絲／裂紋欠 → C2；外形錯 → `OTL0` 封鎖生成技能；噪點多 → C3。

---

## 5. Method Registry + 宣稱邊界 + 追溯

### 5.1 Method Registry

為每種方法登記最少：

- `id` / `version` / `stage`（S0–S7）  
- `inputs` / `outputs` / `failure_codes`  
- `edit_permission` 預設 **False**（模型輸出 = `candidate`）  
- `routes_on`（例如 `identity_drift` → `PATH1E_IDENTITY_ECC_LOCK`；`topology_error` → `OTL0_TOPOLOGY_REPAIR`）  
- `evidence`：要邊啲 SHA／metric／board 先算 LOCK  
- **`entrypoint` / `test_id` / `acceptance_gate_id`**（見 5.3）

Registry 缺失或 schema 失敗 → Router **RuntimeError**（唔准 silent fallback 硬編碼 if/else）。  
參考：`validate_registry.py`、`shq_read_and_skill_router.py`、`shq_battlefield_self_part_traceability_engine.py`。

### 5.2 嚴格「宣稱」邊界（Strict Claim Boundary）

| 可宣稱（Verified Claims） | 明確不宣稱（Non-Claims） |
|---------------------------|---------------------------|
| 有磁碟重讀 + SHA-256 證據嘅閘門結果 | 硬編碼 if/else「等於」Registry |
| 五參數分離已強制 | 下採樣交付圖 = 原生未改 4× |
| 獨立參考遮罩 IoU（非自比） | `m_hole vs m_hole` 證明幾何 |
| 真 backend adapter log | 只有 Lanczos／餘弦網紋 |
| 追溯表 8/8（或契約 N/N）PASS 後嘅「自身部件升級組成大圖」 | 追溯未齊仍咁講 |

**口訣：** 證據唔喺磁碟／JSON → 唔好講出口。

### 5.3 一對一追溯硬規（Turn 19）

每個階段必須可指出：

`method_id` → `entrypoint`（同一支程式同一函式）→ `test_id` → `acceptance_gate_id`

戰場示範八階：`BF_S0_EDIT_4WAY_ANTI_HOLE` … `SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD`。  
缺任何一環 → **唔好宣稱**全鏈通過。

### 5.4 CLIPPING MASK REVERSE（empty-BG 根因規則）

**正確：**

1. 用 **原生圖像編輯**（例：Gemini「把人和機甲人移除,只剩背景」）出 **empty-BG**  
2. 同原圖 **同分辨率、已對齊**  
3. 差分反推 mask：例如 \(\|I_{\mathrm{scene}} - I_{\mathrm{empty\_BG}}\|\)（可加語義引導）  
4. 邊界錯 → **改 empty-BG／reverse 根**，下游 **全重生**  
5. 四態：`生(KEEP) → 除(REMOVE) → 扣(DIFF) → 洞(HOLE)`；`diff_grants_edit_permission=False`

**錯誤（reject）：** 合成／inpaint 假空景；根因變咗仲留舊 donor；只向內縮 DNA 唔補覆蓋。

**口訣：** 根因 mask 錯 ⇒ 成個 project compute 係廢。

---

## 6. 你要回報咩（Report back）

| Item | Requirement |
|------|-------------|
| **Input SHA-256** | \(I_0\)、empty-BG、權重（如 Siax `4x_NMKD-Siax_200k.pth`） |
| **Output SHA-256** | master HR、關鍵 board／ZIP |
| **Ghosting** | 自動化 ghost metric + 視覺板 |
| **Bit-exact** | 洞外 `max_outside_hole_rgb_diff = 0` |
| **Coverage** | 每個鎖定 HR mask pixel 有 tile core 或明確 omit |
| **Flip／pose audit** | 水平翻轉／姿態腐壞偵測 |
| **Adapter proof** | 真實 backend id + seed／params |
| **Method Registry hits** | 邊啲 route 被觸發、邊啲 candidate 被擋 |
| **Traceability table** | 每階段 method→program→test→accept |
| **Claim／Non-claim** | 列明已驗證宣稱 vs 明確不宣稱 |
| **01380 metrics** | `feather_px`、`eroded_low_res_border_pixels`、`boundary_ring_upgraded_ratio` |
| **Frequency ablation** | \(L\)/\(M\)/\(H\) 可分層回退嘅證據 |
| **Stage verdict** | S0–S7 逐項 PASS／FAIL（fail-closed JSON） |
| **反扣** | 磁碟重讀 anti_diff：IoU／Boundary F1／Hausdorff |

格式建議：一個 `*_S7_AUDIT_REPORT.json`（或 `*_METHOD_TRACEABILITY_REPORT.json`）+ 對照 board。

---

## 7. 使用 research fossils 嘅正確姿勢

| File | 用途 | 唔好做 |
|------|------|--------|
| `shq_v2_self_consistent_engine.py` | orchestrator／boards 形狀 | 當已接好 Siax |
| `shq_object_extractor.py` | whole-part、reverse mask、DNA、3D/5D 契約 | 當最終 mask 真理 |
| `shq_recursive_layer_return.py` | guided return／hardpaste | 用 soft alpha「修好」漂移 |
| `shq_read_and_skill_router.py` | READ + 狀態路由 | 自動把 candidate 當可寫入 |
| `shq_edit_hole_four_anti_debug.py` | 洞／除／扣／生 六項 audit | 關 `strict` 交貨；留 `interior_core` 低清邊 |
| `shq_5group_test_and_holdout_suite.py` | 21 項 + holdout 四態 | SKIP／WARN 當 PASS |
| `shq_all24_true_generative_upscale_return.py` | 真生成 8K→鎖幾何回位示範 | 用數學餘弦網紋取代擴散母本 |
| `shq_4skill_frequency_layer_engine.py` | 四技能／三頻率層／01380 | 混合一層出圖當「已拆層」 |
| `validate_registry.py` | Registry schema 驗收 | Registry 壞仲 silent 跑 |
| `shq_battlefield_self_part_traceability_engine.py` | **新** 戰場自身部件 + 一對一追溯 | 無追溯表就宣稱「自身部件組成大圖」 |

**未接進 `src/ige`。** Wiring 屬 sibling runner／READ／geometry PRs。

---

## 8. 快速自檢（開工前 30 秒）

- [ ] 已讀 INDEX → PROGRAM_GUIDANCE → 最新 share（XMyk Turn 17–19）→ fossils  
- [ ] 清楚五參數分離（含 `delivery_transform`）  
- [ ] empty-BG 係原生編輯；四態生除扣洞齊  
- [ ] 計劃咗真 backend；**無** Lanczos 捷徑  
- [ ] Rule 01380：洞邊唔留低清、唔 Feather  
- [ ] \(L+M+H\) 可獨立控制／回退；INPAINT 唔係主鏈  
- [ ] Method Registry + **一對一追溯**；candidate 預設不可寫  
- [ ] 準備 S7 磁碟反扣 + Claim／Non-claim 表  

任何一項做唔到 → **停**，先補契約證據，唔好發明 shortcut。
