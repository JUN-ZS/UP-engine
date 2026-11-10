# SHQ · 外力GROK（WAI_LI_GROK）（01466）

**formal:** `WAI_LI_GROK_IMAGINE_EDIT_V1`  
**zh:** **外力GROK**  
**en:** External-Force Grok · Imagine External EDIT  
**alias:** 外力 · Imagine 外編 · §19/§22 主權  
**STICK:** `STICK_WAI_LI_GROK`  
**LOCK:** `CONSTITUTION_LOCK_01466.json`  
**權威:** `docs/GROK_IMAGINE_FUNCTION_CODES.md`（§19h–§19m · **§22 本 write**）  
**被誰用:** 外力反 V1/V2/V3 · 新女畫 V2 · 真四態 CLIP · 機炸回除生 · 回車大炮外編步  
**ACCEPT_FULL_HD:** false

---

## 0. 一句（定義）

```text
外力GROK ≔ Grok Imagine 的「外部 EDIT 功能」全集
         （以 docs/GROK_IMAGINE_FUNCTION_CODES.md 為法）
         在升清回位鏈中，凡標【外力】的 除 / 生 / 洞內填 / 除背
         必須調用 Imagine 工具落地，禁止本地像素冒充。
```

> **外力 = 力在 Grok Imagine 外編；不是 OpenCV、不是自 peep、不是 checker 手塗洞。**  
> **外力GROK 是技能名；Imagine EDIT 是它的執行器。**

---

## 1. 什麼算「外力GROK」（合法工具）

| 能力 | Imagine 工具 | 四態角色 |
|------|--------------|----------|
| **除**（去目標／去背） | `imagine_image_to_image` | 除 |
| **除背** → 後扣 CLIP | `imagine_image_to_image` | 除 → 扣 → CLIP |
| **洞內生**（INPAINT／填洞） | `imagine_reference_to_image` 或 `imagine_image_to_image` | 生 |
| **plate／姿×身份** | `imagine_reference_to_image` | 生準備 |
| **可選：外力抽主體** | `imagine_extract_subject` | 扣／CLIP 輔助（非自 peep bbox） |
| **可選：區域外編** | `imagine_region_edit` | 洞區生／局部除 |

**必須落盤：** 每步 Imagine 產出 **獨立 asset_id**，寫入 RUN `S_IMAGINE/` 與 REPORT `assets`。

---

## 2. 什麼不算（偷步 · 禁）

| 禁 | 為何不是外力GROK | E 碼 |
|----|------------------|------|
| OpenCV `inpaint` / 填色當「除」 | 本地假除 | **E-WLG-01** |
| OpenCV 裁 bbox 當 peep／CLIP | 自 peep | **E-WLG-02** |
| checker／紫疊手塗當「真洞」卻無 Imagine 除 | 無外力對證 | **E-WLG-03** |
| freeframe densify map 當「生回」 | 無洞座外力生 | **E-WLG-04** |
| 只文字描述「已除」無 asset | 無執行 | **E-WLG-05** |
| 跳過 Imagine 用硬貼原像素冒充「生」 | 偷步 | **E-WLG-06** |

> 本地 **kou／hardpaste／letterbox elev 尺** 仍可作 **扣／回／尺度契約**；  
> **不可** 用它們替代 除 與 生 的 Imagine 主權。

---

## 3. 與「外力反」的關係

```text
外力GROK     = 執行器定義（Imagine EDIT 主權）
外力反 V1/V2/V3 = 連招（除→扣→洞→生→放大加清→回→反）
真四態 CLIP  = 除背必須走外力GROK
新女畫 V2    = 身份 a8b + 外力GROK 洞座返
```

**凡稱「外力反」而未跑外力GROK 除/生 = 偷步，不得報 SUCCESS。**

---

## 4. 最小合法環（單層）

```text
WLG-0  L0 freeze
WLG-1  【外力GROK·除】imagine_image_to_image → L_edit  (asset 落盤)
WLG-2  【扣】kou(L0,L_edit) → M · MARK
WLG-3  【洞】真洞板 = L_edit 可視化（外力結果，非手塗）
WLG-4  【外力GROK·生】imagine_* 只填洞 → R  (asset 落盤)
WLG-5  hardpaste 可選 · outside=0
WLG-6  反板 + 若缺 Imagine asset → NEED_IMAGINE_* 硬停
```

多層：每層 X 重複 WLG-1..4；STACK 經 MARK（外力反 V2）。

---

## 5. 功能碼錨（docs）

權威全文：`docs/GROK_IMAGINE_FUNCTION_CODES.md`

| 節 | 內容 |
|----|------|
| §19h–§19l | 外力除／生／洞 原契約 |
| §19m | 外力反 · 放大加清 |
| **§22** | **外力GROK 技能定義（本 write）** |
| §20 | 回車大炮（可調用外力GROK 步） |
| §21 | 新女畫 V2（除背／除頭／plate／生 = 外力GROK） |

---

## 6. E 碼

| 碼 | 禁 | 治 |
|----|-----|-----|
| **E-WLG-01** | 本地假除 | 重跑 image_to_image 除 |
| **E-WLG-02** | 自 peep 冒充 CLIP | 外力除背再扣 |
| **E-WLG-03** | 無 Imagine 除的「洞」 | 先除後 kou |
| **E-WLG-04** | freeframe 當生 | 生 on L_empty 洞 |
| **E-WLG-05** | 無 asset 宣稱外力 | 落盤 asset_id |
| **E-WLG-06** | 硬貼冒充生 | Imagine 洞內生 |
| E-WLF2-02 | 子層無 Imagine | 同外力GROK |

---

## 7. 宣稱

| 級 | 條件 |
|----|------|
| C2_WAI_LI_GROK | 除+生均有 Imagine asset · MARK · 真洞可視化 · 無偷步項 |
| C3 | + outside log · 反板齊 |
| C5 | Gold+CI only |

---

## 8. 金句

> **外力GROK：除與生，只認 Imagine；kou 只作證，不替代。**  
> **沒有 GROK 外編 asset，就沒有「外力」——只有本地戲法。**  
> **技能名外力GROK = 功能碼裡的 Imagine EDIT 主權。**

---

## 9. 狀態

`implementation_status=constitution_skill_locked`  
`canonical_name=外力GROK`  
`maps_to=Grok Imagine external EDIT (FUNCTION_CODES)`  
