# Grok Imagine — IGE-SHQ 輔助材質 Donor Prompt Pack

## 用途界線

Imagine 的定位是**產生額外的材質／微細節參考 donor**，不是取代 S0 Keep/Remove、S1 masks、S2 geometry lock，也不是生成最終 5504×3072 master。生成圖有可能改變透視、拓撲、部件邊界、數量或位置；這些部分不能成為幾何真值。

每張圖獨立生成、獨立記錄 prompt 和 SHA。不要覆寫原本 `assets/` 的 13 張 canonical assets。先把生成圖交給 Grok Bot，再執行 `grok_shq_runner.py --register-donor ...`。

## 共用負面約束（每次貼在 prompt 後段）

```text
This is a material-reference donor, not a final character or scene image.
Do not create a full character, robot, body, face, weapon, pose, silhouette, or battlefield composition.
No text, labels, logos, watermarks, grids, panels, borders, UI, or measurement marks.
No perspective view, dramatic camera angle, depth-of-field blur, motion blur, or strong cast shadows.
Keep the material physically plausible, with consistent scale and lighting across the entire image.
Avoid large-scale gradients and obvious repeating seams. Do not invent geometry or imply that this image defines any object's boundary.
The result is only an auxiliary texture source; preserve no claim of pixel-exact geometry.
```

## Donor A — B1 P08 金網絲＋碳纖維胸甲

```text
Create a high-detail orthographic macro material reference for a fictional precision mechanical armor surface: fine gold metallic wire mesh embedded over matte black carbon-fiber composite. Show tightly controlled micro-scale weave, realistic thin gold strands, dark carbon weave beneath, tiny fastening points, subtle machining variation, restrained specular response, neutral studio illumination. The image should read as a flat material study with no recognizable torso outline and no complete object.
```

## Donor B — B0 白鈦裝甲

```text
Create an orthographic macro material donor of brushed white titanium mechanical armor plating. Show fine directional machining marks, subtle bead-blasted microtexture, shallow panel grooves, tiny fastener recesses and physically plausible metal reflectance. Neutral soft lighting, high local detail, no complete robot, no silhouette, no labels, no dramatic reflections.
```

## Donor C — B2 銅色冷卻線圈

```text
Create an orthographic macro material donor of tightly wound copper-alloy cooling coils and precision mechanical heat-exchanger details. Show consistent wire gauge, realistic winding pitch, fine oxidation variation, small attachment clips and controlled metallic highlights. Flat close-up material study, no full machine, no perspective distortion, no labels or background props.
```

## Donor D — 黑色碳纖維／陶瓷複合材

```text
Create a highly detailed orthographic macro material reference of black carbon-fiber composite mixed with dark technical ceramic. Include a fine woven fiber pattern, subtle resin depth, tiny pores and realistic non-uniform micro-reflections. Keep texture scale consistent. No complete character, no panel outline, no text, no perspective.
```

## Donor E — 金屬網格接縫／螺絲微細節

```text
Create an orthographic macro detail reference sheet of miniature mechanical fastening details: fine mesh seams, tiny recessed screws, narrow precision joints, micro-clips and thin metallic ribs. Use a restrained industrial palette of dark graphite, muted gold and steel. Keep every detail physically plausible and at consistent scale. This is a donor study only, not a complete object or layout.
```

## Imagine 生成後的交接

1. 保留 Imagine 產生的原檔，不在 Canvas 重新匯出壓縮版本代替原檔。
2. 上傳原圖至 Grok Bot 的專案目錄，例如 `/workspace/grok_imagine_donors/`。
3. 登記：

```bash
python grok_shq_runner.py --register-donor /workspace/grok_imagine_donors/gold_mesh.png --label B1_P08_gold_mesh
```

4. 把回傳的 `sha256`、尺寸、label、prompt 和 Imagine 日期加入 Canvas 的執行紀錄。
5. `REGISTERED_NOT_PIPELINE_WIRED` 是正確狀態。原 M12/M13 尚未讀取該資料夾，所以不要說它已被模型吸收或已用於 master。
6. 要令 donor 真正進入 M12/M13，另開 source patch：定義 donor manifest、part-to-donor mapping、對齊品質門檻、遮罩授權、頻帶範圍、輸入／輸出 SHA，以及獨立 holdout 測試。不要直接把 Imagine 圖塞進原本 HR asset 名稱。
