# 機炸回 · 10 秒調用卡（01441）

**formal:** SHQ_JI_ZHA_HUI_V1  
**STICK:** STICK_JI_ZHA_HUI → STICK_PARTMAP_4CORNER_MAT_GUIDED

## 何時用
機甲／可分件剛體：爆炸教學 → 升材 → 四角硬貼／引導回原景。

## 不做
- 機甲 AABB 當 frame
- elev_remap
- 爆炸當 freeframe 構圖
- 與「換涯人」人崖 peep 混用

## 六步
1 MAT structure-lock 8 parts  
2 EXPLODE MAT densify  
3 4corner hardpaste MATLOCK  
4 guided pose × FULL_MAT  
5 guided align MATLOCK  
6 structure fix hole（可選）

## 金案
`references/JI_ZHA_HUI_GOLD_SHA.json`
