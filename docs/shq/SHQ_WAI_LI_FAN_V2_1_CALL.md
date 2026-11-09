# 外力反 V2.1 · 10 秒卡

**STICK:** `STICK_WAI_LI_FAN_V2` + `STICK_WAI_LI_GROK`

```text
任意物件 part_id
外力GROK 除背 → CLIP
外力GROK 除件 → 洞 MARK
扣 θ 微調 · 生 on 洞 · 回 · 反
禁自 peep · 禁寫死頭先驗
換圖型 = 只改 TunePack / prompt
```

```bash
python3 shq_wai_li_fan_v2_any_object.py selftest
python3 shq_wai_li_fan_v2_any_object.py init-run --src L0.jpg --out RUN --part left_helmet
python3 shq_wai_li_fan_v2_any_object.py structure \
  --out RUN --l0 L0 --l-chu-part L1 --l-chu-bei Lnb --ihd IHD \
  --asset-chu-part ID --asset-chu-bei ID --asset-sheng ID \
  --tune tune.json
```
