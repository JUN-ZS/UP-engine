# N1 · Native Canvas Tiling

| | |
| --- | --- |
| **Status** | `N1_SCAFFOLD_OK` · scaffold + **local PC** plan/init/smoke |
| **asof** | 2026-11-02 |
| **native_4k_success** | `false` |
| **final_acceptance** | `false` |
| **≠** | 4× Siax of low-res BASE (`NATIVE_4K_VS_SIAX4X_BOUNDARY.md`) |

---

## 0. Question

Can we **directly** own a **target-resolution canvas** (default **3840×2160**) and produce content as **overlapping tiles computed at that resolution**, then rebuild a single verifiable frame — **without** “generate small → fixed 4× ESRGAN” as the definition of done?

---

## 1. In scope (N1)

| ID | Item |
| --- | --- |
| N1.1 | Target canvas size locked in plan (default 3840×2160) |
| N1.2 | Tile grid with **overlap** in **target** pixels |
| N1.3 | Per-tile job receipt: id, box, overlap, optional input ref, output SHA |
| N1.4 | Stitch cores only (or weighted overlap) → full PNG + SHA |
| N1.5 | Explicit flags: `path=native_canvas_tiling`, `not_siax_4x_upscale=true` |

**v0 scaffold** delivers N1.1–N1.5 geometry + empty/structure canvas + stitch API.  
**Tile *generation* at native res** (diffusion / local SPM fill) is **N1.gen** — separate; not claimed done by scaffold.

---

## 2. Non-goals

| ❌ | |
| --- | --- |
| Calling 1792×1008 → 7168×4032 Siax **native 4K** | |
| Replacing warrior 4× baseline evidence | |
| Full quality PASS / E3 | |
| Requiring S3 dual-host for N1.0 | |
| Training distill (see SPM_DISTILL_CHARTER) | |

---

## 3. Default geometry (v0)

```text
canvas:  3840 × 2160   (true 4K UHD frame)
tile:    512 × 512     (target px)
overlap: 64            (target px; each side)
```

Derived tile step = tile − overlap. Edge tiles clip to canvas.

---

## 4. CLI

```powershell
python tools/n1_plan.py --width 3840 --height 2160 --tile 512 --overlap 64 --out runs/n1/plan.json
python tools/n1_init_canvas.py --plan runs/n1/plan.json --out runs/n1/canvas.png
# optional structure only (NOT Siax 4x claim):
python tools/n1_init_canvas.py --plan runs/n1/plan.json --base packages/spm_here/warrior_mud_hammer/warrior_BASE.jpg --fit contain --out runs/n1/canvas_struct.png
python tools/n1_stitch.py --plan runs/n1/plan.json --tiles-dir runs/n1/tiles --out runs/n1/OUT_NATIVE.png
```

---

## 5. Acceptance labels

| Label | Meaning |
| --- | --- |
| `N1_SCAFFOLD_OK` | plan + init + stitch round-trip on synthetic tiles |
| `N1_GEN_PILOT_OK` | at least one real native-res generative fill (future) |
| `NATIVE_4K_PILOT_OK` | product-level pilot (future; human review) |

Scaffold success **≠** native 4K product success.

---

## 6. Relation to N2 / N3

- **N2** supplies *what* draws inside a native tile (generative SPM).  
- **N3** may add Siax high-freq *inside* a tile after structure exists.  
- **N1** owns **canvas + tile ledger + stitch** only.


---

## 7. Local PC confirmation

Evidence: `docs/evidence/N1_SCAFFOLD_LOCAL_PC.json`  
User host: 3840×2160 plan (45 tiles), empty canvas, Lanczos structure fit, smoke 15/15.  
**Still not** N1_GEN_PILOT_OK / NATIVE_4K_PILOT_OK.
