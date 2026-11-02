# 單白殺升 · DBSS · 單白殺升

> Constitution skill `DAN_BAI_SHA_SHENG_DBSS_01261` · asof 2026-11-02T16:23:55Z

## 流程

```
A 母圖
  │
  ├─ S1 抽 NON-HD 全臉／ROI peep
  ├─ S2 WNK 殺白（非高清）          ★ 本技核心
  ├─ S3 PATH1E dens（NCNN×4 等）
  ├─ S4 findTransformECC 對位
  ├─ S5 feather 硬貼回母圖（WH 鎖死）
  └─ S6 回扣升清
        ├─ Lanczos ×2 / ×4
        └─ Imagine light（鎖構圖）
```

## 偽代碼

```python
face = mother[y0:y1, x0:x1]                 # NON-HD
face_wnk, mask, st = wnk(face)              # 非高清殺白
dens = ncnn_x4_tiled(face_wnk)              # PATH1E dens；不再 WNK dens
aligned, ecc = findTransformECC(face_wnk, dens)
assert mother.shape 不變
out = feather_paste(mother, aligned, box)
L4 = cv2.resize(out, (W*4, H*4), interpolation=cv2.INTER_LANCZOS4)
# Imagine light: image_to_image(out) 鎖構圖微銳化
```

## 驗收

| 項 | 要求 |
|----|------|
| hd_face_wnk | false |
| pixel_drop | false |
| paste_fail | false（全臉+寫出） |
| quality_qualified | 預設 false |
| Lanczos / Imagine | 收據分開，不冒充 NCNN PASS |

## 參考 run

- `tmp/amrs_nonhd_wnk_path1e`（殺白+PATH1E）
- `tmp/amrs_daf1_light_up`（Lanczos+Imagine light）
- 母圖預覽 asset：`daf1e8ea-66b8-401c-b4e4-161b01a94415`

## DO_NOT_REPEAT

見 constitution：`DAN_BAI_SHA_SHENG_DBSS_DO_NOT_REPEAT.md`
