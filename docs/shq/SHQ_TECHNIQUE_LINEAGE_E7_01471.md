# SHQ 技法憲 · E7 完整對話與憲技整理（01471）

**formal:** `SHQ_TECHNIQUE_LINEAGE_E7_DIALOGUE_CONSTITUTION_V1`  
**範圍:** 01388 之後整段對話／專案試錯（write **01438–01470**）  
**起點:** 換涯人成功 SHA 鏈（01438）  
**終點:** 外力反 V2.1 任意物件 ACCEPT（01470 · C2_PASS）  
**母脈絡:** `SHQ_TECHNIQUE_LINEAGE_FULL_01388`（E0–E6）  
**Hub 圖策:** **SHA 圖改用縮圖**（`sha_thumbs/*` + `01_SHA_THUMBS_CONTACT.jpg`；禁 576KB 全幅 contact 上 Hub）

## 一句

> E7 = 把洞除扣生從「機甲抽象」落地成 **具名 STICK 技能**（換涯人／機炸回／新畫女／回車大炮／外力反／外力GROK），並用 **State Bus + TunePack** 證明：獨立 PASS ≠ 可組合。

## 時代軸（E7）

| Epoch | 題 | write |
|-------|----|-------|
| E7_HUAN | 換涯人 · SHA 金錨 | 01438–01439 |
| E7_JIZHA | 機炸回 · PARTMAP 四角 MAT | 01440–01441 |
| E7_XHN | 新畫女 · a8b 面正典 | 01442–01443 |
| E7_HCD | 回車大炮 · 三主體 S2 | 01444–01447 |
| E7_FOUR | 四態反架構 · 頭咬／MARK／真洞 | 01448–01453 |
| E7_WLF | 外力反 V1→V3 · 新畫女V2 | 01454–01464 |
| E7_WLF21 | 外力GROK · V2.1 any object ACCEPT | 01465–01470 |

## 完整對話時間線（質問保留）

| # | epoch | phase | id | Q |
|---|-------|-------|-----|---|
| 00 | E7_HUAN | LOCK | `00_HYR_BOARD5` | Q: 崖台換人是否可鎖成金錨？ |
| 01 | E7_HUAN | LOCK | `01_HYR_FINAL` | Q: outside=0 是否=視覺成功？ |
| 02 | E7_HUAN | LOCK | `02_HYR_CLEAN` | Q: sole annotate 可否脫離像素？ |
| 03 | E7_HUAN | ORIGIN | `03_HYR_SRC` | Q: 頭必須在？洞不吃岩？ |
| 04 | E7_HUAN | EXPLORE | `04_HYR_HD_CUT` | Q: elev 是否 freeframe？ |
| 05 | E7_HUAN | EXPLORE | `05_HYR_TRIPTYCH` | Q: IC 光影是後綴還是主鏈？ |
| 06 | E7_JIZHA | ORIGIN | `06_JZH_SRC_YARD` | Q: 爆炸是教學還是 freeframe？ |
| 07 | E7_JIZHA | EXPLORE | `07_JZH_EXPLODE` | Q: 框=圖邊？elev_remap=false？ |
| 08 | E7_JIZHA | LOCK | `08_JZH_MATLOCK` | Q: α XOR 必須 0？ |
| 09 | E7_JIZHA | LOCK | `09_JZH_GUIDED` | Q: 機炸回 ≠ 換涯人？ |
| 10 | E7_XHN | ORIGIN | `10_XHN_A8B` | Q: 裸 a8b 直 ECC 合法？ |
| 11 | E7_HCD | ORIGIN | `11_HCD_L0` | Q: 18 相對件 + S2 樹？ |
| 12 | E7_HCD | EXPLORE | `12_HCD_S2` | Q: 三主體 ≠ 單機 PARTMAP？ |
| 13 | E7_HCD | EXPLORE | `13_HCD_PART` | Q: 禁色帶亂件？ |
| 14 | E7_HCD | LOCK | `14_HCD_RETURN` | Q: peep=件級 elev？ |
| 15 | E7_HCD | EXPLORE | `15_HCD_TANK` | Q: D2 無 peep SOLO 禁 SUCCESS？ |
| 16 | E7_XNV2 | LOCK | `16_XNV2_L0` | Q: PATH1E plate 只在洞內生？ |
| 17 | E7_XNV2 | EXPLORE | `17_XNV2_CHU` | Q: CLIP 從除背來？禁自 peep？ |
| 18 | E7_XNV2 | EXPLORE | `18_XNV2_CLIP` | Q: 無洞回=錯位教材？ |
| 19 | E7_XNV2 | LOCK | `19_XNV2_R` | Q: V1 stick 保留、返還改臉默認 V2？ |
| 20 | E7_XNV2 | ASK | `20_XNV2_STORY` | Q: (N)(X) 層層反？ |
| 21 | E7_WLF21 | LOCK | `21_WLF21_STORY` | Q: 任意物件 TunePack 可換？ |
| 22 | E7_WLF21 | LOCK | `22_WLF21_COMPARE` | Q: 獨立 PASS ≠ 可組合？ |
| 23 | E7_WLF21 | EXPLORE | `23_WLF21_SRC` | Q: part_role any object？ |
| 24 | E7_WLF21 | EXPLORE | `24_WLF21_CLIP` | Q: CLIP_from_chu_bei 必須 true？ |
| 25 | E7_WLF21 | EXPLORE | `25_WLF21_HOLE` | Q: true_hole=除後像素不在？ |
| 26 | E7_WLF21 | LOCK | `26_WLF21_RETURN` | Q: elev_remap=false · outside_max=0？ |
| 27 | E7_WLF21 | FIX | `27_WLF21_ANTI` | Q: 反板省略=E-FA-06？ |

## 憲技地圖（可調用）

| STICK / formal | 憲 | CALL | 金錨 write |
|----------------|----|------|-----------|
| `STICK_HUAN_YA_REN` / `HUAN_YA_REN_LOCK_PASTE` | `SHQ_HUAN_YA_REN.md` | `CALL_HUAN_YA_REN.md` | 01439 · board `9043229b` |
| `STICK_JI_ZHA_HUI` / `JI_ZHA_HUI_EXPLODE_RETURN` | `SHQ_JI_ZHA_HUI.md` | `CALL_JI_ZHA_HUI.md` | 01441 · scrapyard 6 圖 |
| `STICK_XIN_HUA_NV` / `XIN_HUA_NV_FACE_STACK` | `SHQ_XIN_HUA_NV.md` | `CALL_XIN_HUA_NV.md` | 01443 · a8b + poster |
| `STICK_HUI_CHE_DA_PAO` / `HUI_CHE_DA_PAO_3SUBJ_RETURN` | `SHQ_HUI_CHE_DA_PAO.md` | `CALL_HUI_CHE_DA_PAO.md` | 01445 · `cb078e94` 族 |
| `STICK_FOUR_ANTI_ARCH` | `SHQ_FOUR_ANTI_ALGEBRA_ARCH.md` | — | 01448 |
| `STICK_WAI_LI_GROK` | `SHQ_WAI_LI_GROK.md` | `SHQ_WAI_LI_GROK_CALL.md` | 01466 |
| `STICK_XIN_NV_V2` | `SHQ_XIN_NV_V2.md` | `SHQ_XIN_NV_V2_CALL.md` | 01464 |
| `STICK_WAI_LI_FAN_V2` / `WAI_LI_FAN_V2_1_ANYOBJ_TUNE_V1` | `SHQ_WAI_LI_FAN_V2_1.md` · `SHQ_WAI_LI_FAN_V2_1_ANY_OBJECT.md` | `SHQ_WAI_LI_FAN_V2_1_CALL.md` | 01469–01470 |

## 核心公式（人讀摘要）

### 換涯人
`SRC → PEEP → HD_ELEV → EMPTY → LOCK_PASTE (+ IC 光影 + sole)`  
頭必須在；洞不吃岩；outside=0 ≠ 視覺成功；ACCEPT_FULL_HD=false。

### 機炸回
`SRC → PARTMAP 教學 → EXPLODE → TUIDI 四角 → MAT structure-lock → 4corner hardpaste MATLOCK → guided FULL_MAT`  
框=圖邊；elev_remap=false；α XOR=0；爆炸是教學不是 freeframe。

### 新畫女
`a8b → ST1 IP → ST2 全幅鎖臉 → PATH1E plate→ECC → ET/GEO`  
≠ 換涯人 peep；≠ 裸 a8b 直 ECC。

### 回車大炮
`L1_GENERIC_3SUBJ (18) + S2_GENERIC_RELATIVE T樹 + EMPTY×MULTI_RETURN`  
大炮 peep=件級 elev；禁色帶亂件；D2 無 peep SOLO 不得 SUCCESS。

### 四態反
\[
[(生,除,洞,扣)\times(反)] + \text{State Bus 不變量 1–6}
\]
獨立成功量的是局部閘；連動需要共享 State Bus。

### 外力反 V2.1（任意物件）
```text
外力GROK·除背(X) → 扣 → M_subj = CLIP MASK
外力GROK·除件(X) → 扣 → 洞 · MARK
CLIP = L0 ⊙ M_subj     ← 禁自 peep
生只在洞內 · elev_remap=false · outside_max=0
TunePack 外置 θ · part_role ∈ {head,mecha_part,full_subject,…}
```

## 對話主線（整理後）

1. **01438** 用戶成功鏈 SHA 對齊 → 證明 換涯人五步不是故事，是可哈希產物。  
2. **01439–01445** 具名 STICK 分家：人崖／機爆／臉正典／三主體戰場，互不冒充。  
3. **01448** 質問「為何各自 PASS、組起來就錯」→ 四態反架構 + State Bus。  
4. **01454–01459** 外力反把「除／生」從本地 peep 拉到 Imagine 外力。  
5. **01462–01464** 新畫女 V2 = a8b × 洞座 × (N)(X) 層層反。  
6. **01466–01470** 外力GROK + V2.1：任意物件、CLIP 只從除背、TunePack；雙機甲 C2_PASS。

## SHA 圖策（本批硬改）

| 舊 | 新 |
|----|----|
| `SHA_TRACE_CONTACT.jpg` 全幅 ~576KB | `sha_thumbs/*.jpg` ≤200px 邊 |
| Hub 推全圖 | Hub 只推縮圖 + `01_SHA_THUMBS_CONTACT.jpg` |
| file/pixel SHA 仍記於 JSON | `SHA_TABLE_*.json` + `MANIFEST.sha_table` |

## 產物

- `00_E7_LINEAGE_CONTACT.jpg` — 技法對話 contact（縮圖拼）  
- `01_SHA_THUMBS_CONTACT.jpg` — SHA 金錨 contact（**縮圖**）  
- `thumbs/` · `sha_thumbs/`  
- `formula/SHQ_E7_LINEAGE_COMPACT.json`  
- `docs/*` 憲 / CALL / GOLD_SHA / LOCK / PY  

## 宣稱級

- 01470：`C2_WLF_V21_L0` · **ACCEPT_FULL_HD=false** · not production FULL_HD  
- 全 pack：技法成立／可調用；**非 C5**

## 金句

> 獨立 PASS ≠ 可組合。  
> CLIP 從除背來，不從自 peep 來。  
> SHA 圖上 Hub 用縮圖；全幅留在本地 artifacts。

asof: 2026-11-09  
ACCEPT_FULL_HD: false
