# DEBUG 01392 — HUB 回位出錯根因與修復

## 現象（PR #19 / RUN_NEW_01392）
- S7 報告 `outside_max_absdiff=0` · `leak=0` · **PASS_DIAG_CHAIN**
- 但 SRC↔RETURN **NCC≈0.79** · **33%+ 像素改變** · 視覺明顯錯位／地板被改

## 根因（三連）

| # | 錯誤 | 證據 |
|---|------|------|
| 1 | **Empty 是 freeframe 空庫**，不是同機位「除主體」 | SRC–Empty NCC≈**0.47**（應 ≥0.85） |
| 2 | **DIFF 大遮罩** 把地板／半幅當主體 | union coverage **36.6%** · bbox 幾乎半幅 |
| 3 | **`scale_lock_map` 用 phaseCorrelate 扭曲 peep** 後再 hardpaste | elev 與 peep 姿態漂移 · 回位「看起來歪」 |
| 4 | **S7 假 PASS**：只查「mask 外 max_diff=0」 | 胖 mask 外幾乎無像素 → 永遠 0 |

Hub 文件宣稱 PASS，**未測** empty freeframe / NCC / phase / coverage。

## 修復（01392b/c/d）

1. `empty_ncc < 0.85` → 標 `empty_freeframe`，改 **SRC GrabCut 雙先驗**（禁 freeframe DIFF 當洞）
2. elev 改 `elev_same_pose`：**禁止 phase warp** · peep 主權姿態
3. hardpaste **只貼 peep alpha @ corners_4**（禁 full-CC mask 貼）
4. S7 加閘：`ncc≥0.90` · `phase<1.5px` · `coverage<0.36` · freeframe 記入 receipt

## 修復後（RUN_NEW_01392d_FIX）

見 `FULL_DRIVER_REPORT.json`：ncc≈0.999 · phase≈0 · peep-only paste。

## 仍不宣稱
- Empty 仍 freeframe（需同機位 inpaint empty 才可真 DIFF 洞）
- GrabCut 仍 candidate（非人工核實剪影）
- ACCEPT_FULL_HD=false
