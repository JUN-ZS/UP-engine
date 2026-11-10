# SHQ Agent Driver — 教其他 AI 如何層層調用 PY（write 01392）

**對齊:** [UP-engine PR #12](https://github.com/JUN-ZS/UP-engine/pull/12)  
**缺口閉合:** Registry 完整性 → Callable Dispatcher → Stage Receipt → Independent S7  
**仍未:** 真 Siax/Flux live adapter 進 production · `src/ige` 合併 · ACCEPT_FULL_HD

---

## 其他 AI 必讀順序

1. `docs/SHQ_AI_USAGE_GUIDE.md`（PR#12）— 思考契約  
2. `method_registry.json`（ige-method-registry/0.1）— 方法表  
3. 本檔 + `shq_agent_driver.py` — **執行控制層**  
4. 研究 fossils — 對照，不直接當 production 後端

## 一句

> AI 只提出狀態／候選；**Driver 決定 method_id、調用 entrypoint、寫 receipt、S7 驗收。**  
> AI **不得** 自授 `edit_permission`，也不得把 FAIL 改寫成 PASS。

## 命令

```bash
python3 shq_agent_driver.py selftest
python3 shq_agent_driver.py validate-registry
python3 shq_agent_driver.py resolve --method-id HOLE_SCALELOCK_HF_RESIDUAL
python3 shq_agent_driver.py run-full --src SRC.jpg --empty EMPTY.jpg --out $RUN
# optional densify map JSON: {"U0_LEFT":"path.jpg","U1_RIGHT":"path.jpg"}
python3 shq_agent_driver.py run-full --src SRC --empty EMPTY --out $RUN --densify-map map.json
```

## 執行閉環

```
AI 讀圖 → 狀態候選
   ↓
S0 freeze (SHA)
   ↓
S1 DIFF candidate masks（≠ permission）
   ↓
S2 corners_4 geometry lock
   ↓
S3 permission compiler（默認 false）
   ↓
S4 Registry resolve(method_id) + entrypoint
   ↓
S5 execute callable（HF / Imagine densify / stub backends）
   ↓
S6 Skill D guard hardpaste（洞外 diff=0）
   ↓
S7 independent reread + receipts audit
```

## 宣稱邊界

| claim | 何時 |
|-------|------|
| C0 | 僅對話 |
| C1 | DIFF / opencv HF |
| C2 | geometry lock peep |
| C3 | 真 Imagine densify adapter + size gate |
| C4 | S7 全定量 |
| C5 | Gold+CI — 唯一 ACCEPT_FULL_HD |

## Skill D 不變式

`SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD` 不是「可選四技能之一」 alone，  
而是 **PATH A/B/C 回位前必須通過的共同 guard**。

## 與 PR#12 分析對齊的修復

| 缺口 | 01392 |
|------|-------|
| method_registry.json 缺失 | ✅ 已提交 21 methods · validate PASS |
| Router 只決策不派工 | ✅ Driver 調用 entrypoint |
| 4-skill Lanczos 冒充 gen | ✅ claim 分級 · 禁 Lanczos as gen |
| 邊界 +2 造假 | ✅ 未使用該 fossil 路徑 |
| AI Guide 落後 | 見 PR#12 另更；本 Driver 獨立可跑 |

ACCEPT_FULL_HD=false · production_claim=false
