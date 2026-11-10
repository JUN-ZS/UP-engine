# SHQ 技法憲 · 全專案脈絡（01388）

**formal:** `SHQ_TECHNIQUE_LINEAGE_FULL_PROJECT_V1`  
**範圍:** 整段對話／專案試錯，不只 posematch 末段  
**起點意象:** `/workspace/artifacts/imagine_images/64daf29a-53b6-47f6-bcd6-a1cd95c311eb.jpg` asset `64daf29a` + 中景人金案  
**終點:** 洞/除/扣/生 鎖尺（01385–01386）+ 合眾 MULTI 金案 B  

## AI 公式

- `formula/SHQ_AI_FORMULA_GRAPH.json` — 全圖（含 thumbs 索引）
- `formula/SHQ_AI_FORMULA_COMPACT.json` — agent 精簡

## 時代軸

| Epoch | 題 |
|-------|-----|
| E0 | 意象球 + 中景人回位 |
| E1 | DDXX + 雙機合眾 HD |
| E2 | 六機咬合失憶 → 公式鎖 |
| E3 | 嵌套部件樹 |
| E4 | Native / 全描 / 辨識 |
| E5 | Partmap 四角·邊整體 |
| E6 | 洞除扣生鎖尺 |

## 時間線

| # | epoch | phase | id | Q |
|---|-------|-------|-----|---|
| 00 | E0_ORIGIN | ORIGIN | `00_SPHERE_METAPHOR` | Q: 何謂層？物件能否獨立升清再回？ |
| 01 | E0_ORIGIN | ORIGIN | `01_MID_SCENE` | Q: 風景擴容 vs 人縮小？ |
| 02 | E0_ORIGIN | EXPLORE | `02_MID_PEEP_EMPTY` | Q: S=1/a 是否先於生成？ |
| 03 | E0_ORIGIN | LOCK | `03_MID_VM` | Q: 禁 Lanczos 冒充 HD？ |
| 04 | E1_DDXX | EXPLORE | `04_G2_WITH` | Q: 他機=風景 單機 SOLO？ |
| 05 | E1_DDXX | EXPLORE | `05_G2_EMPTY` | Q: 合眾底是否唯一 EMPTY×S*？ |
| 06 | E1_DDXX | FAIL | `06_G2_SEG_DEBUG` | Q: 全機邊界未滿能否 GENFIT？ |
| 07 | E1_DDXX | FIX | `07_G2_E40` | Q: peep 是否含腳／翼尖？ |
| 08 | E1_DDXX | LOCK | `08_G2_MULTI_HD` | Q: N×SOLO 後才 MULTI？ |
| 09 | E1_DDXX | LOCK | `09_G2_HEZHONG_FULL` | Q: slot_ratio 有報？ |
| 10 | E2_MULTI6 | FAIL | `10_G6_BOARD` | Q: 為何 1 機成、6 機敗？ |
| 11 | E2_MULTI6 | FAIL | `11_G6_VS_SOLO` | Q: 是否把成功前提換掉？ |
| 12 | E2_MULTI6 | ASK | `12_G6_FORMULA` | Q: composition ≠ fit method？ |
| 13 | E2_MULTI6 | EXPLORE | `13_G6_6MECHA` | Q: 11 點語意 vs 自動輪廓？ |
| 14 | E2_MULTI6 | FAIL | `14_G6_V16_LANDMARK` | Q: E-37 語意替換？E-38 跨閘？ |
| 15 | E3_NEST | EXPLORE | `15_PART_LAYER` | Q: 部件是結構樹還是 CUT？ |
| 16 | E3_NEST | EXPLORE | `16_EMPTY_MECHA` | Q: T_world←robot · T_robot←part？ |
| 17 | E4_NATIVE | EXPLORE | `17_RT_CALL` | Q: HARDFILL 是否誤當辨識？ |
| 18 | E4_NATIVE | EXPLORE | `18_FULLSCAN` | Q: 禁沿用舊 DONOR 底？ |
| 19 | E4_NATIVE | EXPLORE | `19_REASSY` | Q: 黑頭／缺覆蓋？ |
| 20 | E4_NATIVE | FAIL | `20_GRID_AXIS` | Q: 圖邊四角 vs 機體框？ |
| 21 | E5_PARTMAP | EXPLORE | `21_TEACH_PARTMAP` | Q: elev_remap 必須 false？ |
| 22 | E5_PARTMAP | FAIL | `22_TEACH_VS_GT` | Q: 互斥 IoU 閘？ |
| 23 | E5_PARTMAP | FIX | `23_EDGE_WHOLE` | Q: 碎邊能否 elev？ |
| 24 | E5_PARTMAP | LOCK | `24_MAT_PIPELINE` | Q: alpha XOR=0？ |
| 25 | E6_HOLE | EXPLORE | `25_SRC_MECHA` | Q: S0 BASE 凍結？ |
| 26 | E6_HOLE | FAIL | `26_OUTER_HOLLOW` | Q: peep 框能當洞？ |
| 27 | E6_HOLE | FAIL | `27_WORDS` | Q: 字詞鎖死？ |
| 28 | E6_HOLE | EXPLORE | `28_HOLE_CONCEPT` | Q: 洞回 vs 框回？ |
| 29 | E6_HOLE | EXPLORE | `29_EDIT_MULTI` | Q: 一生一除差分？ |
| 30 | E6_HOLE | FAIL | `30_SIZE_GROW` | Q: E-105 HEAD_SCALE_GROW？ |
| 31 | E6_HOLE | ASK | `31_MATRIX4` | Q0–Q9 燈不阻跑 |
| 32 | E6_HOLE | FIX | `32_PEEP_LOCK` | 尺度在 peep 不在 densify |
| 33 | E6_HOLE | LOCK | `33_BEST_RETURN` | ACCEPT_FULL_HD=false · 技法成立 |

## 核心公式（人讀摘要）

### DDXX
\( q = a(pR)+t \) · \( S^*=1/a \) · 逆景 \( v=q A_{\rm scene}+b_{\rm scene} \)

### 合眾
`N×SOLO → EMPTY×S* → HARDPASTE + slot_ratio` · CLI `--multi --hd`

### 階層
\( T_{W\leftarrow part}=T_{W\leftarrow robot}\cdot T_{robot\leftarrow part} \)

### 洞四態
洞=形 · 除=態 · 扣=證 · 生=填 · 反=鏡 · **鎖尺 peep 擁有尺度**

## 金句

> 起點不是第一張成功圖，是第一張敢試錯的圖。  
> 全專案質問貫穿；終案不是 freeframe 特写，是公式+鎖尺洞內生+合眾 CLI。

asof: 2026-11-07T16:52:35.393509+00:00  
ACCEPT_FULL_HD: false · missing_thumbs: 0
