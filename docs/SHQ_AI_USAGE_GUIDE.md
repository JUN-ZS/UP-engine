# SHQ AI 使用引導（給另一個 AI Agent）

**Audience:** 任何要跟進／實作／驗收「物件導向幾何約束升頻」嘅 AI agent  
**Normative contract:** [`SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md)  
**Latest source:** [Gemini 19-turn pack](https://github.com/JUN-ZS/UP-engine/tree/feat/shq-geometry-lock-program-guidance-v0.1/docs/sources/gemini-share-nutrRjsw676R/)（最新；含 PR #12 宣稱再測 + 三技能／頻率層）  \n**Prior source:** [Gemini 17-turn pack](https://github.com/JUN-ZS/UP-engine/tree/feat/shq-geometry-lock-program-guidance-v0.1/docs/sources/gemini-share-hC9HlUpskKK9/)（Method Registry + 真生成 8K）  
**Prior source:** [`sources/gemini-share-47yxULPlPy0W/`](./sources/gemini-share-47yxULPlPy0W/)（15 turns）  
**Fossils:** [`../research/shq_v9/`](../research/shq_v9/) — **唔係** production runtime

---

## 1. 必讀順序（Read order）

嚴格跟呢個次序；唔好一開始就開 fossil Python「照抄當 production」。

1. **[`SHQ_INDEX.md`](./SHQ_INDEX.md)** — 地圖、sibling PRs、邊份 doc 係契約  
2. **[`SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md)** — 階段閘門、禁令、模組對位（**權威**）  
3. **本檔** — 執行 checklist 同回報格式  
4. **最新 Gemini 源** — [19-turn pack](https://github.com/JUN-ZS/UP-engine/tree/feat/shq-geometry-lock-program-guidance-v0.1/docs/sources/gemini-share-nutrRjsw676R/)（research provenance；唔係 production runtime）  
5. **SHQ Agent Driver** — [執行控制文件](./SHQ_AGENT_DRIVER.md)，以 Manifest 提交候選，預設只做 preflight  
6. **`research/shq_v9/`** — 設計化石／實驗日誌；對照契約睇，**禁止**把 Lanczos／CLAHE 路徑當可交貨後端

讀完先動手改 code／開 runner／寫驗收。

---

## 2. 一句意圖（唔好偏題）

> 先 **鎖死每個物件嘅幾何**，再喺契約內排 tile／做真生成升頻；**唔係** 加大 tile、Lanczos 銳化、軟 alpha、補邊、或假 inpaint 扮生成。

參數硬分離：`model_scale` ≠ `object_transform` ≠ `tile_size` ≠ `tile_context`。Siax 嘅 `model_scale` 係固定 4×；加大 `-t` **唔等於** 物件變大。

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

---

## 4. 階段 checklist：S0–S7 + EDGE→WHOLE→LOCATE→RETURN

### 4.1 Pipeline gates

| Stage | Name | You must produce | Gate (fail-closed) |
|-------|------|------------------|--------------------|
| **S0** | BASE 凍結 | 母圖／empty-BG 尺寸、色域、**SHA-256** | 中途 SHA 漂移 → 停 |
| **S1** | OBJECT READ | 物件圖：bbox／剪影／landmarks／遮擋／層級 | 每主體有閉合剪影；同層互斥 |
| **S2** | GEOMETRY LOCK | HR 契約 \(B^{HR},M^{HR},P^{HR}\)、四角／5D、DNA | HR 必須係 LR 嘅精確變換；鏡像 = fail |
| **S3** | 權限／候選標記 | model 輸出標 `candidate`；`edit_permission` 明確 | 未經核實嘅 AI 越權 → 攔截（見 Method Registry） |
| **S4** | TILE／Skill Router | tile core/halo；狀態路由（IDENTITY／TOPOLOGY…） | 身份漂移／拓撲錯 → 路由到修復 path，擋 DETAIL6／SIAX4X |
| **S5** | 真 AI／Siax 推斷 | 真實 backend 產物；細節只喺閉合 edge 內 | 無 adapter log／合成餘弦網紋扮金絲 → fail |
| **S6** | COMPOSE／RETURN | 按 locate 硬貼回 master | 零疊影；契約區 bit-exact；禁 soft blend 瞞錯 |
| **S7** | 獨立 ACCEPT | JSON report + boards；對凍結母圖獨立審計 | `--strict`：洞外 `max_rgb_diff=0`、ghost／flip／coverage |

> Program guidance 正文用 S0–S6 命名；最新 share 把「權限／路由」拆細並強調 **S7 獨立驗收**。實作時兩個編號都要覆蓋：**凍結→讀→鎖→路由→推斷→回位→獨立驗收**。

### 4.2 `EDGE_WHOLE_PART_ELEV`（每個部件）

1. **EDGE** — 二值閉合剪影（`alpha ∈ {0,255}`，`soft_alpha_pixels = 0`）  
2. **WHOLE** — 只喺 edge **內**升清／生成  
3. **LOCATE** — 四角卡或 **Box-Free 5D** 流形 id（優於脆 2D polygon）  
4. **RETURN** — hardpaste／guided return；階層 bottom-up：`L4→L3→L2→L1→L0`

Debug 優先級：**return-chain lock** > 靚 board。

---

## 5. Method Registry + CLIPPING MASK REVERSE

### 5.1 Method Registry（最新兩輪要求）

為每種方法登記最少：

- `id` / `version` / `stage`（S0–S7）  
- `inputs` / `outputs` / `failure_codes`（對接 `E-SHQ-*`、`ORIGIN→EXPLORE→FAIL→QUESTION→FIX→LOCK`）  
- `edit_permission` 預設 **False**（模型輸出 = `candidate`）  
- `routes_on`（例如 `identity_drift` → `PATH1E_IDENTITY_ECC_LOCK`；`topology_error` → `OTL0_TOPOLOGY_REPAIR`）  
- `evidence`：要邊啲 SHA／metric／board 先算 LOCK  

參考化石：`research/shq_v9/shq_read_and_skill_router.py`、`shq_5group_test_and_holdout_suite.py`、`shq_edit_hole_four_anti_debug.py`。  
Holdout 要能 **分開** 四態：全準／S3 攔截越權／S6 攔截尺寸漂移／S6–S7 攔截水平貼反。

### 5.2 CLIPPING MASK REVERSE（empty-BG 根因規則）

**正確：**

1. 用 **原生圖像編輯**（例：Gemini「把人和機甲人移除,只剩背景」）出 **empty-BG**  
2. 同原圖 **同分辨率、已對齊**  
3. 差分反推 mask：例如 \(\|I_{\mathrm{scene}} - I_{\mathrm{empty\_BG}}\|\)（可加語義引導）  
4. 邊界錯 → **改 empty-BG／reverse 根**，下游 **全重生**  

**錯誤（reject）：**

- 合成／inpaint 假空景  
- 根因變咗仲留舊 donor polygon  
- 「只向內縮 DNA」卻唔補齊欠覆蓋主體  

**口訣：** 根因 mask 錯 ⇒ 成個 project compute 係廢。

---

## 6. 你要回報咩（Report back）

每次跑完／交 PR／交 board，最少交出：

| Item | Requirement |
|------|-------------|
| **Input SHA-256** | \(I_0\)、empty-BG、權重（如 Siax `4x_NMKD-Siax_200k.pth`） |
| **Output SHA-256** | master HR、關鍵 board／ZIP |
| **Ghosting** | 自動化 ghost metric + 視覺板；雙重曝光邊 = fail |
| **Bit-exact** | 契約承諾 lossless 嘅區：像素身份（洞外 `max_outside_hole_rgb_diff = 0`） |
| **Coverage** | 每個鎖定 HR mask pixel 有 tile core 或明確 omit |
| **Flip／pose audit** | 水平翻轉／姿態腐壞偵測結果 |
| **Adapter proof** | 真實 backend id + seed／params（**禁止**只有 Lanczos 日誌） |
| **Method Registry hits** | 邊啲 route 被觸發、邊啲 candidate 被擋 |
| **Stage verdict** | S0–S7 逐項 PASS／FAIL（fail-closed JSON） |

格式建議：一個 `*_S7_AUDIT_REPORT.json` + 對照 board；唔好淨係交「睇落好似清楚」嘅縮圖。

---

## 7. 使用 research fossils 嘅正確姿勢

| File | 用途 | 唔好做 |
|------|------|--------|
| `shq_v2_self_consistent_engine.py` | orchestrator／boards 形狀 | 當已接好 Siax |
| `shq_object_extractor.py` | whole-part、reverse mask、DNA、3D/5D 契約 | 當最終 mask 真理 |
| `shq_recursive_layer_return.py` | guided return／hardpaste | 用 soft alpha「修好」漂移 |
| `shq_read_and_skill_router.py` | READ + 狀態路由 | 自動把 candidate 當可寫入 |
| `shq_edit_hole_four_anti_debug.py` | 洞／除／扣／生 六項 audit | 關 `strict` 交貨 |
| `shq_5group_test_and_holdout_suite.py` | 21 項 + holdout 四態 | SKIP／WARN 當 PASS |
| `shq_all24_true_generative_upscale_return.py` | 真生成 8K→鎖幾何回位示範 | 用數學餘弦網紋取代擴散母本 |

**未接進 `src/ige`。** Wiring 屬 sibling runner／READ／geometry PRs。

---

## 8. 快速自檢（開工前 30 秒）

- [ ] 已讀 INDEX → PROGRAM_GUIDANCE → 最新 share → fossils  
- [ ] 清楚 `model_scale`／`object_transform`／`tile_size`／`tile_context` 四分離  
- [ ] empty-BG 係原生編輯，唔係假空景  
- [ ] 計劃咗真 backend（Siax／Comfy／Imagine…），**無** Lanczos 捷徑  
- [ ] RETURN 用硬貼／5D locate；準備 S7 獨立 SHA／ghost／bit-exact 報告  
- [ ] Method Registry 會標記 candidate 同攔截越權／身份漂移  

任何一項做唔到 → **停**，先補契約證據，唔好發明 shortcut。


## 9. Python execution authority

AI agents propose structured evidence and method IDs. They do not import research scripts directly, grant edit permission, or declare their own acceptance. Use the central [SHQ Agent Driver](./SHQ_AGENT_DRIVER.md) and its manifest. The default is plan-only; explicit execution is required. The current callable allowlist includes Siax only. Flux/Comfy remains workflow_candidate until a live Comfy adapter and independent S7 evidence are implemented and verified.

A passing static workflow audit or unit-test suite is not a live generation receipt.
