# 01389 · 宣稱分級 + Method Registry v0.1

**上游契約:** [PR #12](https://github.com/JUN-ZS/UP-engine/pull/12) `docs/SHQ_AI_USAGE_GUIDE.md`

## 核心

| 檔 | 職 |
|----|-----|
| [SHQ_CLAIM_TAXONOMY_V1.md](./SHQ_CLAIM_TAXONOMY_V1.md) | 宣稱 C0–C5 定義 |
| [formula/SHQ_CLAIM_TAXONOMY.json](./formula/SHQ_CLAIM_TAXONOMY.json) | AI 精簡 |
| [formula/SHQ_METHOD_REGISTRY_V1.json](./formula/SHQ_METHOD_REGISTRY_V1.json) | method_id + implementation_status |
| [boards/](./boards/) | 教學圖 |

## 宣稱

`claim` = 對話/檔名/PASS 口號  
`fact` = 可重跑 SHA + Backend + S7  

對話 25/25、true_generative 檔名、8K 口號 → **C0** 直到獨立重現。

## Registry 狀態

本 JSON 為 **契約 v0.1**：結構可驗證、`edit_permission` 默認 false、test_ids 必填。  
**尚未** `src/ige` loader · `wired_to_src_ige=false` · `ACCEPT_FULL_HD=false`
