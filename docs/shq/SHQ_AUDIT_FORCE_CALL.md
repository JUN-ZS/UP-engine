# CALL · 偷步／跑偏／審查力 · 10 秒

```bash
python3 shq_audit_force.py audit --report path/to/REPORT.json
python3 shq_audit_force.py audit --summary path/to/SUMMARY.json
python3 shq_audit_force.py matrix   # claim × AF
python3 shq_audit_force.py selftest
```

**紅線**
- 無 `audit_force` → AF0 → claim≤C0
- STEAL → 禁 SUCCESS
- proxy empty 可跑，但 `empty_mode` 必含 proxy；寫 true = E-DRIFT-02 + E-STEAL-02
- C5 要 AF4

**三詞**
- 偷步 = 缺必經仍 PASS
- 跑偏 = 宣稱 ≠ 實跑
- 審查力 = 能抓 + 能編碼 + 能擋 claim
