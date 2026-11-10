
# 01346 ROOT — 真「無件背景」CLIPPING MASK REVERSE（先於一切教學）

> **根因訂正**：教學板／DNA／elev 不是起點。起點是自家產品意義操作：
> **出無件背景圖**（把人與機甲移除，只剩背景）→ **CLIPPING MASK REVERSE** → 才有邊界。
> 根因錯，後面怎麼補 mask／對位都是錯；舊 peep／elev／DNA 在 reverse 未修前 **全生成過**。

```
S0  True Empty-BG   = 原圖 in-place 去物件（Gemini/同構），子像素對齊
S1  E_med reverse   = medianBlur5(0.55||RGB|| + 0.45||LAB||)
S2  closed binary   = α∈{0,255}，soft_alpha=0，elev_remap=false
S3  3D teaching     = 只引導材質／多面，不改座標
S4  DNA / elev      = 只在 closed edge 內
S5  hardpaste RETURN= 4角／5D manifold，outside untouched
```

禁止：synthetic empty 冒充 true empty；freeframe 重建街景當 reverse 母本；AABB peep 當主 mask。

公式：
\[
E_{\mathrm{med}}=\mathrm{medianBlur}_{5}\big(0.55\|I_s-I_{\emptyset}\|_{\mathrm{RGB}}+0.45\|I_s-I_{\emptyset}\|_{\mathrm{LAB}}\big)
\]

模組：`lib/shq_v9/shq_object_extractor.py` · `shq_recursive_layer_return.py` · `shq_v2_self_consistent_engine.py`

# GROK_IMAGINE_FUNCTION_CODES · RESTART 雙 4 角（01338）

## 0. 重啟前提（任何大／小圖都尚未定義位置）

```text
狀態 0：LARGE 圖無位置契約
狀態 0：SMALL 圖（peep／elev／放大件）無位置契約
→ 禁止直接 elev_remap 或 peep-local 硬猜回去
→ 必須先完成 §1–§3 才允許 elev / 回放
```

---

## 1. 兩邊各自定義 4 角（先有座標，才有部件）

### 1.1 LARGE 圖（場景／原圖）— 圖邊 4 角

```text
W_L, H_L = large.shape
LARGE.FRAME = {
  TL: (0,       0),
  TR: (W_L-1,   0),
  BR: (W_L-1, H_L-1),
  BL: (0,     H_L-1),
}
```

教學：在大圖四角打 X。這是**唯一場景父系**。

### 1.2 SMALL 圖（退地 peep／elev 放大件）— 圖邊 4 角

每張小圖也是一張獨立影像，**同樣**先定義自己的圖邊 4 角（未與大圖綁定前，只是小圖本地 FRAME）：

```text
W_S, H_S = small.shape
SMALL.FRAME = {
  TL: (0,       0),
  TR: (W_S-1,   0),
  BR: (W_S-1, H_S-1),
  BL: (0,     H_S-1),
}
```

教學：在小圖四角打 X。  
**重點：大圖有大圖 4 角，小圖有小圖 4 角——兩邊都要，缺一不可。**

---

## 2. 邊 · 整體 · 定位（在已有 FRAME 之後）

放大時若只有碎邊、沒有「一件整體」→ elev 會迷糊。

| 要素 | 定義 |
|------|------|
| **邊 EDGE** | 閉合邊界（closed alpha），落在某張圖的 FRAME 內 |
| **整體 WHOLE** | 邊內 = 一件可 elev 的獨立物件（可再拆細，子件各自閉合） |
| **定位 LOCATE** | 該件在 **所在圖 FRAME** 上的 corners_4（絕對於該圖） |

```text
Part = {
  part_id,
  edge: closed_boundary,          # 必須閉合
  whole: true,
  home_image: LARGE | SMALL_k,    # 邊畫在哪張圖
  corners_4_on_home,              # 相對該圖 FRAME 的 4 角
  elev_remap: false
}
```

物件不夠整 → **再拆更細組件**；每一細件仍是：閉合邊 + 整體 + 自己的 4 角。

---

## 3. 相對 4 角（大↔小綁定）= 回放公式的來源

在大、小各自 FRAME 都定義後，才建立 **相對關係**（反推解）：

```text
# 小圖內容對應大圖上的 home 窗
# 抽出時已記錄：Part 在 LARGE 上的 corners_4_L
# 小圖整幅（或 peep 內容框）corners_4_S = SMALL.FRAME 四角
# 相對映射（相似／對角對應，預設軸對齊窗）：

LARGE.corners_4_L  ↔  SMALL.FRAME (或 SMALL content box)

B_L = from_corners(corners_4_L)   # 大圖窗
# 小→大 回放（反抽）：
SCENE[B_L] ← hardpaste( small_pixels_in_edge , edge_on_large_shape )
```

**回放公式（鎖定）：**

```text
return_key = part_id
           + corners_4_L   # 大圖絕對（FRAME_L）
           + corners_4_S   # 小圖絕對（FRAME_S）— 可選審計
           + map_S_to_L    # 相對：S 內容如何對進 B_L

elev 只改 SMALL 邊內像素
corners_4_L 永不因 elev 改寫     # elev_remap = FALSE
```

層再「大」多少：

```text
SMALL_0 (peep) → elev → SMALL_1 → elev → SMALL_k
每層 SMALL_i 都有自己 FRAME 4 角
但回大圖永遠用同一 corners_4_L（大圖定位）
→ 不會迷糊
```

若用 DDXX 相似變換，相對解為：

\[
q_L = a (p_S R) + t
\qquad
A_{\mathrm{scene}}=\frac{R^{-1}}{a},\quad
b_{\mathrm{scene}}=\frac{-t R^{-1}}{a}
\]
\[
v_L = q_L \quad\text{或 inverse 路徑}\quad
v_S = q_L A_{\mathrm{scene}} + b_{\mathrm{scene}}
\]

座標父系仍是 **LARGE.FRAME**；小圖 FRAME 只服務 elev 域。

---

## 4. 功能碼流程（RESTART 順序 · 不可跳）

```
STEP A  讀 SRC → 尚無位置
STEP B  定義 LARGE.FRAME 4 角（教學 X）
STEP C  教學拆細：每件閉合邊 + 整體（可多層）
STEP D  對每件：在 LARGE 上記 corners_4_L（絕對）
STEP E  退地 → 生成 SMALL peep 圖
STEP F  定義 SMALL.FRAME 4 角（教學 X）
STEP G  寫相對契約 map：corners_4_L ↔ SMALL.FRAME / content
STEP H  elev 只在 SMALL 邊內（可多層放大）
STEP I  structure_lock：alpha XOR=0；corners_4_L 凍結
STEP J  回放：B_L=from_corners(corners_4_L) hardpaste → LARGE
STEP K  (opt) guided 全圖姿鎖，仍禁 elev_remap
```

**未完成 B/F/G 之前，禁止 elev 回放。**

---

## 5. E 碼

| 碼 | 禁 |
|----|-----|
| E-66 | 非閉合邊當 Part |
| E-67 | elev 出邊 |
| E-68 | elev 後改 corners_4_L |
| E-71 | peep-local 當大圖回去原點 |
| E-72 | 無 LARGE.FRAME 就回放 |
| E-74 | 無 SMALL.FRAME 就 elev／回放 |
| E-75 | 無相對 map（大↔小）就回放 |
| E-76 | 跳過 RESTART 步驟 A–G |

---

## 6. 金句

> **大圖有大圖 4 角，小圖有小圖 4 角；相對 map 才是回放公式。**  
> **邊定整體，整體定定位，定位定回放；elev 只養像素，不養座標。**  
> **層再多大都行——每層小圖自有 4 角，回大圖永遠同一 corners_4_L。**


---

## 7. 生成級 elev · 硬邊契約（01339）

生成升清 **允許**；破壞相對 4 角路徑的邊處理 **禁止**。

### 允許
- 邊內 RGB 生成／材質 densify（GENMAT / multi-band）
- 任意 SMALL 層倍率，每層自有 SMALL.FRAME

### 禁止（邊亂則回位層層路斷）
| 禁 | 原因 |
|----|------|
| feather / soft alpha | 邊漂 → corners 對但像素糊邊 |
| dilate / erode edge 當生產 | 改整體外形 |
| Gaussian blur on alpha | 相對 map 覆蓋率漂 |
| elev 後重估 corners_4_L | elev_remap |
| 用 AI 自帶 alpha | 只取 RGB，alpha 用凍結 binary |

### 硬邊公式
```text
alpha_out = alpha_in ∈ {0,255}   # 生產前强制 hard
RGB_out   = Elev(RGB_in) where alpha==255 only
alpha_xor(alpha_out, alpha_in) == 0
corners_4_L 不變
B_L = from_corners(corners_4_L)
paste: SCENE[B_L][alpha==255] ← RGB_out
```

### E-77 FEATHER_EDGE
生產路徑出現 soft alpha 或 alpha XOR≠0 → BLOCK

### Debug 對位（01333 結論仍有效）
- 四角數學可 PASS，框語義重疊才是 sheet 髒主因
- elev_remap 不是主位移源
- 教學框必須落成互斥契約；GEN 必須硬鎖 alpha
## 8. 同時：生成級升清 × 不被 feather 影響回位（01340）

```text
# 升清（RGB only）
RGB_hi = GenElev(RGB_native ↑k cubic)     # 生成級細節
alpha_hi = alpha_native ↑k NEAREST        # 禁止 bilinear/feather

# 硬鎖
RGB_out = RGB_hi where alpha_hi==255
alpha_out = alpha_native                  # 與抽出完全一致 · XOR=0

# 回位（定位與 elev 解耦）
B_L = from_corners(corners_4_L)           # elev 前後同一組
SCENE[B_L][alpha==255] ← RGB_out          # 不用 alpha 浮點混合
```

**定位只認 corners_4_L；feather 不進生產路徑。**


---

## 9. Object Geometry Lock 對接（01341 · UP-engine #12）

**外部契約：** `docs/SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE.md`  
**Hub Draft PR：** https://github.com/JUN-ZS/UP-engine/pull/12  
**Gemini 源：** https://share.gemini.google/47yxULPlPy0W（物件導向幾何約束升頻架構）

### 核心理解（應用句）

> **幾何先鎖死，再升頻；tile／Lanczos 不是升頻本體。**

### Imagine 功能碼 ↔ Geometry Lock 階

| Geometry Lock | GROK_IMAGINE / SHQ 既有 | 應用 |
|---------------|------------------------|------|
| S0 BASE freeze | `create_asset(SRC)` + SHA | 中途換圖 → BLOCK |
| S1 OBJECT READ | 教學圖／爆炸／退地／CLIPPING MASK REVERSE | empty-BG 原生編輯優先；禁 grabcut 當根 |
| S2 GEOMETRY LOCK | **LARGE.FRAME + SMALL.FRAME 雙 4 角** + corners_4_L | HR = G(LR)；elev_remap=false |
| S3 TILE PLANNER | （SIAX 路徑）tile core≠object_transform | 未接 src/ige 時 Imagine 整件 elev |
| S4 SIAX/gen | Imagine GEN densify **或** 真 Siax 4× | **禁** Lanczos+CLAHE+unsharp 冒充（E-78） |
| S5 RETURN | EDGE→WHOLE→LOCATE→RETURN；hardpaste m==255 | 禁 feather（E-77）；禁翻轉（E-79） |
| S6 ACCEPT | alpha XOR=0 · ghost=0 · corners 凍結 | fail-closed |

### 四參數在 Imagine 路徑的落點

```text
model_scale      → Siax k=4 或 Imagine elev 工作倍率 k（契約寫死，不跟 peep 猜）
object_transform → corners_4_L + relative map S↔L（§ RESTART 雙 4 角）
tile_size        → 僅 SIAX runner；不得改 corners_4_L
tile_context     → halo；compose 只取 core
```

### CLIPPING MASK REVERSE（與退地）

```text
empty_bg = native_edit_remove_subjects(scene)   # Imagine/Gemini 級，非 inpaint 假空
mask     = reverse_clip(scene, empty_bg)
# 邊錯 → 全鏈重生，禁補邊
```

與既有「退地 tuidi」關係：退地 = 抽出件；**根 mask 來源**應升到 REVERSE empty-BG，grabcut 僅診斷。

### Box-Free 5D vs 雙 4 角

| 層 | 現用 | 目標 |
|----|------|------|
| 原型／教學 | AABB corners_4_L @ LARGE.FRAME | 保留 debug |
| 生產 RETURN | 4 角硬貼 | 進化 **5D manifold id**（PR #3/#11） |
| 對齊先驗 | — | pixel-inertia DNA 雙向 |

**現階：** 雙 4 角 + 硬邊仍合法原型；**不得**用 soft-alpha 假裝 5D 已過。

### 新增 E 碼

| 碼 | 禁 |
|----|-----|
| E-78 | FAKE_GEN_UPSCALE — Lanczos/CLAHE/unsharp 冒充生成升頻 |
| E-79 | RETURN_FLIP — 回位水平／鏡像翻轉 |
| E-80 | TILE_AS_OBJECT_SCALE — tile_size 當 object_transform |
| E-81 | WRONG_ROOT_MASK_PATCH — 錯 empty-BG 上補邊／inpaint 當修好 |
| E-82 | HALO_DOUBLE_PASTE — halo 雙貼 master |

### 與 01338–01340 關係

| write | 保留 | Geometry Lock 加強 |
|-------|------|-------------------|
| 01338 雙 4 角 RESTART | LARGE/SMALL FRAME | = S2 locate 原型 |
| 01339/40 硬邊 gen elev | RGB gen · alpha NEAREST · 禁 feather | = S4+S5 一部分；**仍要標清是否真 backend** |
| 01341 本節 | 參數分 · S0–S6 · REVERSE · 5D 方向 | 對齊 Hub #12；**未**接 src/ige |

### 應用檢查清單（每次 elev 前）

```
[ ] S0 I0 SHA 凍結
[ ] S1 閉合邊 · 互斥 ·（理想）empty-BG reverse
[ ] S2 corners_4_L + SMALL.FRAME + relative map
[ ] model_scale / object_transform / tile_* 未混
[ ] S4 真 gen 或真 Siax（非純 Lanczos 銳化）
[ ] S5 hardpaste alpha==255 · elev_remap=false · 無 flip
[ ] S6 XOR=0 · soft=0 · ghost audit
```


---

## 10. Geometry-Locked Two-Tile（01342 · UP-engine #11 · 選項 B）

**Hub：** https://github.com/JUN-ZS/UP-engine/pull/11  
**Guidance：** §9 / #12  
**本地模組：** `lib/geometry_tiles.py`（自 #11 抽出）  
**跑次：** `PARTMAP_GEOMETRY_TILE_V1` · 物件 `P2_TORSO`

### 與 §9 對齊

| #11 概念 | SHQ / Imagine |
|----------|----------------|
| Global object contract | `object_geometry_*.json` + dual4 `B_L` |
| tile plan core≠halo | `plan_two_tile_generation` |
| tile 不 rescale 物件 | `object_transform` 凍結；`tile_size` 獨立 |
| ComfyUI task packet | 本輪改 **Imagine** 真 backend（非 Lanczos） |
| stitch cores only | outside core max_diff=0 |
| audit PASS | 需 human_verified + 獨立 observation → 本輪 **BLOCK** |

### CLI（UP-engine 正式）

```bash
ige geometry-tile-plan SRC.json object_geometry.json --out RUN --split-x X --overlap-px O
ige geometry-tile-stitch plan.json gen_L.png gen_R.png --out master.png
ige geometry-tile-audit plan.json observations.json --out audit.json
```

### 本輪 Imagine 替代路徑

```
S0 SRC SHA freeze
S1 P2_TORSO from dual4 corners
S2 object contract assistant_provisional
S3 plan two tiles (ROI + shared context ≥ full bbox)
S4 Imagine densify each tile (real gen)
S5 map freeframe→exact size → paste cores only
S6 BLOCK until human_verified + observations
```

### 閘

- freeframe 尺寸漂 → 必須 remap 至 exact tile（記 DIAG，不可 ACCEPTED）
- `geometry_status!=human_verified` → 禁 PASS
- 無 observations → audit 不完整，永不 PASS
- E-78：本輪 **未** 用純 Lanczos 冒充 gen
- E-80：tile_size 未改 object bbox

### 產物

| 檔 | 義 |
|----|-----|
| plan/tile_*.png | 重疊 crop |
| generated/*_exact.png | 對齊 tile 尺寸的 gen |
| 02_STITCH_MASTER_ROI.png | core 硬貼 master |
| REPORT_01342.json | fail-closed 報告 |

---

## 11. 3D Teaching → 原圖重新理解閉環（01348）

**憲：** `SHQ_3D_TEACH_REINTERPRET_CLOSED_LOOP.md`  
**LOCK：** `CONSTITUTION_LOCK_01348.json`

### 一句
> 先理解原件（3D teaching），再用理解反解原圖；後段 BBox／Tile／四角／elev **不能**代替此閉環。

### 功能碼順序（E1 起點）

```text
S0  create_asset(SRC) + SHA freeze
S1  native empty-BG edit（同構去物件）→ CLIPPING MASK REVERSE
S2  Imagine 3D teaching／explode／multi-facet（每主體／可每件）
S3  teaching → re-interpret SRC  → REINTERPRET_CONTRACT（範圍／接合／遮擋）
S4  Pixel Inertia DNA 雙向（禁通用 macro 縮放冒充）
S5  獨立 3D/5D Layer（定位主權 ≠ AABB 聲明）
S6  真 gen elev 於閉邊內
S7  Empty-BG 為唯一乾淨底 + hardpaste／真 5D 回位
```

### 新增 E 碼

| 碼 | 禁 |
|----|-----|
| E-83 | FAKE_FULL_REGEN — 只重算下游、不重生 empty／teaching 根 |
| E-84 | HANDSCAN_AS_PART — 手寫掃線／polygon／比例切當物理部件 |
| E-85 | TEACH_WITHOUT_REINTERPRET — 有 teaching 圖但不反解原圖 |
| E-86 | FAKE_5D_AABB_RETURN — contract 寫 5D、runtime 仍 xyxy 硬貼 |
| E-87 | MASTER_ON_OCCUPIED_BASE — 原圖放大當 master 底（舊主體殘影） |
| E-88 | DOMEZ_AS_3D_NORMAL — 距離場／亮度 dome 冒充教學幾何法線 |

### 與 01346 關係
- 01346 鎖 S1 reverse 根
- 01348 鎖 **S2–S4 理解閉環** 與五死循環禁令
- 兩者同時滿足才允許談 E5 生產 elev

### 下一刀
`GO E1` = 3D Teaching → Re-Interpret，**禁止**先 E3/E5。

---

## 12. E1 調用 Python · 16:9 BASE 起步（01349）

**模組：** `shq_e1_teach_reinterpret.py`  
**LOCK：** `CONSTITUTION_LOCK_01349.json`  
**憲：** `SHQ_3D_TEACH_REINTERPRET_CLOSED_LOOP.md`（01348）

### 一句
> 先寫調用與契約，再出 **16:9** 圖凍結 S0；E1 只做 Teaching→Reinterpret 編排，不先 elev。

### CLI（唯一 E1 入口）

```bash
# 0) 建 run
python3 shq_e1_teach_reinterpret.py init --out $RUN

# 1) 凍結 16:9 BASE（S0）
python3 shq_e1_teach_reinterpret.py freeze-base --src $SRC_16x9 --out $RUN --require-16x9

# 2) 吐出 Imagine 功能碼 prompt packs（S1/S2）
python3 shq_e1_teach_reinterpret.py emit-prompts --out $RUN

# 3) 人工／Imagine 產 empty → 登記
python3 shq_e1_teach_reinterpret.py register-empty --out $RUN --path $EMPTY [--confirm]

# 4) 登記 3D teaching 板
python3 shq_e1_teach_reinterpret.py register-teach --out $RUN --unit U0 --kind pose --path $TEACH

# 5) 寫入反解契約（有 parts 才 S3 PASS）
python3 shq_e1_teach_reinterpret.py write-reinterpret --out $RUN --contract $CONTRACT.json

# 6) 閘
python3 shq_e1_teach_reinterpret.py gate --out $RUN
python3 shq_e1_teach_reinterpret.py status --out $RUN
```

### shq_cli 別名

```bash
python3 shq_cli.py e1 --out $RUN init
python3 shq_cli.py e1 --out $RUN freeze-base --src $SRC --require-16x9
python3 shq_cli.py e1 --out $RUN emit-prompts
python3 shq_cli.py e1 --out $RUN gate
```

### Imagine 功能碼（與 packs 對齊）

```text
S0  text_to_image 16:9 BASE  或 既有 SRC 縮放／裁切至 16:9 後 freeze
    → create_asset 等價：freeze-base 寫 SHA + LARGE.FRAME

S1  image_to_image(SRC)：同構去人物／機甲，只留背景
    → register-empty（--confirm 才 S1_CONFIRMED）

S2  image_to_image / reference_to_image：pose|cad|explode|macro 教學板
    → register-teach（教學不改 SRC 座標）

S3  讀 teaching → 填 REINTERPRET_CONTRACT（部件範圍／接合／遮擋）
    → write-reinterpret

S4+ 禁：未 gate elev_allowed 前禁止 E5 elev／E3 補邊
```

### 16:9 契約

```text
aspect = W/H
|aspect - 16/9| / (16/9) ≤ 0.02   # --require-16x9
LARGE.FRAME = TL(0,0) TR(W-1,0) BR(W-1,H-1) BL(0,H-1)
```

違規 → **E-89**。中途換 BASE 未 freeze → **E-83**。未 S2+S3 就 elev → **E-90**。

### 產物樹

```text
$RUN/
  S0_BASE_FREEZE.json
  E1_STATE.json
  base/00_SRC_BASE_*
  empty/  teach/  reinterpret/  prompts/  audit/  docs/
```

### 狀態
`ACCEPT_FULL_HD=false` · `success_allowed=false` 直到完整閉環 + 人審。

---

## §13 · Teach → SRC Correspondence Lock（教學全相 → 原圖關係鎖）

**write 01350 · formal `SHQ_TEACH_SRC_CORRESPONDENCE_LOCK_V0`**

### 根因位置

S2 教學板與 S3 REINTERPRET 之間，長期**缺運算子**：

```text
ALL teach plates (pose/cad/explode/macro)
        → 組件全相 catalog
        → correspondence graph ↔ SRC units/parts
        → relationship lock（join / occlusion / pose resonance）
        → 回 / 放 / 解 / 升 / 拼 能力綁在鎖上
```

沒有這層就宣稱 elev／FULL HD → **E-91**。

### 模組

```bash
python3 shq_teach_src_correspond_lock.py selftest
python3 shq_teach_src_correspond_lock.py build-catalog --run $RUN
python3 shq_teach_src_correspond_lock.py lock --run $RUN [--rebuild-catalog]
python3 shq_teach_src_correspond_lock.py status --run $RUN
```

### V0 能力（誠實）

| 有 | 無 |
|----|----|
| 教學板 FG + explode 連通域 catalog | 深度訓練神經網（slot 已留） |
| HSV+DNA structure-tensor 特徵 | 端到端 part embedding 學習 |
| 與 SRC 契約部件 name+cosine 匹配 | 把 match 當 production_part_claim |
| join 關係鎖 + ops 回放解升拼 註記 | 自動開 elev / ACCEPT_FULL_HD |
| 寫入 `correspond/CORRESPONDENCE_GRAPH.json` | 替代 S1 reverse / E3 閉邊 |

`neural_net=false` · `production_claim=false` · 未來 NN/SAM 必須寫入**同一 edge schema**。

### 功能碼流程（接 E1）

```text
S0 freeze-base
S1 empty → register-empty
S2 teach → register-teach ×N
S3 write-reinterpret（parts 種子）
S3-LOCK  shq_teach_src_correspond_lock.py lock --run $RUN   ← §13
S4 DNA / E3 閉邊（僅在 graph 存在後）
S6 elev 僅 closed-edge RGB 且 elev_allowed
```

### 產物

```text
$RUN/correspond/
  TEACH_COMPONENT_CATALOG.json
  CORRESPONDENCE_GRAPH.json
  PRIMARY_MAP.json
  01_CORRESPOND_LOCK_OVERLAY.jpg
```

### E 碼

| 碼 | 名 |
|----|----|
| E-91 | CLAIM_ELEV_WITHOUT_CORRESPOND_LOCK |
| E-92 | TEACH_CATALOG_EMPTY |
| E-93 | SRC_PART_WITHOUT_TEACH_MATCH |

### 姿態共振（與 S3 同憲）

教學 = 完整多面原件；SRC = 活姿與場景位。  
Correspondence lock **只鎖身份與接合關係**，不得用教學 freeframe 姿替換 SRC 回位姿。

### 狀態

DIAG_LOCK_V0 可報告 match_rate；**ACCEPT_FULL_HD 仍 false**。



---

## §13b · Full-Phase Relation Lock Network V1（01351）

**formal `SHQ_TEACH_FULLPHASE_RELATION_LOCK_NET_V1`**

把 **ALL 教學圖** 中同一 `unit+part_stem` 的多視（pose/cad/explode/macro）融成 **全相節點**，再與原圖 SRC 部件做對應，並組成 **關係鎖網路**（correspond 邊 + join 邊 + unit 對峙邊）。

```text
ALL teach plates
  → raw components (V0 catalog)
  → full-phase fuse (multi-view mean feature)
  → bipartite match → SRC parts
  → RELATION_LOCK_NETWORK
        L_teach_fullphase
        L_src_parts
        L_units
        edges_correspond / edges_join / edges_unit
```

姿態：教學管身份與全相；**SRC 管活姿與回位**。  
`neural_net=false`（圖網路 + 特徵）；深度 embedding 可替換 `fused_feature`，**schema 不變**。

產物：`$RUN/correspond_net_v1/`


---

## §14 · 原圖手 ↔ 教學手 · DNA 象素連算子（01352）

**formal `SHQ_DNA_PIXEL_HAND_LOCK_V1`**

### 功能碼意圖

```text
原圖手 (SRC)
    ← Grok / 區域認（ARM distal ROI）
教學圖中的手（可能不同角落 / 多視 pose）
    ← 遠端 extremity 搜 FG，不靠畫面絕對角
DNA 象素「神經」連算子 PY
    structure-tensor 慣性場 + 局部 hist → 64-d dna_descriptor
    bipartite affinity（同 unit + 同 side 加權）
對位成功
    align_ok ⇔ score ≥ 0.55
    回：SRC corners_4_L
    放：教學只供身份全相
    解：手 ⊂ ARM
    升：僅閉邊內 DNA densify（仍 gated）
    拼：腕接 ARM join
```

### CLI

```bash
python3 shq_dna_pixel_hand_lock.py selftest
python3 shq_dna_pixel_hand_lock.py lock --run $RUN
```

### 產物

```text
$RUN/dna_hand_lock/
  DNA_HAND_LOCK_REPORT.json
  01_DNA_HAND_LOCK.jpg
```

### 誠實邊界

| 是 | 否 |
|----|----|
| 可呼叫 PY 連算子 | 已訓練 GPU 深度手部 NN |
| DNA 象素場對位 | 替代整機 elev |
| 教學手可在任意角落 | production_claim / FULL HD |

深度 embedding 可替換 `dna_descriptor`，**I/O schema 不變**。


---

## §14b · 先頭（HEAD-first）DNA 部件鎖（01353）

**formal `SHQ_DNA_PIXEL_PART_LOCK_V1`**

手路徑曾錯焦（腳／靴／空框）。**改先鎖頭**，同一 DNA 連算子，部件可切換。

### 功能碼

```text
原圖頭 (SRC HEAD / HEAD_HELMET)
    ← 契約部件 ROI
教學圖頭（pose/cad 多視；身可在任意角落）
    ← 每個 body CC 上緣 ~18% = head
DNA 象素連算子
    dna_descriptor 64-d · cosine affinity · unit 對齊
對位成功
    HEAD_ALIGN_OK · corners_4_L 回位鍵
之後才 hand / 其他部件
```

### CLI

```bash
python3 shq_dna_pixel_part_lock.py selftest
python3 shq_dna_pixel_part_lock.py lock --run $RUN --part head   # 先試頭
python3 shq_dna_pixel_part_lock.py lock --run $RUN --part hand  # 頭通過後
```

### 產物

```text
$RUN/dna_head_lock/
  DNA_HEAD_LOCK_REPORT.json
  01_DNA_HEAD_LOCK.jpg
```

### 順序

`head → (OK) → hand → …` · 禁止再以手當第一驗證部件。  
elev / FULL HD 仍 false。


---

## §15 · 同部件多方位轉向 · Motion DNA（01354）

**formal `SHQ_DNA_MOTION_HEAD_TURNTABLE_V1`**

### 意圖（對齊 video 保身份轉向）

參考：多視 identity-consistent video / character sheet turnaround  
（如 SpinMeRound、HarmoView／大角度保臉、角色多視 ref 再生成）

```text
同一部件（先 HEAD）× 大量不同方位教學
    Imagine 8-view turntable（正/斜/側/背…）
        → 每視 DNA 象素描述子
        → Motion DNA bundle
              identity_dna = mean(views)     # 身份錨（類 video ref）
              motion_dna   = turn trajectory  # 轉向路徑
              view_dna[]   = 各方位
SRC 頭
        → 對所有 view 取 max cosine
        → 與 identity_dna 融合
              score = 0.55*best_view + 0.45*identity
        → 對位成功（可轉向仍鎖同一頭）
```

### 功能碼

```text
1. image_to_image(SRC): multi-azimuth HEAD turntable ONLY（8+ 方位，同身份）
2. register plate → teach_motion_head/
3. DNA split cells → motion bundle
4. lock SRC head ↔ motion DNA
5. corners_4_L 仍用 SRC（活姿）；教學只供全相身份＋轉向 DNA
```

### 產物

```text
$RUN/dna_motion_head/
  U0_HEAD_TURNTABLE.jpg / U1_HEAD_TURNTABLE.jpg
  U*_viewXX.jpg
  MOTION_DNA_BUNDLES.json
  MOTION_DNA_HEAD_REPORT.json
  01_MOTION_DNA_HEAD_LOCK.jpg
```

### 憲

- 先頭，且教學必須 **多方位同部件**（單張 freeframe 不足）
- elev_remap=false；FULL HD false
- 深度 embedding 可替換 dna_descriptor，schema 不變


---

## §16 · 同機位 EMPTY（BG-NCC）→ S1 confirm → 凍 alpha 材質（01356）

**問題**：去主體後全圖 NCC 必降，不能用 full-NCC≥0.85 當同機位 empty 唯一閘。

**正確閘（same-cam）**

```text
ncc_bg >= 0.95          # 僅 ~mask 背景
off_mask_mae < 2
phase_px < 2
subj_bg >= 25
on_mask_mae > 20        # 主體區確有改寫
```

**EMPTY 構造**

```text
hybrid: SRC 像素鎖背景 | Imagine/inpaint 只寫 subject mask
```

**材質**

```text
Imagine 任意 freeframe RGB
  → material_fill：只映射進凍結 alpha
  → alpha XOR = 0 · elev_remap = false
  → S* NEAREST alpha · hardpaste · SHA + IoU
```


---

## §17 · Grok 智能「只留部件／無背景」→ 反推定位全 DNA 部件（01357）

**formal `SHQ_GROK_ISOLATE_PART_LOCATE_V1`**

### 產品意義（你說的覆用）

```text
Grok Imagine edit：
  「把圖中其他東西除掉，只剩 {PART}，沒背景」
        ↓
  隔離出純部件 cutout（黑底）= 該件 DNA 源
        ↓
  PY 反推：multi-scale template + DNA 在 SRC 上定位
        ↓
  corners_4_L + 閉邊 alpha 種子
        ↓
  同一套邏輯 → head / torso / arm / legs / weapon / …
```

不是手畫 AABB 猜框，而是 **Grok 認件 → 再反鎖回原圖**。

### 功能碼

```text
1. create_asset(SRC)
2. image_to_image(SRC):
     Extract ONLY the {unit} {PART}.
     Pure solid black background. No body extras. No scene.
3. shq_grok_isolate_part_locate.py locate \
     --run $RUN --unit U0 --part head --isolate $CUTOUT
     [--search x,y,w,h]   # 建議：head 用 unit 上 32% 帶
4. 產出 corners_4_L + LOCATED_RGBA（凍邊種子）
5. 後接 §14b DNA / §15 motion / §16 mat_fill（elev_remap=false）
```

### 可覆用 part_id

| part | Imagine 隔離句要點 |
|------|-------------------|
| head | ONLY HEAD，無肩無身 |
| torso | ONLY TORSO，無頭無腿 |
| arm_l / arm_r | ONLY 該臂 |
| legs | ONLY LEGS |
| weapon / backpack | ONLY 該件 |

### CLI

```bash
python3 shq_grok_isolate_part_locate.py selftest
python3 shq_grok_isolate_part_locate.py prompts
python3 shq_grok_isolate_part_locate.py locate --run $RUN --unit U0 --part head --isolate cutout.jpg
```

### 產物

```text
$RUN/grok_isolate_locate/
  U0_HEAD_ISOLATE_GROK.jpg     # Grok 只留頭
  U0_head_LOCATED_RGBA.png     # 反推 SRC 上的頭
  U0_head_OVERLAY.jpg
  U0_head_LOCATE.json
```

### 與 DNA 網關係

| 層 | 角色 |
|----|------|
| Grok isolate | **認是什麼部件**（智能切） |
| locate PY | **原圖哪裡**（座標） |
| DNA / motion DNA | **身份全相／轉向** |
| mat_fill | **凍 alpha 升材質** |

### E 碼

| 碼 | 禁 |
|----|-----|
| E-94 | MANUAL_AABB_AS_GROK_ISOLATE — 手框冒充 Grok 隔離 |
| E-95 | ISOLATE_WITHOUT_LOCATE — 有 cutout 不反推 SRC |
| E-96 | HEAD_SEARCH_FULL_BODY — 頭搜索全 unit 易鎖到胸腿金網 |

### 誠實

- Grok freeframe 姿態可異於 SRC → 必須 **unit 分帶搜索**（頭=上段）
- template 低、DNA 高 → 可能紋理誤配；以 **head band + score 結構** 為準
- production / FULL HD 仍 false，直到閉邊人審


---

## §17b · 同姿隔離 POSEMATCH（換圖角度 = 原圖部件角度）（01358）

**formal `SHQ_GROK_ISOLATE_POSEMATCH_V1`**

### 問題
§17 freeframe「只留頭」常變成 **產品棚拍正面**，與 SRC 活姿角度不同 → DNA 紋理似但 **定位漂**（如 U1 鎖到胸）。

### 強制邏輯

```text
WRONG:
  image_to_image(FULL SRC) → freeframe product head（可轉角）

RIGHT:
  1) make-seed：從 SRC 裁 peep（已是原圖角度）
  2) image_to_image(POSESEED)：
       只去背 → 純黑底
       禁止轉頭 / freeframe / 重設計
       保持 EXACT same angle, pose, silhouette
  3) locate(POSEMATCH isolate) → corners_4_L
```

### CLI

```bash
python3 shq_grok_isolate_part_locate.py make-seed \
  --run $RUN --unit U0 --part head --box x,y,w,h

# Imagine: image_to_image(POSESEED, prompt=POSELOCK)

python3 shq_grok_isolate_part_locate.py locate \
  --run $RUN --unit U0 --part head --isolate $POSEMATCH_CUTOUT
```

### Prompt 契約（功能碼）

```text
From this crop ONLY: remove background to pure solid black.
Keep EXACT same angle, pose, scale, silhouette as the input.
Do not redesign, do not turn, do not freeframe studio product shot.
```

### E 碼

| 碼 | 禁 |
|----|-----|
| E-97 | FREEFRAME_ANGLE_DRIFT — 隔離件角度與 SRC peep 不一致仍當 DNA 源 |
| E-98 | FULLSRC_ISOLATE_AS_POSEMATCH — 用全圖 isolate 冒充同姿 peep 隔離 |

### 驗收

| 指標 | 含義 |
|------|------|
| seed peep 角度 | = SRC 部件 |
| isolate 與 seed 輪廓/朝向 | 應一致（目視 + DNA） |
| locate score | 通常高於 freeframe |
| corners_4_L | 落在 peep 鄰域 |

### 狀態
U0 POSEMATCH 已驗證；U1 同流程。FULL HD 仍 false。


---

## §18 · CLIP MASK 回扣升清回位（01360）

**formal `SHQ_CLIP_MASK_ELEV_RETURN_V1`**  
**PY** `shq_clip_mask_elev_return.py`

### 優改鏈（功能碼）

```text
① edit 去背
② edit 去「頭以外」→ 只剩部件 cutout（同姿 §17b）
③ 回扣舊圖 → CLIP MASK
      isolate FG 對齊 peep／locate B
      clip_alpha 凍在 peep 外形（硬 alpha，禁 feather 亂邊）
④ 升清／材質
      只用 clip 框外形當生成／映射邊界
      框內可 HD；框外不改
      elev_remap = false
⑤ 框框對框框 hardpaste
      return_key = part_id + corners_4_L(B)
      位合一致：B 不變、alpha XOR=0
⑥ 不夠清晰 → 再 edit 除外物 → 重跑 ③–⑤
```

### 為何鎖得住

| 層 | 鎖什麼 |
|----|--------|
| peep / B | 大圖上的位置（四角） |
| clip_alpha | 部件外形（回扣 isolate） |
| HD RGB | 只填 clip 內 |
| hardpaste | box-to-box，不 elev 挪座標 |

**不是** 放大後再猜位；是 **先鎖 clip 框，再生成框內**。

### CLI

```bash
# 接 POSEMATCH isolate + locate B
python3 shq_clip_mask_elev_return.py run --run $RUN

# 單件 + 可選 HD 材質圖
python3 shq_clip_mask_elev_return.py run --run $RUN \
  --unit U0 --part head --box x,y,w,h \
  --isolate $POSEMATCH.jpg --hd $HD_RGB.jpg
```

### Imagine 步驟對應

| 步 | 功能碼 |
|----|--------|
| 去背／只留頭 | `image_to_image(POSESEED, POSELOCK)` §17b |
| （可選）再除外物 | `image_to_image(isolate, "remove non-head extras, black bg")` |
| 回扣 | **PY** reverse clip on peep — 非 elev |
| 框內升清 | `image_to_image(peep)` 或 densify → **map into clip** |
| 回位 | hardpaste @ corners_4_L |

### E 碼

| 碼 | 禁 |
|----|-----|
| E-99 | FEATHER_CLIP_AS_GEOMETRY — soft alpha 當幾何邊 |
| E-100 | HD_OUTSIDE_CLIP — 升清改到 clip 外 |
| E-101 | ELEV_REMAP_AFTER_CLIP — 有 clip 仍 elev 改 B |
| E-102 | FREEFRAME_HD_AS_CLIP — 用 freeframe 整機當 clip 外形 |

### 閘

| 閘 | 條件 |
|----|------|
| alpha_xor | = 0（輸出 alpha ≡ clip） |
| elev_remap | false |
| box_to_box | paste 尺寸 = B |
| corners_4_L | 與 locate 相同 |

### 狀態
接 1920 POSEMATCH 試跑；ACCEPT_FULL_HD 仍 false（真 HD 生成可後掛 --hd）。


---

## §18b · 兩 MASK 交叉倒扣（修正跳步）（01361）

**formal `SHQ_CLIP_MASK_PAIR_REVERSE_V1`**  
**PY** `shq_clip_mask_pair_reverse.py`

### 你指出的錯（01360 跳步）

```text
錯：peep 灌水 / isolate 硬 resize 到 locate B
    → 沒有「頭的空框位」
    → 認框方法不對

對：clip 完頭之後，reverse 倒扣舊圖
    → 得到的是「頭的空框位」M_slot
    → 再與 isolate 的 M_iso 兩 mask 交叉對準
    → 一對就除／對準，不是單圖瞎猜 B
```

### 正確鏈

```text
① edit 去背 / 只留頭     → isolate cutout
                           M_iso = FG(isolate)

② edit 去頭（或去物件） → EMPTY 景（同機位）
                           M_slot = reverse(SRC, EMPTY)
                           = 頭／主體的「空框位」mask（全圖座標）

③ 兩 mask 交叉對準
     align(M_iso 或 isolate,  落入 M_slot 的搜索窗)
     M_clip = warp(M_iso) ∩ M_slot
     （對不準 → 不准用 peep flood 冒充）

④ 框內升清
     HD 只填 M_clip；B = 對準後 corners_4_L

⑤ 框框對框框 hardpaste
     elev_remap = false

⑥ 不清 → 再 edit 除外物 → 重 ①–⑤
```

### 數學

\[
M_{\mathrm{slot}}=\mathbf{1}\big[\mathrm{med}\big(0.55\|I_{\mathrm{src}}-I_{\mathrm{empty}}\|_{\mathrm{RGB}}+0.45\|I_{\mathrm{src}}-I_{\mathrm{empty}}\|_{\mathrm{LAB}}\big)\ge\tau\big]
\]

\[
(B^*,R^*)=\arg\max_{B,R}\ \mathrm{TM}\big(I_{\mathrm{src}}|_{M_{\mathrm{slot}}},\ R(I_{\mathrm{iso}})\big)
\]

\[
M_{\mathrm{clip}}=R^*(M_{\mathrm{iso}})\ \cap\ M_{\mathrm{slot}}
\]

### CLI

```bash
# 必備：真 EMPTY（去頭/去物件，同機位）
python3 shq_clip_mask_pair_reverse.py run \
  --run $RUN \
  --empty $EMPTY.jpg \
  --isolate $POSEMATCH_HEAD.jpg \
  --hd $HD.jpg \
  --unit U0
```

### E 碼（新增）

| 碼 | 禁 |
|----|-----|
| E-103 | PEEP_FLOOD_AS_SLOT — peep 灌水冒充 reverse 空框 |
| E-104 | ISO_RESIZE_WITHOUT_PAIR — isolate 硬縮放到 B 不經 M_slot 對準 |
| E-105 | SLOT_WITHOUT_EMPTY — 無 EMPTY 宣稱 reverse clip |
| E-106 | PAIR_SKIP_INTERSECT — 不對準就硬貼 |

### 與 §18 關係

| 版 | 角色 |
|----|------|
| §18 01360 | 框內 HD 填＋hardpaste 工具（可留） |
| **§18b 01361** | **認框／clip 真源**：M_iso × M_slot pair |

**認框只准 pair reverse；不准 skip 到 peep flood。**


---

## §18c · DEBUG：外框 ≠ 鏤空（01362）

**用戶判決（正確）：**「peep/clip 反的是外框，是不可能鏤空發生」

### 詞義

| 詞 | 是什麼 | 能否鏤空貼回 |
|----|--------|--------------|
| **外框 AABB** | 只有 `x,y,w,h` 的矩形 | **否** — 無頭形邊界 |
| **peep 外框** | 裁窗矩形 | **否** — 同外框 |
| **M_slot reverse** | SRC−EMPTY 的**實心空位形**（被扣走的剪影域） | 支援定位；本身是「空位形」不是畫框中空環 |
| **M_iso cutout** | edit 只留頭的**硬 alpha 外形** | **是 — 鏤空外形** |
| **M_clip** | `warp(M_iso)` 落在 SRC 上 | **是 — 場景鏤空 mask** |

### 我曾跳錯的步

```text
錯：clip := peep 外框 / B 矩形 / flood 填框
    reverse 外框 → 永遠只有方塊
    → 鏤空不可能發生

對：clip := M_iso 鏤空外形（剪影）
    reverse := M_slot 空位形（剪影）
    pair := 形對形（不是框對框）
    B := 對準後由 M_clip 內容 bbox **派生**，B 不是 clip 定義
```

### 硬規則

1. **禁止**用 peep/outer rect 定義 clip  
2. **禁止**把 B 當成 clip  
3. paste **只**在 `M_clip>0`  
4. 兩 mask 交叉 = `M_iso × M_slot` 形對形  

### E 碼

| 碼 | 禁 |
|----|-----|
| E-107 | OUTER_FRAME_AS_CLIP — 外框當 clip／鏤空 |
| E-108 | PEEP_RECT_AS_HOLLOW — peep 矩形冒充鏤空 |



---

## §18d · EDIT 幾何契約引擎（01363）— 不再發明識別流

**formal `SHQ_CLIP_MASK_ELEV_RETURN_V1`**  
**PY** `shq_clip_mask_elev_return.py`  
**模式** `LOCAL_EDIT`（≠ 完整 3D 原件重建）

### 一句話

> 框已鎖、clip 已鎖、mask 與邊界已鎖；**edit 只改框內 RGB**；完成後必須按**原框、原邊界、原位置**覆回。  
> 生成再漂亮，也**不得**改形狀、比例、位置。

### EDIT 必須遵守的鎖（既定輸入，不是每次重發明）

| 部分 | 功能 |
|------|------|
| 原圖 SRC / SHA / 尺寸 | 凍結 |
| corners / 原位 | 凍結；生成結果不可重定 |
| **M_iso** | 隔離硬剪影（**不是** peep 矩形） |
| **M_slot** | 同鏡 EMPTY reverse 空位剪影 |
| **pair / T** | 形對形；禁 resize 灌水猜位 |
| **M_clip** | `warp(M_iso,T) ∩ M_slot` = 唯一可編輯區 |
| **B** | 由 M_clip **派生**；B ≠ 邊界本身 |
| HD RGB | **只**在 M_clip 內 |
| RETURN | 硬貼；clip 外 **bit-exact** |
| elev_remap | **false** |

### 正確次序

```text
1 SRC 凍結
2 EDIT ISOLATE → M_iso
3 EMPTY-BG REVERSE → M_slot
4 SHAPE-TO-SHAPE PAIR → T, M_clip
5 LOCKED-CLIP UPSCALE/EDIT → 只改 RGB
6 HARD RETURN → SRC
7 幾何+回位驗收 → 才 ACCEPT_LOCAL_EDIT
```

### 四個必防

1. peep 矩形 ≠ clip  
2. 外框 reverse ≠ 鏤空  
3. 升清不得改幾何（feather/拉伸/翻轉/改四角禁）  
4. 低信心 pair → **BLOCK**（禁 BBox/flood 假成功）

### 驗收（不止 alpha_xor=0）

| 閘 | 要義 |
|----|------|
| alpha_xor=0 | 同一張 mask 用於升清前後（必要不足） |
| pair 同部件 | M_iso↔M_slot 真同一件 |
| 輪廓/原位 | 配準後邊界吻合 |
| outside bit-exact | M_clip 外原圖像素不變 |
| no overflow | 不超出 clip、無鬼影錯覆 |
| corners 契約 | 與鎖定一致 |

### 架構邊界

| 模式 | 允許 |
|------|------|
| **LOCAL_EDIT** | 鎖原剪影，只改內容 |
| **FULL_3D_REBUILD** | 可生成未顯示結構 — **另軌驗收**；禁偷擴舊 clip 冒充 LOCAL_EDIT |

### CLI

```bash
# selftest（合成形對形 + poison BLOCK）
python3 shq_clip_mask_elev_return.py selftest --out /tmp/shq_edit_selftest

# 實景 LOCAL_EDIT
python3 shq_clip_mask_elev_return.py edit \
  --run $RUN \
  --empty $EMPTY.jpg \
  --isolate $KEEP_PART_ONLY.jpg \
  --hd $HD_RGB.jpg \
  --unit U0 --part head \
  --pair_score_min 0.35
```

### 與 §18c 關係

§18c 定：**剪影對剪影**（外框不能鏤空）。  
§18d 定：**EDIT 引擎如何在鎖下只改內容並硬回**。

**附件敘述 ≠ runtime 已接線。** 以本 PY + selftest PASS + 實跑 gates 為準。


---

## §19 · EDIT 一生一除差分 Clip（01364）

**formal `SHQ_EDIT_PAIR_DIFFERENTIAL_CLIP_V1`**  
**PY** `shq_edit_pair_differential_clip.py`  
**替換** Clip Mask **Producer**（不整包重寫 RETURN）

### 質疑（成立）

> 既然 EDIT 的「生／除」已能產生頭部形狀，為何還另叫程式猜一次頭部外框／獨立 M_iso？

### 新鏈

```text
① I_keep  生／保留頭   同畫布同鏡位
② I_remove 除／去頭     同 SRC 只去頭
③ D = Diff(I_keep, I_remove)
④ M_head = Support(D)   〔優先 ∩ native edit_mask〕
⑤ 反扣 SRC（必要時 phase 對齊）
⑥ 鎖 M_head 只改 RGB → hard return
```

\[
D=\operatorname{Diff}(I_{\mathrm{生}},I_{\mathrm{除}}),\quad
M_{\mathrm{head}}=\operatorname{Support}(D)
\]

### 對照

| 舊 | 新 |
|----|-----|
| 獨立 isolate 猜輪廓 | EDIT 生／除配對差分 |
| SRC−EMPTY + 外 mask 配 | 兩 EDIT 狀態直接差分 |
| peep/BBox 猜位 | 差分剪影給形+位 |
| M_iso×M_slot 再配準 | 同源座標天生對應 |
| 失敗補 polygon | **BLOCK → 重做 EDIT** |

### 閘

| 閘 | |
|----|--|
| canvas 同尺寸／同鏡 | 盡量 native；resize 需標 |
| **bg_stable** | 非頭區 mean/p95 差分上限，失敗 = 重做 EDIT |
| head_support_px | 最小像素 |
| multi_blob | 可選 BLOCK |
| α_xor=0 · outside bit-exact · elev_remap=false | 覆回 |

### CLI

```bash
python3 shq_edit_pair_differential_clip.py selftest --out /tmp/pd_st
python3 shq_edit_pair_differential_clip.py produce \
  --run $RUN --keep $I_KEEP.jpg --remove $I_REMOVE.jpg \
  --unit U0 --part head [--hd $HD.jpg] [--edit_mask $NATIVE.png]
```

### 與 §18d

§18d = EDIT 鎖下只改 RGB 硬回。  
§19 = **M_clip 從哪來**：一生一除差分，不另猜頭。



---

## §19b · 同機位 inpaint 除 + native edit_mask（01365）

兩條都試；**生產預設優先 A/B，不優先 C。**

### A · 同機位 inpaint 級「除」
seed → dilate → native_edit_mask → inpaint only inside → outside = SRC bit-exact.
I_keep=SRC; M_head = native ∩ Diff（Diff 弱則用 native）。

### B · Hybrid AI 除 + native
AI full-frame 只 paste 進 native mask；outside bit-exact。

### C · 全幅 AI + 純 RGB Diff（對照）— bg 漂，outside 不 exact。

### D · 全幅 AI + native 閘 Diff — 次於 A/B。

### 優先序
1. native edit_mask 優先於純 RGB Diff  
2. seed 存在 → 先 A 或 B 造 I_remove  
3. Diff 在 native 內 refine；弱 → 整張 native  
4. 全幅 AI 無 mask → DIAG，不 ACCEPT  



---

## §19c · 洞回洞（01370）— 不是「框回」

**误会：** 把 return 做成矩形 peep / B 框贴回 → 灰底板、elev 画布进景。

**正解：** edit clip 是 **洞回洞**：

```text
生 I_keep = SRC（头在）
除 I_remove = 同机位去头（洞出现）
D = Diff(生, 除)
M_hole = Support(D)     ← 真正的 clip = 空位剪影
elev RGB 只写入 M_hole
hard return：洞外 bit-exact
```

| 禁止 | 必须 |
|------|------|
| 矩形 B 当 clip | clip = M_hole 剪影 |
| peep 窗外填灰再贴 | 洞外保持原图像素 |
| 框对框 resize 回 | 洞对洞（shape hole） |

B 只作运算窗口，**不是**边界本身。


## §19d · ROI 锁洞边升清（01371）

几何仍硬 `M_hole`；**内容**强度用距离场：

```
w = power(smoothstep(dist_to_edge / dmax), 1.6)
out = (1-w)·SRC + w·HD_densify   # 仅洞内
```

| 位置 | w | 变化 |
|------|---|------|
| 洞边 | →0 | 低变，贴原像素 |
| 中心 | →1 | 升清最强 |

禁止用 soft alpha 改几何；w 只调 RGB 混合强度。


## §19e · 反洞 clip 必须洞形对洞形（01372/01373）

DEBUG：`IoU(HD_freeframe_mask, M_hole)` 低 + freeframe 灌洞 → **内容没回对洞**。

| 错 | 对 |
|----|----|
| freeframe 整盔 bbox 拉伸进 B | peep **低频结构** 锁死 |
| 只靠 ROI w 边权 | dens **高频细节** 注入洞内 |
| 洞外被误改 | hard `M_hole` 洞回洞 |

```
out = peep_LF + w · dens_HF   # 仅 M_hole
```
NCC(peep,out) 应 ≫ NCC(peep, freeframe灌洞)


## §19f GEOMETRY_LOCKED_MATERIAL_FILL (01378)

真 AI 同姿 ≠ freeframe prompt 碰运气。

```
冻 alpha = M_hole / peep silhouette   # 边、位、尺度锁死
AI RGB  = 任意尺寸材质图             # 可 freeframe，只取材质
fill    = peep_LF + AI_HF  (ROI w)   # 只刷 RGB
return  = hardpaste @ M_hole on SRC×S*
alpha XOR = 0 · elev_remap = false · 洞外 bit-exact
```

禁止：让 AI 重生轮廓／比例／pose 再当 production donor。


## §19g FULL_HOLE_HD_RETURN (01380)

洞是反扣底再反出的剪影 `M_hole`，不是需要再 feather 的矩形。

```
M_hole = Support(Diff(I_keep, I_remove))   # 已是真 ROI
w(x,y) = 1  if M_hole   else  0            # 全洞高清，禁止边弱心强把盔缘留低清
out    = SRC*(1-M) + HD_fill*M
洞外 bit-exact · elev_remap=false · alpha 冻的是边，不是冻低清
```

旧 ROI 边弱：只在对位不稳时作诊断；不得当 production 洞回默认。


## §19h EDIT_MULTILAYER_HOLE (01381) — 极用 Imagine 原生 EDIT

洞不是后算剪影主路径；洞来自 EDIT 图层关系（如 PS 魔棒）：

```
每次:
  EDIT 除背  → NO_BG
  EDIT 除头  → NO_HEAD          # 有背无头
  EDIT 除头@NO_BG → NO_BG_NO_HEAD
  EDIT 只头  → HEAD_PLATE
  EDIT 色相键 → MAGENTA/CYAN 头  # 魔棒探测器

关系:
  有头×有背 = SRC
  无头×有背 = NO_HEAD
  有头×无背 = NO_BG
  无头×无背 = NO_BG_NO_HEAD

M_hole = Support(|有头−无头|) ∪ ChromaKey(EDIT色相)
       （优先无背差分，bg 漂移更低；色相键给硬边）

回洞: w=1 全洞 HD · elev_remap=false · 冻的是 EDIT 认的边
备选: 就算用剪影，也先 EDIT 把头变成探测器能全扣的色相
```


## §19i HOLE_FRAME_INPAINT_ELEV (01382) — 禁止偷步

高清必须在**洞框内 INPAINT 生成**，不得 freeframe 后再 map 塞洞。

```
1 EDIT 扣: 除头/色相键 → 得到洞 (M_hole)
2 EDIT 洞内 INPAINT: 在无头图或色相洞上，只重生洞内 HD
3 覆回: out = SRC; out[M_hole] = INPAINT[M_hole]
   洞外 bit-exact · elev_remap=false

偷步 = 扣洞 与 生成 断开（另生 freeframe 再硬贴）→ 必错位
对   = 生成坐标系 = 洞坐标系 = SRC 坐标系
```


---

## §19j RESET_DONOR · EDIT 多層洞 × 洞內 INPAINT · DEBUG 全問（01383）

**formal `SHQ_EDIT_HOLE_INPAINT_DEBUG_CHAIN_V1`**  
**LOCK** `CONSTITUTION_LOCK_01383.json`  
**前置** §19h 多層 EDIT · §19i 洞內 INPAINT · **本節 = 合併 + RESET DONOR + DEBUG 質問生成**

### 0. RESET DONOR（每次新鏈強制）

```text
RESET_DONOR = true
  禁止沿用：舊 peep donor、HARDFILL mask、freeframe densify map、
            舊 LOSR soft、舊 matfill donor、舊 warp 進洞結果
  允許輸入：僅 SRC（S0 freeze）
  允許工具：僅 Grok Imagine 原生 image_to_image EDIT + 差分/色相扣洞 PY
  允許 HD：僅「在洞框內 INPAINT」產出的像素
```

**E-99 RESET_DONOR_VIOLATION** — 鏈上出現舊 donor 路徑仍當 production → BLOCK

---

### 1. 你要的過程（一句不漏）

```text
① 每次用 EDIT 除背
② 再用 EDIT 把頭變成「反扣的洞位」（無頭圖）
③ 重點：頭 × 無頭  與  有背 × 無背  的圖圖關係
④ 在 EDIT 功能中扣出「回洞／回框」的多層 LAYER（如 PS 魔棒）
⑤ 不是手算剪影主路徑 —— EDIT 早已能認頭邊；
   若不能，是沒用 EDIT 洞回，不是模型不會
⑥ 備選：EDIT 把頭改成色相鍵（品红／青）→ 探測器全扣
⑦ 極用 Imagine 原生 EDIT
⑧ 【不可少】高清必須在洞框中 INPAINT 生成
   —— 扣與洞的關係層一偷步（另生 freeframe 再塞）必錯位
```

---

### 2. DEBUG 式質問生成（執行前／中／後必答）

每一步產物落地前，**生成並寫入** `DEBUG_QA.json` 對應項；任一答「否」→ 停，不准跳下一步。

#### Q0 · RESET

| # | 質問 | 合格答 |
|---|------|--------|
| Q0.1 | 本輪是否聲明 RESET_DONOR=true？ | 是 |
| Q0.2 | 輸入是否只有 SRC SHA（無舊 donor 目錄）？ | 是 |
| Q0.3 | 是否仍引用 peep densify / freeframe map 當 HD？ | **否** |

#### Q1 · EDIT 除背

| # | 質問 | 合格答 |
|---|------|--------|
| Q1.1 | 是否呼叫 Imagine `image_to_image(SRC)` 除背？ | 是 |
| Q1.2 | NO_BG 是否同機位、同畫布比例（非 freeframe 棚拍）？ | 是 |
| Q1.3 | 主體是否仍在、背景是否被抽空？ | 是 |

#### Q2 · EDIT 反扣洞位（除頭）

| # | 質問 | 合格答 |
|---|------|--------|
| Q2.1 | 是否對 **同一 SRC**（及可選對 NO_BG）做 EDIT 除頭？ | 是 |
| Q2.2 | 無頭圖是否只缺目標頭、身／機／景大致保留？ | 是 |
| Q2.3 | 頭洞是否落在原頭位置（非全身蒸發）？ | 是 |

#### Q3 · 關係矩陣（有頭×無頭 × 有背×無背）

| # | 質問 | 合格答 |
|---|------|--------|
| Q3.1 | 是否四格齊？ | 見下表必須落地 |

```text
              有背(SRC 系)         無背(NO_BG 系)
有頭          L0 = SRC            L3 = NO_BG
無頭          L1 = NO_HEAD        L5 = NO_BG_NO_HEAD
色相探測      L4 = MAGENTA/CYAN   （備選魔棒）
頭 plate      —                   L2 = HEAD_ONLY（可選材質，非位姿主權）
```

| Q3.2 | 是否用 **圖−圖** 關係扣洞，而非單張 peep 猜框？ | 是 |
| Q3.3 | 優先差分是否為 **無背有頭 − 無背無頭**（bg 漂移更低）？ | 是 |
| Q3.4 | 是否同時保留 **有背有頭 − 有背無頭** 作交叉驗證？ | 是 |

#### Q4 · 魔棒／色相（EDIT 認邊）

| # | 質問 | 合格答 |
|---|------|--------|
| Q4.1 | 是否用 EDIT 把目標頭改成固色相（#FF00FF / #00FFFF）？ | 建議是 |
| Q4.2 | 色相鍵是否 **只改頭像素**、其餘盡量不變？ | 是 |
| Q4.3 | M_chroma 是否由色相鍵抽出（PS 魔棒等價）？ | 是 |
| Q4.4 | 若差分失敗，是否回到 EDIT 重做，而不是手繪 polygon？ | 是 |

#### Q5 · 多層 LAYER 合成 M_hole

| # | 質問 | 合格答 |
|---|------|--------|
| Q5.1 | M_hole 公式是否為： | |

```text
M_diff_nobg = Support(|L3 − L5|)      # 無背：有頭 vs 無頭
M_diff_bg   = Support(|L0 − L1|)      # 有背：有頭 vs 無頭
M_chroma    = ChromaKey(L4)           # EDIT 魔棒
M_hole      = clean( M_chroma ∪ (M_diff_* ∩ dilate(M_chroma)) )
            # 或 chroma 為主 + 差分修邊；禁止純 bbox
```

| Q5.2 | M_hole 是否硬 α∈{0,255}（無 feather 當生產）？ | 是 |
| Q5.3 | 洞是否完整覆蓋真頭（無大破洞、無整肩誤吃）？ | 人審+面積閘 |

#### Q6 · 【不可少】洞框內 INPAINT 生成 HD

| # | 質問 | 合格答 |
|---|------|--------|
| Q6.1 | HD 是否在 **無頭圖 L1** 或 **色相洞 L4** 上 INPAINT 生成？ | **必須是** |
| Q6.2 | 是否禁止：另開 freeframe 頭 → resize/map 塞進 M_hole？ | **禁止=合格** |
| Q6.3 | 生成 prompt 是否寫死 *INPAINT-IN-HOLE only / same camera / do not freeframe*？ | 是 |
| Q6.4 | 生成坐標系是否 = 洞坐標系 = SRC 坐標系？ | 是 |

```text
偷步（E-100）:
  扣洞 ──×── 另生 freeframe HD ── map 塞洞  → 必錯位

正步:
  扣定義洞 → EDIT 在洞內 INPAINT 生 HD → 只覆洞內像素
```

#### Q7 · 覆回

| # | 質問 | 合格答 |
|---|------|--------|
| Q7.1 | `out = SRC; out[M_hole]=INPAINT[M_hole]`？ | 是 |
| Q7.2 | 洞外 max_diff == 0？ | 是 |
| Q7.3 | elev_remap == false？ | 是 |
| Q7.4 | 是否用舊 donor matfill 代替洞內 INPAINT？ | **否** |

#### Q8 · 全鏈自證

| # | 質問 | 合格答 |
|---|------|--------|
| Q8.1 | 八層（或四格+色相）是否全部落盤可回放？ | 是 |
| Q8.2 | DEBUG_QA.json 是否逐步有答？ | 是 |
| Q8.3 | 任一 Q 失敗是否 BLOCK 而非「先貼再調」？ | 是 |

---

### 3. 功能碼順序（RESET 後唯一合法）

```text
S0   create_asset(SRC) + SHA + RESET_DONOR=true
S1a  EDIT 除背          → L3 NO_BG
S1b  EDIT 除頭@SRC      → L1 NO_HEAD
S1c  EDIT 除頭@NO_BG    → L5 NO_BG_NO_HEAD
S1d  EDIT 色相鍵頭      → L4 MAGENTA/CYAN   （魔棒）
S1e  (opt) EDIT 只頭    → L2 HEAD_PLATE     （非座標主權）
S2   多層扣洞           → M_hole（差分∪色相）
S3   EDIT 洞內 INPAINT  → I_HD（在 L1 或 L4 上生）
S4   覆回               → out[M_hole]=I_HD[M_hole]；洞外 bit-exact
S5   (opt) MAG = out↑S* Lanczos 整圖（對位已在 S3–S4 完成）
S6   DEBUG_QA + ACCEPT 閘（本節 Q0–Q8）
```

**禁止插入：** freeframe densify → warp → 塞洞（任意位置）。

---

### 4. 產物契約

```text
$RUN/edit_hole_inpaint_v1/
  RESET_DONOR.json
  layers/
    L0_SRC.jpg
    L1_NO_HEAD.jpg
    L3_NO_BG.jpg
    L4_CHROMA.jpg
    L5_NO_BG_NO_HEAD.jpg
  masks/
    M_diff_bg.png
    M_diff_nobg.png
    M_chroma.png
    M_hole.png
  inpaint/
    I_HD_on_NOHEAD.jpg
    I_HD_on_CHROMA.jpg
  return/
    RETURN_HOLE_INPAINT.jpg
    RETURN_MAG_*.jpg
  audit/
    DEBUG_QA.json          # 逐步質問答案
    RELATION_MATRIX.jpg
    AB_STEAL_VS_INPAINT.jpg
  SUMMARY.json
```

---

### 5. E 碼（本節）

| 碼 | 名 | 觸發 |
|----|-----|------|
| E-99 | RESET_DONOR_VIOLATION | 沿用舊 donor／freeframe map 當 HD |
| E-100 | HOLE_GENERATE_STEAL | 扣洞與生成斷開（偷步） |
| E-101 | SKIP_EDIT_LAYER | 缺除背／除頭／關係格仍宣稱 M_hole |
| E-102 | HAND_SILHOUETTE_PRIMARY | 手剪影／bbox 冒充 EDIT 魔棒洞 |
| E-103 | INPAINT_NOT_IN_HOLE | HD 不在 L1/L4 洞框內生成 |
| E-104 | OUTSIDE_HOLE_TOUCHED | 覆回後洞外像素被改 |

---

### 6. 與舊節關係

| 節 | 角色 |
|----|------|
| §19h | 多層 EDIT 扣洞（魔棒思想） |
| §19i | 洞內 INPAINT、禁偷步 |
| **§19j** | **RESET DONOR + DEBUG 全問 + 合併唯一合法鏈** |
| §19f/g | matfill／全洞 w=1 僅作 **洞內 INPAINT 之後** 的可選強化，**不得**取代 S3 |

---

### 7. 金句

> **EDIT 除背 + EDIT 反扣無頭 + 有頭/無頭×有背/無背 關係層 = 洞。**  
> **洞內 INPAINT = 唯一合法 HD；freeframe 塞洞 = 偷步 = 錯位。**  
> **魔棒是 EDIT 色相／差分，不是手剪影。RESET DONOR 每次新鏈。**


## §19k 洞/除/扣/生 四態各自不斷出「反」· 禁頭變大（01385）

| 態 | 正 | 反 | 產出 |
|----|----|----|------|
| **洞** | M_洞 剪影空位 | M_反洞 = 全圖−洞 | 只允許在洞內動 |
| **除** | L1 有背無頭 | L0 有背有頭 | 除頭 EDIT |
| **扣** | Diff(有頭,無頭) | Diff 熱圖反查 | 洞的形來自扣 |
| **生** | 洞框內 densify/INPAINT | 生後 peep 反 生前 peep | **同 wh·同面積·禁變大** |

有背 peep 與 無背 peep 必須 **同一洞框 bbox**；頭不得因無背 freeframe 放大。

```
E-105 HEAD_SCALE_GROW — 生 後 content 面積/占框比 > 洞 peep ×1.15 → BLOCK
E-106 FREEFRAME_PEEP_AS_HOLE — 1408 特写头当洞 donor → BLOCK
```


---

## §19l 字詞·走錯·DEBUG·PY 可調用憲（01386）

**憲本:** `SHQ_EDIT_HOLE_FOUR_ANTI_DEBUG.md`  
**PY:** `shq_edit_hole_four_anti_debug.py`  
**formal:** `SHQ_EDIT_HOLE_FOUR_ANTI_DEBUG_V1`

### 四態定義（鎖死）

| 字 | 定義 |
|----|------|
| 洞 | 剪影空位 M_hole，非矩形 |
| 除 | EDIT 無頭態 L1 |
| 扣 | Diff(有頭,無頭) 證洞 |
| 生 | 只在洞內刷 HD；鎖尺 |
| 反 | 每態成對反查 |

### 走錯精煉

W3 freeframe densify→頭變大 · W5 偷步 map · W9 DEBUG 不該全 BLOCK

### 質問政策

```text
run-diag          → WARN/SKIP 落盤，exit 0（不阻運行）
run-diag --strict → FAIL 可 exit 2（僅 CI / ACCEPT 前）
```

### CLI

```bash
python3 shq_edit_hole_four_anti_debug.py selftest
python3 shq_edit_hole_four_anti_debug.py glossary
python3 shq_edit_hole_four_anti_debug.py wrong-paths
python3 shq_edit_hole_four_anti_debug.py check-size --peep P --densify D
python3 shq_edit_hole_four_anti_debug.py scale-lock-map --peep P --densify D --out elev.png
python3 shq_edit_hole_four_anti_debug.py anti-diff --keep L0 --remove L1 --out $OUT
python3 shq_edit_hole_four_anti_debug.py run-diag --run $RUN
```

### 金句

> 洞是形，除是態，扣是證，生是填；反是鏡子。質問為燈，不為牆。
