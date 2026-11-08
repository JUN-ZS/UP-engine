# SHQ AI 使用引導（給另一個 AI Agent）

**Audience:** 任何要跟進／實作／驗收「物件導向幾何約束升頻」嘅 AI agent  
**Normative contract:** [`SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md)  
**Latest source:** [`sources/gemini-share-XMyk6HVn2J9S/`](./sources/gemini-share-XMyk6HVn2J9S/)（**20 turns**；+1 vs nutr：戰場自身部件追溯／生除扣洞反 + 方法一對一追溯）  
**Prior sources:** [`nutrRjsw676R`](./sources/gemini-share-nutrRjsw676R/)（19）、[`hC9HlUpskKK9`](./sources/gemini-share-hC9HlUpskKK9/)（17）、[`47yxULPlPy0W`](./sources/gemini-share-47yxULPlPy0W/)（15）  
**Verifiable package:** [`../research/ige_shq_github_verifiable_package_v1.0/`](../research/ige_shq_github_verifiable_package_v1.0/) — **research-only** 五層可重現包（優先用呢個驗）  
**Other-AI runbook:** [`SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`](./SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md) — clone、preflight、逐步 RUN L0→L4、S7、回報格式及 BLOCK 規則
**Fossils:** [`../research/shq_v9/`](../research/shq_v9/) — 早期單檔化石 ×10；**唔係** production runtime

---

## 0. 對上一包（nutr）新增咗咩

| 項 | 內容 |
|----|------|
| Turn 19 新測 | 複雜人機**戰場圖**：`生→除→扣→洞→自身高清部件三層升級→01380 硬邊回位→反` |
| 新化石 | `shq_battlefield_self_part_traceability_engine.py` |
| **可驗證包** | [`research/ige_shq_github_verifiable_package_v1.0/`](../research/ige_shq_github_verifiable_package_v1.0/) — 五層聯動 + 下半身 HR 母本 + dense registration（見 §9） |
| 追溯硬規 | 每階段必須 **同一 `method_id` → 同一 `entrypoint` → 同一 `test_id` → 同一 `acceptance_gate_id`**（一對一；唔可以「方法表有、程式另一套」） |
| 宣稱 | 可宣稱「大圖由**自身**高清部件升級組成回去」——前提係上述追溯 + S7 磁碟反扣全 PASS；否則屬越權宣稱 |

nutr 已有、本包延續（務必保留）：**嚴格宣稱邊界**、**Anti-Tautology**、**五參數分離（含 `delivery_transform`）**、**Rule 01380**、**三頻率層 \(L+M+H\)**、**四技能 A/B/C/D（INPAINT 降級）**。

---

## 1. 必讀順序（Read order）

嚴格跟呢個次序；未做 preflight 前唔可以直接跑長流程。

1. **[`SHQ_INDEX.md`](./SHQ_INDEX.md)** — HUB 地圖、PR 關係及現行套件入口  
2. **[`SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`](./SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md)** — 權威階段契約、硬閘及禁令  
3. **本檔** — AI 閱讀、證據、候選、權限、技能路由及宣稱邊界  
4. **[`SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`](./SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md)** — 外部 AI 必須照做：Clone → Environment → Preflight → Registry → Unit Tests → L0–L4 Strict RUN → Fresh S7 Evidence  
5. **最新 Gemini 源** — `sources/gemini-share-XMyk6HVn2J9S/EXTRACT.md` → `Gemini-完整對話.md`（20 turns；戰場自身部件、一對一追溯）  
6. **可驗證套件** — `research/ige_shq_github_verifiable_package_v1.0/`：先讀 `README.md`／`HUB_NOTES.md`／Registry，再讀 L0–L4 實作；`research/shq_v9/` 只作歷史化石，不可直接當 production runtime

讀文件係理解契約；執行結果必須由當前 clone 的新輸出、SHA、測試及 strict exit code 證明。

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

- [ ] 已讀 INDEX → PROGRAM_GUIDANCE → 最新 share（XMyk）→ **可驗證包** `run_all_verifications.py --strict` → fossils  
- [ ] 清楚五參數分離（含 `delivery_transform`）  
- [ ] empty-BG 係原生編輯；四態生除扣洞齊  
- [ ] 計劃咗真 backend；**無** Lanczos 捷徑  
- [ ] Rule 01380：洞邊唔留低清、唔 Feather  
- [ ] \(L+M+H\) 可獨立控制／回退；INPAINT 唔係主鏈  
- [ ] Method Registry + **一對一追溯**；candidate 預設不可寫  
- [ ] 準備 S7 磁碟反扣 + Claim／Non-claim 表  

任何一項做唔到 → **停**，先補契約證據，唔好發明 shortcut。

---

## 9. 五層 GitHub 可驗證包（現行參考實作）

**路徑：** [`research/ige_shq_github_verifiable_package_v1.0/`](../research/ige_shq_github_verifiable_package_v1.0/)  
**狀態：** research-only；**未**接 `src/ige`。任何外部 AI／工程師應以呢包做端到端重現，而唔係只開 `shq_v9` 單檔。

### 9.1 外部 AI 必須按次序執行

先在套件根目錄安裝固定依賴，再依序執行；不可跳過 preflight：

```bash
python -m pip install -r requirements.txt
python preflight_check.py
python registry/validate_registry.py registry/method_registry.json
python -m unittest discover -s tests -v
python run_all_verifications.py --strict
```

**停機規則：**

- Preflight 非 `PASS`：立即 `BLOCK`，唔准執行下游。
- Registry 非 `PASS`、unit tests 有 FAIL／ERROR／SKIP：停機，唔准叫 pipeline accepted。
- Strict runner 非零退出、任何 WARN／SKIP／BLOCK 或缺少新產物：唔准宣稱完成。
- 只可以用當前執行新產生嘅 master、board、report 和 SHA；舊 report 只係歷史證據。

Hub baseline 儲存報告曾記錄 **12/12** runner unit tests、**8/8** strict stage checks PASS。呢個係歷史報告紀錄，**唔係每次新環境自動保證**；每個 AI clone 後都必須重跑並核對新 report。依賴由套件根目錄 `requirements.txt` 固定（NumPy、OpenCV headless）。

**另注意：** 2026-11-08 新附上的 candidate ZIP（SHA-256 `6f13bd5c45f99db1541f236991dbd9e07d7bb637f9d02138563f85ff7f63b2e8`）缺少 `B0_GL`、`B2_GL` 兩張幾何鎖定母本；Registry 和 package 4 tests 雖可通過，完整 strict runner 會在 L3 失敗。該 ZIP 唔可以取代目前 HUB 五母本 baseline。詳見 Runbook §0。

### 9.2 Layer ↔ 階段／技能／Rule 01380

| Layer | 模組 | 階段／技能 | 驗收門檻（例） |
|-------|------|-----------|----------------|
| **L0** | `l0_s0_four_way_anti_hole.py` | S0 生/除/扣/洞/反洞 | `ACCEPT_BF_S0_HOLE_AND_ANTIHOLE_COMPLEMENT` |
| **L1** | `l1_s1_s2_part_hierarchy_and_geometry_lock.py` | S1 18-part；S2 幾何鎖 | `ACCEPT_BF_S1_…` / `ACCEPT_BF_S2_…` |
| **L2** | `l2_s3_s4_permission_and_registry_router.py` | S3 權限；載入 registry | `ACCEPT_BF_S3_DISJOINT_EDIT_AND_PRESERVE_PERMISSIONS` |
| **L3** | `l3_s4_self_part_dense_registration_and_3freq_engine.py` | Skills **A/B/C**；\(L+M+H\)；逐部件 template+光流 | `ACCEPT_SKILL_A/B/C_…` |
| **L4** | `l4_s5_s6_s7_rule01380_return_and_reverse_qa.py` | Skill **D**；Rule **01380** 回位；S7 磁碟反扣 | `ACCEPT_SKILL_D_RULE_01380_AND_S7_DISK_REVERSE_QA` |

### 9.3 三大 DEBUG 根因（做同類升清時必須避開）

1. **上半身裁切套全身 bbox** → 下半身腿甲／戰靴垂直錯位。必須有完整自身 HR 母本（本包：`B0_UPPER/LOWER`、`B1_UPPER/LOWER`、`B2_FULL` 覆蓋 P01–P18）。  
2. **粗框縮放無逐部件稠密配準** → 「真」高清寫唔準入大圖。必須 per-part `matchTemplate` + Farneback／等效非剛性對齊。  
3. **硬編碼絕對路徑** → 外部 AI 下載即 `FileNotFoundError`。必須相對路徑五層模組 + 可攜 runner。

詳見包內 [`README.md`](../research/ige_shq_github_verifiable_package_v1.0/README.md) 與 [`HUB_NOTES.md`](../research/ige_shq_github_verifiable_package_v1.0/HUB_NOTES.md)。



### 9.4 生成後端宣稱邊界

五層套件使用已存在於 `assets/` 的自身 HR 母本作 dense registration、頻率層轉移、幾何回位及反扣驗收。單靠執行此 PY 套件，**唔代表**本次有呼叫 Siax／NCNN、ComfyUI／Flux、Imagine 或其他 live diffusion backend。若要宣稱本次有真生成，必須另附真實 adapter log、模型／權重 SHA、seed、參數及新生成圖 SHA。頻率 RMS、Sobel 或 detail_gain 只係診斷量，唔可以單獨證明語義細節正確。
