# STILL SEQUENCE F2F · 調用公式（非 Image-to-Video）

## 0. 硬邊界

| 禁止 | 原因 |
|------|------|
| `imagine_image_to_video` / `imagine_text_to_video` / `imagine_reference_to_video` | 合成**連續運動**，不是「一片一片靜圖組片」 |
| 把 I2V 抽幀當「下一幀生成」驗收 | 運動來自影片模型，不是你的靜圖公式 |
| 用有聲 Imagine 原片冒充組片結果 | 音軌來源不同，會混淆驗收 |

| 允許 | 用途 |
|------|------|
| 既有靜圖 asset / PNG 序列 | 幀庫 |
| `imagine_text_to_image` / `image_to_image` / `reference_to_image` | **只**產下一張**靜圖**（若要補幀） |
| PIL 膠卷／網格 | 視覺排版 |
| ffmpeg `image2` 序列 → mp4 | **靜幀播放**（可加 anullsrc 靜音軌，必須標 `audio=silence`） |
| SIFT / MAE / DDXX | 相鄰**靜圖**幾何／像素差（不是「電影物理真幀」） |

**口號：組片 = 排程靜圖；I2V = 合成時間。兩條路永遠分欄。**

## 1. 對話偏航時間線（DEBUG）

1. 你要 **NEXT FRAME / FRAME-TO-FRAME**，並寫明 **PIL 膠卷 + ffmpeg 寫回 mp4**。
2. 正確解讀應是：`frames[]` 有序靜圖 → 組片 → 量測。
3. 我誤把「生成下一幀能力」解成 **Imagine Image-to-Video**（15s+6s），再抽幀對 v12。
4. 你再問「為什麼有聲音／是否等於生成影片」——暴露混線。
5. 正解：**你要的是多圖組件公式，不是 I2V 按鈕。**

## 2. 多組件公式（抽象）

```
Input:
  S0..Sn-1   # 有序靜圖路徑或 asset_id
  fps        # 播放速率（例如 24；只影響播放，不創造運動）
  labels     # 可選：t_index, source_tag

Pipeline:
  C1 FrameBank.ingest(S*)
  C2 Metrics.pair_adjacent(S_i, S_{i+1})   # MAE / optional flow-on-stills / SIFT
  C3 Layout.filmstrip | Layout.grid       # PIL
  C4 Encode.stills_mp4(fps, audio=silence)
  C5 Report.write(JSON)                   # motion_source=still_sequence

Forbidden:
  C_video = ImageToVideo(S0)              # 不進本公式
```

## 3. 組件契約

### C1 FrameBank
- 輸入：路徑列表或目錄 `frame_%04d.png`
- 輸出：`manifest.json`（index, path, sha256, wh）
- 失敗：缺幀、尺寸不一致 → fail-closed

### C2 Metrics（相鄰靜圖）
- MAE, p95；可選 Farneback（**對兩張靜圖**，不是真 1/24s 物理）
- SIFT/DDXX 可選
- 報告必須寫：`sampling=still_adjacent_not_native_cinema_unless_labeled`

### C3 Layout
- filmstrip：橫向縮圖條
- grid：N×M
- 禁止把 layout 圖再當「生成影片源」混報

### C4 Encode
```bash
ffmpeg -framerate {fps} -i frame_%04d.png \
  -f lavfi -t {dur} -i anullsrc=r=48000:cl=stereo \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest out.mp4
```
- 標籤：`motion_source=still_playback` · `audio=silence_anullsrc`

### C5 Report
```json
{
  "mode": "still_sequence_f2f",
  "not_image_to_video": true,
  "n_frames": 0,
  "fps_playback": 24,
  "motion_source": "still_sequence",
  "audio": "silence_anullsrc",
  "quality_qualified": false
}
```

## 4. 後續調用口令（給人／給 Grok）

| 你說 | 我應做 |
|------|--------|
| 「組片／串幀／膠卷／ffmpeg 寫回」 | **只** C1–C5，**禁止 I2V** |
| 「下一張靜圖／補幀」 | 靜圖生成 → 進 FrameBank |
| 「生成影片／I2V／動起來」 | 才開 video 工具，且**另開欄**，不寫進 still 驗收 |
| 「對 v12 下限」 | 僅在**同源靜幀採樣**時比；I2V 抽幀**另表** |

## 5. CLI

```bash
python tools/still_sequence_f2f_kit.py \
  --frames-dir path/to/frames \
  --glob 'n_*.png' \
  --fps 24 \
  --out-dir runs/still_f2f_demo \
  --filmstrip --grid --mp4 --metrics
```
