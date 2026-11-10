# SHQ 「宣稱」分級憲（write 01389）

**formal:** `SHQ_CLAIM_TAXONOMY_V1`  
**上游:** UP-engine [PR #12](https://github.com/JUN-ZS/UP-engine/pull/12) · `docs/SHQ_AI_USAGE_GUIDE.md`  
**兄弟:** PR #15 技法脈絡 · PR #5 READ · PR #11 Tile  
**asof:** 2026-11-07T19:07:23.492518+00:00

---

## 一句

> **宣稱（claim）** = 對話／檔名／PASS 數字／「真 8K／真生成」口號  
> **工程事實（engineering fact）** = 可獨立重跑的 SHA · Backend ID · Seed · S7 audit · 原尺寸像素證據  

二者**不得互換**。Gemini／任何 AI 對話裡的 `21/21`、`25/25`、`8K` **默認為宣稱**，直到 S7 獨立重現。

---

## 分級（由弱到強）

| 級 | 代碼 | 是什麼 | 可否寫 ACCEPT_FULL_HD |
|----|------|--------|------------------------|
| **C0** | `DIALOGUE_CLAIM` | 對話／PR 正文宣稱 PASS、8K、已接通 | **否** |
| **C1** | `FOSSIL_SIM` | research Python 模擬／Lanczos+HF residual／同 mask 自比 | **否** |
| **C2** | `EXTERNAL_DONOR_XFER` | 外部 AI 圖檔多頻帶轉移（無本輪 backend log） | **否**（可 DIAG） |
| **C3** | `BACKEND_ADAPTER_LOG` | 有真實 Siax/Flux/Imagine adapter log + seed/params/SHA | 部分 stage 可 PASS |
| **C4** | `S7_INDEPENDENT` | 獨立重存輸出 + 洞外 max_rgb_diff=0 + ghost/flip/coverage + method_id | 候選 |
| **C5** | `GOLD_REPLAY` | Golden fixture 可重現 + Method Registry 載入 + CI | **唯一**可升憲 SUCCESS |

**規則：** 報告必須寫 `claim_level`；缺省 = C0。

---

## 禁止的「宣稱偷換」（E-CLAIM-*）

| 碼 | 名 | 例 |
|----|-----|-----|
| E-CLAIM-01 | PASS_NUMBER_AS_FACT | 對話 25/25 寫進 production ACCEPT |
| E-CLAIM-02 | FILENAME_AS_BACKEND | `true_generative_*.py` 檔名冒充 Diffusion |
| E-CLAIM-03 | SAME_MASK_SELF_PROOF | m_hole 同時作 src/dst → IoU=1 假 PASS |
| E-CLAIM-04 | LANCZOS_AS_GEN | INTER_LANCZOS4+Gaussian residual 當 gen-level |
| E-CLAIM-05 | DONOR_SIZE_AS_8K | 896×1200／1376×768 稱 8K |
| E-CLAIM-06 | DETAIL_GAIN_AS_QUALITY | Sobel gain 因銳化上升當新細節 |
| E-CLAIM-07 | REGISTRY_DOC_ONLY | 文件要求查 Registry 但程式 if/else 硬編碼 |
| E-CLAIM-08 | AI_SELF_GRANT_PERM | DIFF 漂亮洞 → 自動 edit_permission=true |

---

## 三路徑（不得互相冒充）

| path_id | 名稱 | 真後端 | 冒充禁 |
|---------|------|--------|--------|
| PATH_A_SIAX | Neural SR | Siax/NCNN 4× | Lanczos residual |
| PATH_B_HR_TILE_DIFFUSION | HR Tile Diffusion | Flux/Imagine tile i2i + VAE | Donor 轉移當本輪 diffusion |
| PATH_C_DONOR_MULTIBAND | AI Donor Multiband | 外部 donor 檔 + 對位轉移 | 稱「真 8K tile gen」 |

共享：Geometry Lock · Permission · S7。  
各有：method_id · Backend ID · failure_codes · claim_level 上限。

---

## 四態位置（修正）

**洞／除／扣／生／反** = Method Registry 可選 skill，**不是**每圖必經流水線。  
`DIFF ≠ edit_permission`。

---

## 閱讀次序（AI）

1. SHQ_INDEX  
2. SHQ_OBJECT_GEOMETRY_LOCK_PROGRAM_GUIDANCE  
3. **SHQ_AI_USAGE_GUIDE**  
4. 本檔 CLAIM_TAXONOMY  
5. SHQ_METHOD_REGISTRY_V1.json  
6. PR #15 技法記憶  
7. research fossils（只對照，不當 production）

## 參數分離

\[
\mathrm{model\_scale} \ne \mathrm{object\_transform} \ne \mathrm{tile\_size} \ne \mathrm{tile\_context}
\]

asof: 2026-11-07T19:07:23.492518+00:00  
ACCEPT_FULL_HD: false
