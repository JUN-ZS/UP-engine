# IGE-SHQ「真升清 → 鎖幾何併回大圖」模組化方法庫與逐一調用指南 (`v2.0`)

本專案將全鏈路 22 個已註冊方法（`M01`–`M22`）與 3 個端到端組合應用（`R01`–`R03`）按工程階段與職責分類為 **5 大方法資料夾 (`methods/cat01..cat05`) + 1 個組合應用資料夾 (`recipes/`)**。每一個方法皆為獨立可執行的 `.py` 應用程式，支援其他 AI 或開發者透過統一調用器 `invoke_method.py` 或直接執行個別 `.py` 檔案逐一試用、單獨出圖並檢視 JSON 驗收收據。

## 1. 快速調用方式（供其他 AI 使用者逐一試用）

### A. 列出全部 22 個分類方法、3 個組合應用與 18 個可選部件
```bash
# 列出 5 大分類、22 個方法 (M01..M22) 與 3 個組合應用 (R01..R03)
python invoke_method.py --list

# 列出戰場三主體可單獨指定試用的 18 個完整流線自身部件 (P01..P18)
python invoke_method.py --list-parts

# 查看單一方法的輸入、輸出、宣稱邊界與驗收門檻
python invoke_method.py --info M12
python invoke_method.py --info SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD
```

### B. 逐一調用單一方法（支援代碼 `M01`..`M22` 或完整 `METHOD_ID`）
```bash
# 方式 1：透過統一調用入口 invoke_method.py 試用單一方法
python invoke_method.py --run M01
python invoke_method.py --run M04 --part P08
python invoke_method.py --run M12 --part P08
python invoke_method.py --run M15 --part P08 --gamma 0.45
python invoke_method.py --run M22 --part P02

# 方式 2：直接執行分類資料夾下的獨立 .py 檔案
python methods/cat01_s0_anti_hole_and_base/m01_bf_s0_edit_4way_anti_hole.py
python methods/cat02_s1_s2_part_read_and_5d_lock/m04_bf_s1_self_18part_decompose_read.py --part P08
python methods/cat04_s4_s5_true_hd_upgrade_engines/m12_skill_b_geometry_locked_material_gen.py --part P08
python methods/cat05_s6_s7_geometry_locked_return_and_audit/m22_skill_d_immutable_alpha_geometry_guard.py --part P02
```

### C. 按分類整組調用、執行端到端組合 Recipe，或一鍵逐一全測
```bash
# 按分類試用整組方法 (例如 cat04 真升清核心引擎類)
python invoke_method.py --category cat04 --part P08

# 執行端到端組合應用 Recipe (R01 單部件升清回位 / R02 全 18 部件升清回大圖 / R03 四階消融實驗)
python invoke_method.py --recipe R01 --part P08
python recipes/r03_ablation_compare_a_b_c_d.py --part P02 --gamma 0.45

# 自動逐一執行全部 22 個方法 + 3 個組合應用，並產出 25 宮格總覽圖與總報告
python try_all_methods_one_by_one.py --part P08
```

### D. 從其他 Python 程式作為 SDK 模組調用
```python
from invoke_method import run_single_method_by_key, run_recipe_by_key
from methods.cat04_s4_s5_true_hd_upgrade_engines.m12_skill_b_geometry_locked_material_gen import run_method

# 直接調用單一方法 M12 (技能 B：幾何鎖定中頻材質層)
receipt_m12 = run_method(part_id="P08")
print(receipt_m12["status"], receipt_m12["metrics"])

# 調用端到端單部件升清併回大圖組合 R01
receipt_r01 = run_recipe_by_key("R01", part_id="P02")
```

## 2. 全專案 5 大方法分類與 22 個獨立 `.py` 檔案總表

### 分類 01：`methods/cat01_s0_anti_hole_and_base/` — S0 原圖凍結與正反對照空背景「生・除・扣・洞・反洞」類

| 代碼 | 方法 ID (`method_id`) | 獨立 Python 檔案路徑 | 核心功能與交付產物 | 單獨調用指令 |
| :--- | :--- | :--- | :--- | :--- |
| **M01** | `BF_S0_EDIT_4WAY_ANTI_HOLE` | `methods/cat01_s0_anti_hole_and_base/m01_bf_s0_edit_4way_anti_hole.py` | 對照同鏡頭原圖 (`Keep`) 與空背景 (`Remove`)，求出有機閉合剪影洞 `M_hole` 與反洞 `M_anti_hole`（`M_hole ^ M_anti_hole == 255`） | `python invoke_method.py --run M01` |
| **M02** | `HOLE_FOUR_ANTI_EVIDENCE` | `methods/cat01_s0_anti_hole_and_base/m02_hole_four_anti_evidence.py` | 四反防呆驗收（反偷縮放、反相機平移 `<=0.1px`、反背景異動、反軟邊羽化 `soft_px=0`），驗證差分僅為幾何證據 | `python invoke_method.py --run M02` |

### 分類 02：`methods/cat02_s1_s2_part_read_and_5d_lock/` — S1–S2 自身 18 部件流線拆解、無框 5D 定位與 4× 幾何鎖定類

| 代碼 | 方法 ID (`method_id`) | 獨立 Python 檔案路徑 | 核心功能與交付產物 | 單獨調用指令 |
| :--- | :--- | :--- | :--- | :--- |
| **M03** | `READ_LAYERED_EVIDENCE` | `methods/cat02_s1_s2_part_read_and_5d_lock/m03_read_layered_evidence.py` | S1 分層語義觀察與反過度宣稱讀取器（對不可見 3D 背面強制輸出 `unknown`） | `python invoke_method.py --run M03 --part P08` |
| **M04** | `BF_S1_SELF_18PART_DECOMPOSE_READ` | `methods/cat02_s1_s2_part_read_and_5d_lock/m04_bf_s1_self_18part_decompose_read.py` | 戰場三主體拆解為 18 個互不重疊 (`overlap=0`)、無斷頭台平切 (`guillotine=0`) 之流線部件，並作非同義反覆驗收 | `python invoke_method.py --run M04 --part P08` |
| **M05** | `BF_S2_SELF_PART_4X_GEOMETRY_LOCK` | `methods/cat02_s1_s2_part_read_and_5d_lock/m05_bf_s2_self_part_4x_geometry_lock.py` | 將 18 個部件鎖定至 `5504×3072` (4×) 母畫布之四角座標與閉合遮罩，驗證 $T_{\text{scene}\leftarrow\text{leaf}}$ 零誤差並分離五參數 | `python invoke_method.py --run M05 --part P02` |
| **M06** | `BOX_FREE_5D_LOCATE_PROXY` | `methods/cat02_s1_s2_part_read_and_5d_lock/m06_box_free_5d_locate_proxy.py` | 由 2D 閉合遮罩計算距離變換測地線 $(u,v)$、PCA 主軸角 $\theta$ 與球頂法線/深度代理（誠實標註為 2D 代理非 LiDAR 3D） | `python invoke_method.py --run M06 --part P08` |
| **M07** | `PATH1E_IDENTITY_ECC_LOCK` | `methods/cat02_s1_s2_part_read_and_5d_lock/m07_path1e_identity_ecc_lock.py` | 針對 B1 指揮官面部與關鍵感測器部件執行亞像素相位與 ECC 結構對齊鎖定，缺失參考圖時強制標記 `unknown` | `python invoke_method.py --run M07 --part P07` |

### 分類 03：`methods/cat03_s3_s4_permission_and_routing/` — S3–S4 人類核實權限編譯、拓撲守門與狀態技能路由類

| 代碼 | 方法 ID (`method_id`) | 獨立 Python 檔案路徑 | 核心功能與交付產物 | 單獨調用指令 |
| :--- | :--- | :--- | :--- | :--- |
| **M08** | `BF_S3_HUMAN_PERMISSION_COMPILER` | `methods/cat03_s3_s4_permission_and_routing/m08_bf_s3_human_permission_compiler.py` | 將人類核實後的 4× 部件編譯為嚴格互斥的 `edit_mask_4x` 與 `preserve_mask_4x`；未核實時強制阻斷寫入 | `python invoke_method.py --run M08` |
| **M09** | `OTL0_TOPOLOGY_REPAIR` | `methods/cat03_s3_s4_permission_and_routing/m09_otl0_topology_repair_gate.py` | 拓撲守門器：當外輪廓破損 (`outer_shape_broken=True`) 時強制阻斷下游高頻增強 (`SKILL_C`/`DETAIL6`) | `python invoke_method.py --run M09 --part P02` |
| **M10** | `INPAINT_HOLE_REPAIR_OPTIONAL` | `methods/cat03_s3_s4_permission_and_routing/m10_inpaint_hole_repair_optional.py` | 受控選用之遮擋缺損低頻修補器（僅修補局部遮擋孔洞，嚴禁充當主升清引擎） | `python invoke_method.py --run M10 --part P02` |

### 分類 04：`methods/cat04_s4_s5_true_hd_upgrade_engines/` — S4–S5 真升清核心引擎（三頻分解 A/B/C/C2/C3 與多源高清轉移類）

| 代碼 | 方法 ID (`method_id`) | 獨立 Python 檔案路徑 | 核心功能與交付產物 | 單獨調用指令 |
| :--- | :--- | :--- | :--- | :--- |
| **M11** | `SKILL_A_NEURAL_SR_BASE_4X` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m11_skill_a_neural_sr_base_4x.py` | **技能 A**：在鎖定的 4× 座標內重建零相位漂移 (`<=0.05px`) 的低頻形體基底層 $L_{\text{base}}$，不改動 Alpha | `python invoke_method.py --run M11 --part P08` |
| **M12** | `SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m12_skill_b_geometry_locked_material_gen.py` | **技能 B**：從幾何鎖定與上下半身高清母本經密集光流對齊 (`NCC >= 0.98`) 提取中頻材質反射層 $M_{\text{material}}$ | `python invoke_method.py --run M12 --part P08` |
| **M13** | `SKILL_C_MULTISCALE_DETAIL_SYNTHESIS` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m13_skill_c_multiscale_detail_synthesis.py` | **技能 C**：合成與基底、材質正交分離之零均值高頻微細節殘差層 $H_{\text{detail}}$（接縫、螺絲、金網絲、刮痕） | `python invoke_method.py --run M13 --part P08` |
| **M14** | `SKILL_C2_NORMAL_DEPTH_STRUCTURAL_DETAIL` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m14_skill_c2_normal_depth_structural_detail.py` | **技能 C2**：利用 2D 切空間法線與深度梯度代理導引微接縫與金絲沿曲面結構方向貼合 | `python invoke_method.py --run M14 --part P08` |
| **M15** | `SKILL_C3_ATTENUATE_HF_DETAIL_LAYER` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m15_skill_c3_attenuate_hf_detail_layer.py` | **技能 C3**：高頻細節無損衰減器（僅對 $H_{\text{detail}}$ 乘上 $\gamma$，保持 $L_{\text{base}}$ 與 $M_{\text{material}}$ Bit-Identical） | `python invoke_method.py --run M15 --part P08 --gamma 0.45` |
| **M16** | `ALL24_AI_DONOR_MULTIBAND_TRANSFER` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m16_all24_ai_donor_multiband_transfer.py` | AI 高清母本多頻段對位轉移引擎（如實記錄 `1200×896` 母本尺寸與 SHA-256，不偽稱為即時 8K 擴散） | `python invoke_method.py --run M16 --part P14` |
| **M17** | `DETAIL6_MATERIAL_RESIDUAL` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m17_detail6_material_residual.py` | 材質分區遮罩高頻投遞器（對裝甲/金絲投遞高頻能量，對 B1 指揮官面部皮膚強制維持 0 額外高頻變動） | `python invoke_method.py --run M17 --part P08` |
| **M18** | `HOLE_SCALELOCK_HF_RESIDUAL` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m18_hole_scalelock_hf_residual.py` | 非生成式比例鎖定高頻殘差對照基準（作為對比真 AI 三層升清增益的科學對照組） | `python invoke_method.py --run M18 --part P08` |
| **M19** | `SIAX4X_TILE_CORE_SR` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m19_siax4x_tile_core_sr_contract.py` | Siax 4× Tile-Core 超分契約與反插值偽造守衛（離線環境誠實回報契約模式，嚴禁以 Lanczos 冒充 Siax 推理） | `python invoke_method.py --run M19 --part P02` |
| **M20** | `FLUX_HR_TILE_IMG2IMG` | `methods/cat04_s4_s5_true_hd_upgrade_engines/m20_flux_hr_tile_img2img_contract.py` | Flux HR Tile Img2Img 分塊擴散契約與收據守衛（驗證 Core+Halo 讀取與 Disjoint Core 寫回契約，不偽造 GPU 收據） | `python invoke_method.py --run M20 --part P02` |

### 分類 05：`methods/cat05_s6_s7_geometry_locked_return_and_audit/` — S6–S7 規則 01380 鎖幾何併回大圖與磁碟重讀反驗類

| 代碼 | 方法 ID (`method_id`) | 獨立 Python 檔案路徑 | 核心功能與交付產物 | 單獨調用指令 |
| :--- | :--- | :--- | :--- | :--- |
| **M21** | `GEOMETRY_LOCKED_TILE_PLAN_RETURN` | `methods/cat05_s6_s7_geometry_locked_return_and_audit/m21_geometry_locked_tile_plan_return.py` | 全局幾何分塊規劃與 Disjoint Write-Core 零疊影精確回位器（排除 Halo 寫入，Core 重疊=0、缺口=0） | `python invoke_method.py --run M21` |
| **M22** | `SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD` | `methods/cat05_s6_s7_geometry_locked_return_and_audit/m22_skill_d_immutable_alpha_geometry_guard.py` | **技能 D**：不可變 Alpha 守衛 + 規則 `01380` 全洞 100% 直達硬邊併回 `5504×3072` 大圖 + S7 磁碟重讀反扣驗收 | `python invoke_method.py --run M22 --part P08` |

### 分類 06：`recipes/` — 端到端「真升清 → 鎖幾何併回大圖」組合應用調用類

| 代碼 | 組合應用檔案路徑 | 串聯方法鏈 (`Chain`) | 適用場景 | 調用指令 |
| :--- | :--- | :--- | :--- | :--- |
| **R01** | `recipes/r01_single_part_hd_upgrade_and_return.py` | `M01 → M04 → M05 → M11 → M12 → M13 → M22` | 任選單一自身部件（`P01`–`P18`）執行完整三頻升清與規則 `01380` 鎖幾何併回大圖驗收 | `python invoke_method.py --recipe R01 --part P08` |
| **R02** | `recipes/r02_full_18parts_battlefield_4x_return.py` | `M01 → M04 → M05 → M08 → M11 → M12 → M13 → M21 → M22` | 全戰場 18 部件完整「生・除・扣・洞 → 密集光流真升清 → 併回 `5504×3072` 大圖 → S7 反驗」 | `python invoke_method.py --recipe R02` |
| **R03** | `recipes/r03_ablation_compare_a_b_c_d.py` | `M11 → M12 → M13 → M14 → M15 → M22` | 四技能三頻消融對比（Stage1 僅 SR vs Stage2 +材質 vs Stage3 +微細節 vs C3 高頻衰減回退） | `python invoke_method.py --recipe R03 --part P02 --gamma 0.45` |

## 3. 18 個可選戰場自身部件代號表 (`--part P01` .. `P18`)

| 簡碼 | 完整部件 ID (`part_id`) | 所屬主體 | 對應高清母本 (`assigned_hr_source_key`) |
| :--- | :--- | :--- | :--- |
| `P01` | `B0_P01_OPTICAL_SENSOR_HEAD` | 左側白鈦先鋒機甲 (`B0`) | `B0_UPPER` / `B0_GL` |
| `P02` | `B0_P02_TITANIUM_CHEST_CORE` | 左側白鈦先鋒機甲 (`B0`) | `B0_UPPER` / `B0_GL` |
| `P03` | `B0_P03_RIGHT_SHOULDER_AND_ARM` | 左側白鈦先鋒機甲 (`B0`) | `B0_UPPER` / `B0_GL` |
| `P04` | `B0_P04_LEFT_SHOULDER_ROTARY_SHIELD` | 左側白鈦先鋒機甲 (`B0`) | `B0_UPPER` / `B0_GL` |
| `P05` | `B0_P05_PELVIS_AND_THIGHS` | 左側白鈦先鋒機甲 (`B0`) | `B0_LOWER` |
| `P06` | `B0_P06_HYDRAULIC_BOOTS` | 左側白鈦先鋒機甲 (`B0`) | `B0_LOWER` |
| `P07` | `B1_P07_COMMANDER_HEAD_AND_HAIR` | 中央金網絲女指揮官 (`B1`) | `B1_UPPER` |
| `P08` | `B1_P08_GOLDMESH_CARBON_TORSO` | 中央金網絲女指揮官 (`B1`) | `B1_UPPER` |
| `P09` | `B1_P09_TACTICAL_ARMS_AND_CARBINE` | 中央金網絲女指揮官 (`B1`) | `B1_UPPER` |
| `P10` | `B1_P10_UTILITY_BELT_AND_HOLSTERS` | 中央金網絲女指揮官 (`B1`) | `B1_LOWER` |
| `P11` | `B1_P11_GOLDMESH_ARMORED_THIGHS` | 中央金網絲女指揮官 (`B1`) | `B1_LOWER` |
| `P12` | `B1_P12_KNEE_GREAVES_AND_BOOTS` | 中央金網絲女指揮官 (`B1`) | `B1_LOWER` |
| `P13` | `B2_P13_TWIN_SHOULDER_RAIL_CANNONS` | 右側重型攻城機甲 (`B2`) | `B2_FULL` / `B2_GL` |
| `P14` | `B2_P14_RECESSED_VISOR_AND_CHEST` | 右側重型攻城機甲 (`B2`) | `B2_FULL` / `B2_GL` |
| `P15` | `B2_P15_COPPER_COOLING_COILS` | 右側重型攻城機甲 (`B2`) | `B2_FULL` / `B2_GL` |
| `P16` | `B2_P16_RIGHT_CANNON_ARM` | 右側重型攻城機甲 (`B2`) | `B2_FULL` / `B2_GL` |
| `P17` | `B2_P17_LEFT_BRONZE_GAUNTLET_ARM` | 右側重型攻城機甲 (`B2`) | `B2_FULL` / `B2_GL` |
| `P18` | `B2_P18_TRACKED_HYDRAULIC_LEGS` | 右側重型攻城機甲 (`B2`) | `B2_FULL` / `B2_GL` |
