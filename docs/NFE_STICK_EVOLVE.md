# NFE STICK · 進化生成附卡

**碼：NFE-STICK** · 掛在每一輪 next-still I2I 之前。

## 作用

把狀態（F_t / F_{t-1} / K / ΔS / 禁令 / 驗收帶）**粘**到生成請求上，使進化生成可重試、可拒絕、可 provenance。

## 一鍵產 STICK

```bash
python tools/nfe_one_click.py --master F0.png --job-id nfe_x --out-dir runs/nfe/x
# → runs/nfe/x/STICK_EVOLVE.json
# → runs/nfe/x/STICK_NEXT.prompt.txt
```

## 進化循環

1. 讀 `STICK_EVOLVE.json` 的 `prompt` + `paths` + `accept_rules`
2. **I2I only** 產候選 F_{t+1}
3. `nfe_next_frame_pilot.py accept-candidate`（失敗不推進 t）
4. 成功後 `attach_stick` 再產下一張 STICK
5. 僅 accepted 進 C1–C5

## 禁止

- 用 I2V 代替 G
- 用光流 morph 冒充 next-frame
- 把 STICK 當品質 PASS
