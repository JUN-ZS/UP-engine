# 新女畫 V2 · 10 秒卡（01464）

**STICK:** `STICK_XIN_NV_V2`  
**身份:** a8b78fe5-2654-4f6f-84e3-c1dfbee61004  
**formal:** `SHQ_XIN_NV_V2_WLF3_TRUE_FOUR_ANTI`

## 何時用
中景／全幅要 **同一張 a8b 臉** 且必須 **經洞返還**（含多層升清再回）。

## 主鏈
```text
a8b + L0
→ 外力除背 → 扣 M_subj → CLIP     【禁自 peep】
→ 外力除頭 → 扣 M_head → 同框洞
→ face@CLIP native RATIO（letterbox elev）
→ PATH1E plate(姿@CLIP臉, a8b)
→ 生只在洞 → hardpaste
→ 反 + ERROR（無洞｜自peep｜RATIO硬方）
→ (N>1 則對 X 層重複)
```

## 不做
- 裸 a8b 直 ECC 全圖
- 無洞 freeframe 嵌臉
- 自 peep bbox 當 CLIP／洞
- face 硬拉 1:1
- 跳層不凍 MARK
