# SHQ · 偷步 · 跑偏 · 出錯審查力（01473）

**formal:** `SHQ_STEAL_DRIFT_AUDIT_FORCE_V1`  
**write_id:** `01473`  
**zh:** 偷步／跑偏／出錯審查力  
**STICK:** `STICK_AUDIT_FORCE`  
**母:** 01389 Claim 分級 · 01448 四態反 · 01466 外力GROK · 01469 外力反 V2.1 · 01472 Harness KILL  
**PY:** `shq_audit_force.py`  
**ACCEPT_FULL_HD:** false

---

## 0. 一句

> **偷步** = 跳過必經主權步仍報成功。  
> **跑偏** = 宣稱的 STICK／路徑與實際執行不是同一條。  
> **出錯審查力** = 系統**必須能**抓出偷步與跑偏，並把錯誤升成可引用 E 碼；抓不到 = 審查力不足 = 不得升 claim。

三者必須**寫進文憲與收據**，不能只靠對話提醒。

---

## 1. 定義（硬）

### 1.1 偷步 `STEAL_STEP`

**定義：** 在已鎖定的連招／不變量中，**省略或用弱代理替換**必經步驟，卻仍輸出 `PASS`／`SUCCESS`／高 claim。

| 必經類 | 合法 | 偷步例 |
|--------|------|--------|
| 外力除／生 | Imagine asset_id | OpenCV inpaint／Telea 當 REMOVE |
| CLIP | 外力除背 → kou | bbox 自 peep 當 CLIP |
| 洞 | 凍結 \(M_{hole}\) 或 kou 真洞 | 方法自擴 union 再測 outside |
| 回 | hardpaste 洞內 · 洞外 0 | freeframe 全圖重生當回 |
| 反 | 正／對板或 ERROR_TEXTBOOK | 只出漂亮 RETURN |
| 多層 MARK | 反扣經 MARK | 子層 freeframe 貼回 |

**公式：**

\[
\mathrm{Steal}
\iff
\exists\, s\in S_{\mathrm{required}}:\ 
\mathrm{executed}(s)=\bot
\ \wedge\
\mathrm{claim}\ge \mathrm{PASS}
\]

### 1.2 跑偏 `DRIFT`

**定義：** 收據上的 `STICK`／`formal`／`path_id`／`method_id` 與**實際跑的代碼路徑、輸入契約、金錨**不一致。

| 維度 | 跑偏例 |
|------|--------|
| STICK | 標 `STICK_WAI_LI_FAN_V2` 實際只跑換涯人 peep 硬貼 |
| empty_mode | 標 `true_remove` 實際 `proxy_telea` |
| claim_level | 標 C4 實際 C1 fossil |
| method | 名 R14_NEURAL 實際 dens_u 無網 |
| gold | 引用 9043229b 實際用了另一張 SRC |
| 層 | A 通就報 B／C 通 |

**公式：**

\[
\mathrm{Drift}
\iff
\mathrm{declared}(T) \neq \mathrm{observed}(T)
\quad T\in\{\mathrm{STICK},\mathrm{path},\mathrm{empty},\mathrm{claim},\mathrm{method},\mathrm{gold}\}
\]

### 1.3 出錯審查力 `AUDIT_FORCE`

**定義：** 對一次 run／報告，系統能否在**不依賴作者自述**下，自動或半自動判定：

1. 有無偷步（缺步表）  
2. 有無跑偏（宣稱 vs 觀測）  
3. 錯誤能否**編碼**（E-*）且 **擋住 claim 升級**

\[
\mathrm{AuditForce}\ge \mathrm{AF2}
\iff
\mathrm{detect}(\mathrm{Steal}\lor\mathrm{Drift})
\ \wedge\
\mathrm{emit}(E\text{-code})
\ \wedge\
\mathrm{block}(\mathrm{claim}>\mathrm{allowed})
\]

| AF 級 | 能力 | 可否支持 SUCCESS 候選 |
|-------|------|----------------------|
| **AF0** | 無檢查；人看圖 | 否 |
| **AF1** | 只查 outside／NCC 數字 | 否（01433 假綠） |
| **AF2** | 缺步表 + 凍結洞 + empty_mode 誠實標 + E 碼 | C2 上限 |
| **AF3** | + asset_id 外力鏈齊 + STICK 綁定核 | C3–C4 候選 |
| **AF4** | + 金 replay + Registry 載入 + CI | C5 唯一門 |

**規則：** `ACCEPT_FULL_HD=true` 或 C5 **要求 AF4**。缺省 run 至少 **AF2**，否則 claim 強制 ≤ C1。

---

## 2. 落憲位置（寫進哪）

| 文憲位 | 寫什麼 |
|--------|--------|
| **本檔 01473** | 總定義 · 三詞 · AF 級 · 總檢查單 |
| **01389 Claim** | 偷步／跑偏 → 自動降 claim；E-CLAIM 聯動 |
| **01466 外力GROK** | 缺 Imagine 除生 = 偷步 E-WLG-* |
| **01469 V2.1** | 自 peep CLIP = 偷步；無 Tune 卻 any-object = 跑偏 |
| **01448 四態** | 獨立 PASS 當組合 = 跑偏／假組合 |
| **01472 Harness** | proxy empty 必須標；禁 RANK；AF 自檢 |
| **每技 CALL** | 文末加「偷步紅線」3 條 |
| **每份 REPORT** | 必填 `steal_flags[]` `drift_flags[]` `audit_force` `E_codes[]` |

---

## 3. 總檢查單（每次 run 必跑）

### 3.1 偷步檢查 `CHECK_STEAL`

| # | 問 | 否 → |
|---|-----|------|
| S1 | 宣稱含「外力／REMOVE／CLIP」時，有無對應 Imagine asset_id？ | E-WLG-01/02 · STEAL |
| S2 | CLIP 是否來自除背 kou 而非 bbox？ | E-WLG-02 · STEAL |
| S3 | outside 是否對**凍結** \(M_{hole}\) 算？ | E-GEO-PERM · STEAL |
| S4 | 多 peep 是否互斥（或有顯式融合）？ | E-COMPOSE-01 · STEAL（假組合） |
| S5 | 標 FULL_HD／C5 時有無金 replay＋CI？ | E-CLAIM-01 · STEAL |
| S6 | ERROR_TEXTBOOK／反板是否要求時存在？ | E-FA-06 · STEAL |

### 3.2 跑偏檢查 `CHECK_DRIFT`

| # | 問 | 否 → |
|---|-----|------|
| D1 | `STICK` 字段 = 實際 skill 路徑？ | E-DRIFT-01 |
| D2 | `empty_mode` 與實做一致（proxy 不可寫 true）？ | E-DRIFT-02 |
| D3 | `method_id` 名 = 實做 family（無假 NEURAL）？ | E-DRIFT-03 |
| D4 | `claim_level` ≤ AF 允許上限？ | E-DRIFT-04 |
| D5 | 金 SHA／asset 與 ingest 源一致？ | E-DRIFT-05 |
| D6 | 層 A/B/C 有無互替宣稱？ | E-DRIFT-06 |

### 3.3 審查力自檢 `CHECK_AF`

| # | 問 | 否 → |
|---|-----|------|
| A1 | 報告含 `audit_force` 字段？ | AF0 · 強制降 C0 |
| A2 | 偷步／跑偏檢查有執行記錄？ | AF≤1 |
| A3 | 任一 STEAL/DRIFT → status 不得為 SUCCESS | 硬閘 |
| A4 | E 碼可機讀（JSON 數組）？ | 審查力不足 |
| A5 | 磁碟 re-read 與記憶體 PASS 一致？ | E-AUDIT-DISK |

---

## 4. E 碼總表（本 write 新增 + 聯動）

### 4.1 新增 `E-AUDIT-*` / `E-DRIFT-*` / `E-STEAL-*`

| 碼 | 名 | 義 |
|----|-----|-----|
| **E-STEAL-01** | SKIP_REQUIRED_STEP | 缺必經步仍 PASS |
| **E-STEAL-02** | PROXY_AS_TRUE | proxy Telea／GrabCut 當真 REMOVE |
| **E-STEAL-03** | SELF_MASK_PASS | 方法自改 mask 再測 outside |
| **E-STEAL-04** | RANK_WITHOUT_CONTROL | 01433 式混淆排名 |
| **E-DRIFT-01** | STICK_MISLABEL | STICK 標籤 ≠ 路徑 |
| **E-DRIFT-02** | EMPTY_MODE_LIE | empty_mode 標籤說謊 |
| **E-DRIFT-03** | METHOD_NAME_LIE | 方法名 ≠ 實做 |
| **E-DRIFT-04** | CLAIM_OVER_AF | claim 高於 AF 允許 |
| **E-DRIFT-05** | GOLD_MISMATCH | 金錨不一致 |
| **E-DRIFT-06** | LAYER_SUBSTITUTE | A/B/C 互替 |
| **E-AUDIT-00** | NO_AUDIT_FIELD | 無 audit 字段 |
| **E-AUDIT-01** | AF_TOO_LOW | AF 低於宣稱所需 |
| **E-AUDIT-02** | NO_E_CODES | 失敗無 E 碼 |
| **E-AUDIT-03** | DISK_MEM_MISMATCH | 記憶體 PASS ≠ 磁碟 |
| **E-AUDIT-04** | REVIEWER_BLIND | 無法在無作者解釋下複核 |

### 4.2 聯動（已有，必須一起掃）

| 族 | 來源 | 管 |
|----|------|-----|
| E-WLG-* | 01466 | 外力偷步 |
| E-WLF* / E-WLF21-* | 01456/01469 | 連招偷步／自 peep |
| E-FA-* | 01448 | 四態／假組合 |
| E-CLAIM-* | 01389 | 宣稱偷換 |
| E-XHN2-* | 01464 | 新女畫V2 洞座 |

---

## 5. 與 claim 分級聯動（01389 補釘）

| 想報 | 最低 AF | 偷步/跑偏 |
|------|---------|-----------|
| C0 對話 | AF0 | 仍應標 flags（教育） |
| C1 fossil | AF1 | proxy 允許但必標 |
| C2 external | **AF2** | 任一 STEAL → 禁 |
| C3 backend | **AF3** | 外力 asset 鏈齊 |
| C4 S7 | AF3+ | 獨立重存 |
| C5 gold | **AF4** | 零 STEAL 零 DRIFT |

**降級規則（自動）：**

```text
if STEAL: claim_level = min(claim_level, C0) 且 status ≠ SUCCESS
if DRIFT: claim_level = min(claim_level, C1)
if AF < required(claim): claim_level = max_allowed(AF)
```

---

## 6. REPORT 必填 schema（落實到每份 JSON）

```json
{
  "write_id": "...",
  "STICK": "STICK_...",
  "claim_level": "C2",
  "audit_force": "AF2",
  "empty_mode": "proxy_grabcut_telea | true_diff_chu_tou | imagine_remove | ...",
  "steal_flags": [],
  "drift_flags": [],
  "E_codes": [],
  "required_steps": ["chu_bei", "chu_part", "gen", "hardpaste"],
  "executed_steps": ["hardpaste"],
  "outside_basis": "frozen_M_hole",
  "ACCEPT_FULL_HD": false
}
```

缺 `audit_force` → **E-AUDIT-00** → 視作 AF0。

---

## 7. 審查力如何「有牙齒」（執行）

1. **寫入前：** CALL 文末紅線（每技 3 條偷步）  
2. **跑中：** harness／WLF py 產 `steal_flags`（程式）  
3. **跑後：** `shq_audit_force.py audit --report REPORT.json`  
4. **升憲前：** AF 與 claim 矩陣門；否則 LOCK 拒收  
5. **Hub：** 無 AF 字段的 SUCCESS 報告不得合 main 當 production

---

## 8. 對 01433／01472 的示範定性

| 案 | 偷步 | 跑偏 | AF |
|----|------|------|-----|
| 01433 RANK | 假方法獨立、自擴 mask、Telea 當 EMPTY | 22 名≠22 實做；unique-src 當公平 | AF1 假綠 → **KILL** |
| 01472 synth | 無（結構自檢） | 無（標 synth） | AF2 結構 |
| 01472 gold hyr/jzh | **S2 級：** proxy empty（已標） | 若標 true_remove 才算 DRIFT | AF2（誠實 proxy） |
| 01472 gold xnv2 | 除头 true_diff；除背鏈視情況 | STICK 標 XIN_NV_V2 需 cohere | AF2–AF3 視 asset |

**誠實標 proxy ≠ 偷步；把 proxy 寫成 true = 偷步+跑偏。**

---

## 9. 一句鎖

> 不查偷步的 PASS 是假綠；  
> 不標跑偏的 STICK 是假名；  
> 沒有審查力的文憲是牆上標語。

asof: 2026-11-10  
ACCEPT_FULL_HD: false
