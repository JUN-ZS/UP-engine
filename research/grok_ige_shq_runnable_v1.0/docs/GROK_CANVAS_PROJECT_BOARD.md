# IGE-SHQ — Grok Canvas 專案工作板

> Canvas 用作規格、工作分解、程式碼審閱與證據索引。命令要在 Grok Bot terminal 或真正啟用的 code execution 環境執行；Canvas 上的文字不是執行證據。

## 專案目標

把 IGE-SHQ「自身 18 部件 → 4× 幾何鎖定 → 材質／細節增強 → 鎖幾何回位」整理成可由 Grok AI 操作、由 Imagine 製作額外 donor、由 Python runtime 驗證的可追溯流程。

## 平台分工

| Surface | 工作 | 完成證據 |
|---|---|---|
| Grok Chat | 總控、問題拆解、審查 diff 和報告 | 對話回報 + 引用的檔案路徑 |
| Canvas | 保存本工作板、資料契約、變更提案和決策 | 本文件版本／修訂紀錄 |
| Imagine | 生成新的材質 donor 或參考圖 | 圖片檔 + SHA-256 + prompt + 生成日期 |
| Grok Bot terminal | 解壓、安裝套件、跑 preflight／registry／tests／方法 | 命令、exit code、stdout/stderr、輸出 SHA |

## 目前狀態

- [x] 原始工具包已打包到 `source/`，保留原始程式與素材。
- [x] 增加 Grok master prompt、Canvas 工作板、Imagine prompt、執行指南。
- [ ] Grok Bot terminal 確認可用。
- [ ] 當次 Preflight PASS（需新執行記錄）。
- [ ] Registry validation PASS（需新執行記錄）。
- [ ] S3 人工批准從硬編碼布林改成可驗簽的 approval artifact。
- [ ] Cache 改為 source/model/parameter/output SHA 的 content-addressed cache。
- [ ] Method receipt 從固定 PASS 改成 assertion-derived status。
- [ ] Recipe 改成 typed artifact DAG，每步驗 SHA 和契約。
- [ ] P08 單件 holdout 及人工檢查。
- [ ] 通過後才擴展至 18 parts。

## 執行紀錄表

| Run ID / UTC | Phase | Command | Exit | Input SHA | Output / Report | Status | What it proves / Does not prove |
|---|---|---|---:|---|---|---|---|
| — | — | — | — | — | — | NOT RUN | 不可預填 PASS |

## 方法層級（保持原始 ID）

| Group | Method IDs | Role |
|---|---|---|
| Cat 01 — S0 anti-hole/base | M01–M02 | Keep/Remove、hole/anti-hole、source freeze |
| Cat 02 — S1/S2 part read and geometry lock | M03–M07 | layered evidence、18-part decomposition、4× coordinate lock、2D proxy、identity alignment |
| Cat 03 — S3/S4 permission and routing | M08–M10 | human permission、topology gate、optional inpaint |
| Cat 04 — S4/S5 upgrade engines | M11–M20 | base/material/detail layers、donor transfer、contract guards |
| Cat 05 — S6/S7 return and audit | M21–M22 | tile/return planning、geometry guard and reverse QA |
| Recipes | R01–R03 | single-part, whole battlefield, ablation |

## 需要保留的狀態語義

- `PASS_COMMAND_EXIT_0`：命令正常退出；不等於輸出質量獲得接受。
- `PASS_CONTRACT_ONLY`：接口／契約檢查通過；不代表後端模型執行。
- `PASS_SYNTHETIC`：只在合成或模擬輸入上通過。
- `PASS_INDEPENDENT`：使用獨立 holdout、獨立目標或人工審核完成驗收。
- `BLOCKED`：前置條件不足，停止後續依賴步驟。
- `FAIL`：實際 assertion 或命令失敗。

## 不可越過的寫入閘門

1. 無有效 S3 approval artifact，不得新增或覆蓋任何 part/master。
2. source asset hash 或 model hash 改變，舊 cache 不可沿用。
3. Imagine donor 只作材質來源，不作輪廓、身份、座標或 alpha authority。
4. M19/M20 合約檢查，不得升格為 live Siax/NCNN/Flux inference。
5. 18 parts 全部通過之前，不可把全局 battlefield 報告標成 ACCEPTED。
