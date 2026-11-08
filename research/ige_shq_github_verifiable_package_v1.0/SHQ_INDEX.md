# SHQ_INDEX.md — 套件檔案與五層模組索引

| 路徑 | 角色與職責 |
| :--- | :--- |
| `SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md` | 其他 AI 的第一入口：1 → 8 逐步執行與逐關停機手冊 |
| `SHQ_AI_USAGE_GUIDE.md` | 理解規約、宣稱邊界與禁止事項 |
| `preflight_check.py` | Step 1 素材、SHA-256、尺寸與反冒充閘門（失敗回傳 `exit code 2`） |
| `requirements.txt` | Python 相依套件清單 |
| `assets/asset_manifest.json` | 全部 13 張圖像素材之權威 SHA-256、尺寸與角色清單 |
| `registry/method_registry.json` | `ige-method-registry/0.1`（22 個方法，1-to-1 對應程式、測試與驗收） |
| `registry/validate_registry.py` | Registry Schema 與成熟度標籤驗證器 |
| `src/ige_shq/l0_s0_four_way_anti_hole.py` | Layer 0：`S0` 生／除／扣／洞／反洞與 SHA 凍結 |
| `src/ige_shq/l1_s1_s2_part_hierarchy_and_geometry_lock.py` | Layer 1：`S1` 18 部件分割與 `S2` 遞迴座標鏈 $T_{\text{scene}\leftarrow\text{leaf}}$ |
| `src/ige_shq/l2_s3_s4_permission_and_registry_router.py` | Layer 2：`S3` 人工核實權限編譯與 `S4` 動態 Registry 路由 |
| `src/ige_shq/l3_s4_self_part_dense_registration_and_3freq_engine.py` | Layer 3：`Skill A/B/C` 逐部件光流配準與 $L_{\text{base}} + M_{\text{material}} + H_{\text{detail}}$ 拆層 |
| `src/ige_shq/l4_s5_s6_s7_rule01380_return_and_reverse_qa.py` | Layer 4：`Skill D`、`Rule 01380`、18 部件回位與 `S7` 磁碟重讀反扣驗收 |
| `tests/test_registry_schema.py` | Registry Schema 與 Preflight 完整性單元測試（5 項測試） |
| `run_all_verifications.py` | 頂層執行器：依序執行 Preflight → Registry → L0–L4 → 13 項 unittest → 產出報告 |
