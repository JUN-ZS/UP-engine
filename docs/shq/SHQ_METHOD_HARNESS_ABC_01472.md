# SHQ · 方法驗收 Harness A/B/C（01472）

**formal:** `SHQ_KILL01433_HARNESS_ABC_V1`  
**write_id:** `01472`  
**PY:** `shq_method_harness_abc.py`  
**KILL 附:** `SHQ_KILL_01433_RANKING.md`  
**參考流程:** 換涯人／機炸回／新畫女／回車大炮／四態反／外力GROK／新女畫V2／外力反 V2.1  
**ACCEPT_FULL_HD:** false

---

## 0. 一句

> 三層不可互替：  
> **A 單方法** · **B 組合** · **C 跨場景矩陣**。  
> A 通 ⇏ B 通；B 通一景 ⇏ C 通。  
> 同場景內凍結 `KEEP/EMPTY/HOLE/peeps/elev`，**只換方法**。

---

## 1. 對位具名 STICK 流程（Harness 凍結什麼）

| STICK | 流程摘要 | Harness 凍結 |
|-------|----------|--------------|
| **換涯人** 01439 | SRC→PEEP→HD→EMPTY→LOCK_PASTE | SRC·M_hole·peep corners·elev_remap=false |
| **機炸回** 01441 | PARTMAP→EXPLODE→4corner→MAT hardpaste | 圖邊四角·互斥件·α XOR |
| **新畫女** 01443 | a8b→ST1→ST2→PATH1E→ECC | 身份錨·plate 只在洞內 |
| **回車大炮** 01445 | L1 18 + S2 樹 + MULTI_RETURN | 相對樹·件級 peep |
| **四態反** 01448 | (生除洞扣)×反 + State Bus | 不變量·獨立≠可組合 |
| **外力GROK** 01466 | Imagine 除件/除背/生 | CLIP 只從除背 |
| **新女畫V2** 01464 | a8b×洞座×(N)(X) | 無洞回=教材失敗 |
| **外力反V2.1** 01469 | TunePack any object | 凍結洞·outside 對凍結洞 |

Harness **不替身**完整 skill 引擎；它提供 **公平比較與組合閘** 的骨架，對接上述契約。

---

## 2. 層定義

### A · 單方法驗收

```text
SceneBundle 凍結後：
  for method in distinct_methods:
      RETURN = method(BASE, peeps, elev)  # BASE=EMPTY 或 KEEP
      outside = max|RETURN-BASE| on (¬M_hole_frozen)
      PASS_A ⇔ outside==0
```

- 同場景全部方法共用同一 bundle  
- **禁** 每方法換原圖（那是 01433 死因）  
- 磁碟 re-read 再算 outside（修 JPEG/記憶體不一致）

### B · 組合驗收

```text
mutex:      Σ 1[peep_i] ≤ 1  per pixel
order:      compose(fwd) == compose(rev)
outside:    對凍結 M_hole
seam:       邊界梯度 proxy（報告用，非唯一 PASS）
```

- 測的是 **連動**，不是 22 排名  
- 對應 01448：獨立 PASS ≠ 可組合

### C · 跨場景矩陣

```text
for scene in scenes:
    run A(scene) + B(scene)
→ matrix[scene, method]  ·  禁止壓成單一 RANK
```

- 場景是 **block**  
- 方法比較只在 block 內配對  

---

## 3. 凍結 SceneBundle 契約

| 欄 | 義 |
|----|-----|
| KEEP | L0 原圖 |
| EMPTY | **真無主體底**（synth 建構；實跑應外力除／同鏡空，禁 Telea 自欺） |
| HOLE | **凍結** \(M_{hole}\) · 方法不得改寫後拿來算 outside |
| peeps[] | 互斥 mask + peep_rgb + elev_rgb + part_role |
| SCENE_BUNDLE.json | sha 指紋 · mutex_ok |

\[
M_i \cap M_j = \varnothing \quad (i\neq j)
\]

每個像素至多一個 peep 擁有；需要重疊必須顯式融合規則（預設：禁）。

---

## 4. 方法登記（誠實）

- 01433 宣稱 22；本 harness **合併別名**（R02/R08/R21/R22→R01）  
- 假 NEURAL→`dens_u`；假 GUIDED→`edge_preserve`  
- 權限自擴張族（R09 類）**BAN**  
- 見 `list-methods` / `METHOD_REGISTRY.txt`

---

## 5. CLI

```bash
python3 shq_method_harness_abc.py selftest
python3 shq_method_harness_abc.py kill-note
python3 shq_method_harness_abc.py list-methods
python3 shq_method_harness_abc.py list-sticks
python3 shq_method_harness_abc.py init-scene --out runs/S01 --preset synth_cliff
python3 shq_method_harness_abc.py run-A --scene runs/S01 --out runs/S01/A
python3 shq_method_harness_abc.py run-B --scene runs/S01 --out runs/S01/B
python3 shq_method_harness_abc.py run-C --scenes runs/S01,runs/S02 --out runs/C_MATRIX
```

presets: `synth_cliff`（換涯人）· `synth_dual_mecha`（外力反）· `synth_3subj`（回車大炮）

---

## 6. 宣稱級

| 產物 | 級 |
|------|-----|
| selftest PASS | **C1 structure** |
| A/B/C 報告 | **C2 harness** · 非畫質排名 |
| 01433 RANK | **KILL** |
| ACCEPT_FULL_HD | **false** |

---

## 7. 與 01470 關係

外力反 V2.1 已修：**CLIP 從除背、TunePack、禁自 peep**。  
本 harness 補的是 **跨方法公平實驗骨架** + **01433 假 PASS 死刑**。  
兩者並立，不互相冒充 C5。

asof: 2026-11-10
