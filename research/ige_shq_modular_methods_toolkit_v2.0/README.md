# IGE-SHQ Layered Self-Part High-Resolution Upgrade & Verification Package (`v1.0`)

本套件已對齊 `UP-engine` PR #12 (`feat/shq-geometry-lock-program-guidance-v0.1`) 之 **Other-AI Step-by-Step Runbook** 標準，補齊全部 **13 張圖像素材**（含 `B0_GL` 與 `B2_GL` 兩張 `1200×896` 幾何鎖定母本）、`assets/asset_manifest.json`、`preflight_check.py`、`requirements.txt` 及三份導引文件（`SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`、`SHQ_AI_USAGE_GUIDE.md`、`SHQ_INDEX.md`）。

## 快速執行（其他 AI 請先讀 `SHQ_OTHER_AI_STEP_BY_STEP_RUNBOOK.md`）

```bash
python3 -m pip install -r requirements.txt
python3 preflight_check.py
python3 registry/validate_registry.py registry/method_registry.json
python3 -m unittest discover -s tests -v
python3 run_all_verifications.py --strict
```
