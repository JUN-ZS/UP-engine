# SHQ Object Geometry Lock — Program Guidance v0.1

**Source conversation:** Gemini share `47yxULPlPy0W` → `970343afbbef`  
**Title:** 物件導向幾何約束升頻架構  
**Transcript:** [`docs/sources/gemini-share-47yxULPlPy0W/Gemini-完整對話.md`](./sources/gemini-share-47yxULPlPy0W/Gemini-完整對話.md)  
**Research fossils:** [`research/shq_v9/`](../research/shq_v9/)  
**Status:** implementer contract / design lock. Not a runtime merge.

---

## 0. One-line intent

Upscale by **locking each object’s geometry first**, then scheduling tiles and generative/inference detail **inside** that contract — **not** by naïve tiling, Lanczos sharpening, soft-alpha cheats, or fake inpaint/補邊.

---

## 1. Parameter separation (hard)

Never let one knob play two roles.

| Variable | Controls | Decided by object? |
|----------|----------|---------------------|
| `model_scale` | Network output factor (Siax = **fixed 4×**) | **No** |
| `object_transform` | Per-object pose / size / silhouette on target canvas | **Yes** |
| `tile_size` | Inference window / VRAM | **No** |
| `tile_context` (prepadding / halo) | Extra border context for the model | Empirically / model-driven |

**Forbidden confusion:** increasing `-t` / tile size must **not** be treated as “make the object larger.”

Global affine for plain Siax 4×:

\[
G = \begin{bmatrix} k R & t \\ 0 & 1 \end{bmatrix},\quad k=4,\ R=I,\ t=0
\]

Per object \(O_i = (B_i, M_i, P_i)\):

- \(B_i^{HR} = \mathrm{bbox}(G(B_i))\)
- \(M_i^{HR} = \mathrm{Rasterize}(G(M_i))\)
- \(P_i^{HR} = G(P_i)\)

Tiles consume \(B_i^{HR}\) / \(M_i^{HR}\); they do not invent them.

---

## 2. Canonical pipeline stages

Implement as ordered stages with **gates**. Skip or reorder only with an explicit contract change.

```
BASE freeze
  → OBJECT READ
  → GEOMETRY LOCK
  → TILE PLANNER
  → SIAX / generative inference
  → GEOMETRY COMPOSE / RETURN
  → ACCEPTANCE
```

### S0 — BASE freeze

**In:** master image \(I_0\), optional empty-BG plate (see §4).  
**Out:** frozen canvas size, provenance SHA-256 of \(I_0\) (and empty-BG if present), color space, bit depth.  
**Gate:** bit-identical re-read of frozen bytes; refuse if SHA drifts mid-run.

### S1 — OBJECT READ

**In:** frozen \(I_0\).  
**Out:** per-object records: bbox / silhouette / landmarks / mask / occlusion order / part hierarchy (L0 world → L1 subjects → L2 whole-parts → L3/L4).  
**Preferred mask root:** Gemini (or equivalent) **native edit** empty background — *not* heuristic grabcut / soft feather.  
**Gate:** every subject has a closed silhouette; hierarchy is mutually exclusive at each layer (no double-claim pixels without an explicit occlusion rule).

### S2 — GEOMETRY LOCK

**In:** READ records + `model_scale` (+ optional non-identity `object_transform`).  
**Out:** HR contracts \(B_i^{HR}, M_i^{HR}, P_i^{HR}\), 4-corner locate cards, DNA / inertia anchors (§5).  
**Gate:** HR boxes are exact transforms of LR contracts (no “visual nudge”); horizontal flip / mirror of parts is a hard fail.

### S3 — TILE PLANNER

**In:** HR canvas + locked masks.  
**Out:** tile grid with `core` vs `halo`/`context`; object∩tile coverage map.  
**Rules:**

- Schedule by **global HR coordinates**.
- Keep only **core** pixels from each tile at compose time; never double-paste halo.
- Tile size ≠ object scale (§1).

**Gate:** union of cores covers every elevated ROI; no orphan locked pixels.

### S4 — SIAX / generative inference

**In:** planned tiles + locked masks (detail only inside closed edge / ROI).  
**Out:** per-tile HR cores (and optional 8× super-ROI donors for micro-parts).  
**Must call a real upscale/gen backend** (Siax NCNN / ComfyUI / Imagine / etc.).  
**Gate:** inference adapter registered; “Lanczos base + CLAHE + unsharp” is **not** an acceptable stand-in (§6).

### S5 — GEOMETRY COMPOSE / RETURN

**In:** elevated whole-parts / layers + locate cards.  
**Out:** master HR canvas.  
**Protocol — `EDGE_WHOLE_PART_ELEV`:**

1. **EDGE** — closed silhouette / hard boundary  
2. **WHOLE** — elevate detail *inside* the closed edge  
3. **LOCATE** — 4-corner (or 5D manifold) place card  
4. **RETURN** — hardpaste / guided return to master  

**Chain the user demanded:**

> 圖 → 解部件 → AI 3D teaching 推原件 → pixel-inertia DNA 框對 → 3D/5D 獨立 layer → ROI/8× elev → 智能併回 master  

Return is **bottom-up** when hierarchical: `L4 → L3 → L2 → L1 → L0`.  
**Gate:** zero ghosting; bit-exact return where the contract promises lossless paste; no soft-alpha “blend away” errors.

### S6 — ACCEPTANCE

Per-object geometry, per-tile coverage/seams, SHA provenance chain, ghosting score, flip/detect audits. Publish JSON report + board; fail closed.

---

## 3. EDGE_WHOLE_PART_ELEV (normative)

| Step | Name | Allowed | Forbidden |
|------|------|---------|-----------|
| ① | EDGE | Closed hard silhouette | Soft alpha feather as “edge” |
| ② | WHOLE | Elevate **inside** edge only | Growing the silhouette via blur/補邊 |
| ③ | LOCATE | 4-corner card / 5D manifold id | Ad-hoc drag; horizontal flip |
| ④ | RETURN | Hardpaste / guided self-return | Soft composite that hides mis-locate |

Debug priority: **return-chain lock** > pretty boards. A horizontal flip in return is a **severity-break** bug, not a cosmetic issue.

---

## 4. CLIPPING MASK REVERSE (root-cause mask)

### Correct procedure

1. Produce **empty-BG** with the **same native image-edit** capability that understands the scene  
   (example intent:「把人和機甲人移除,只剩背景」→ hangar/background only).  
2. Align empty-BG to scene at **identical resolution / registration**.  
3. Reverse mask energy, e.g. \(\|I_{\mathrm{scene}} - I_{\mathrm{empty\_BG}}\|\), then semantic guidance if needed.  
4. If the person/mecha edge is wrong → **fix the empty-BG / reverse root**, regenerate downstream.  
   **Do not** patch the wrong mask with inpaint / 補邊 / polygon nudge-as-fix.

### Wrong (reject in review)

- Synthetic “empty” plates that were themselves composited or inpainted.  
- Keeping stale donor polygons when the reverse plate changed.  
- “DNA snap only shrinks inward” without bidirectional inertia fill when the box under-covers the subject.

**Rule:** wrong root mask ⇒ **entire project compute is waste**; regenerate from root.

---

## 5. Localization: Box-Free 5D (preferred) vs brittle 2D polygons

| Mode | Use when | Notes |
|------|----------|-------|
| Brittle 2D polygon / AABB | Prototypes only | Easy to under-cover (e.g. hair / collar); one bad donor poisons the chain |
| Pixel-inertia DNA | Always as alignment prior | Bidirectional (shrink bg + expand to complete subject) |
| 3D teaching layers | When inferring “what the part was” | Multi-facet / normal / depth teaching plates guide elev |
| **Box-Free 5D manifold** | Production locate for return | Geodesic / UV-like ids instead of hand polygons; supports 8× super-ROI paste-back |

Implementers: prefer manifold ids for RETURN locate; keep AABB only as a debug overlay.

---

## 6. Forbidden practices (CI / review checklist)

Mark **BLOCK** if any appear in production paths:

1. **Lanczos / INTER_LANCZOS4 + CLAHE + unsharp** (or Gaussian residual sharpening) sold as “generative upscale.”  
2. Fake backends: no Siax / NCNN / Comfy / Imagine call, but claiming gen-level detail (`detail_gain` from Sobel ≠ generation).  
3. Soft-alpha / feather used to hide mis-alignment or ghosting.  
4. Horizontal flip / mirrored paste in return chain.  
5. Halo double-paste into the master.  
6. `INTER_AREA` (or similar) **preview downscale** used as proof of bit-exact return.  
7. Inpaint / 補邊 / “fix edges on the wrong mask” instead of regenerating CLIPPING MASK REVERSE root.  
8. Letting `tile_size` mutate `object_transform`.  
9. Stale polygon donors after empty-BG / DNA formula change.

---

## 7. Evidence & provenance gates

| Gate | Requirement |
|------|-------------|
| Input SHA-256 | Frozen for \(I_0\), empty-BG, model weights (e.g. Siax `4x_NMKD-Siax_200k.pth`) |
| Bit-exact return | Where contract says lossless hardpaste: pixel identity on non-elevated regions / locate card |
| Zero ghosting | Automated ghost metric + visual board; fail if double-exposure edges |
| Coverage | All locked HR mask pixels explained by some tile core or explicit omit |
| Hierarchy mutex | Sibling parts at same layer do not claim the same pixel without occlusion record |
| Adapter proof | Inference log shows real backend id + seed/params |

---

## 8. Module map (research → intended production)

| Concern | Research fossil (`research/shq_v9/`) | Intended UP-engine home (sibling PRs) |
|---------|--------------------------------------|----------------------------------------|
| Orchestrator / boards | `shq_v2_self_consistent_engine.py` (`run_v9_full_pipeline`) | Engine runner / studio boards (bootstrap #1, REF router #5) |
| Whole-part / reverse mask / DNA / 3D·5D contracts | `shq_object_extractor.py` | READ + geometry contracts (#2, #3) |
| Guided return / hardpaste / L3→L2 | `shq_recursive_layer_return.py` | Pixel-safe reconstruction (#3), geometry-locked tiles (#11) |
| Real 4× inference | *(missing / faked in early share)* | Siax runners (#7, #9), DDXX/Comfy (#10), PBI (#6) |

**This PR does not wire fossils into `src/ige`.** It freezes the **program guidance** so those PRs converge on the same gates.

---

## 9. Suggested interfaces (for implementers)

Sketch only — names may match existing contracts on feature branches.

```text
freeze_base(image) -> BaseRecord                 # sha256, WxH, color
read_objects(base, empty_bg?) -> ObjectGraph     # hierarchy + silhouettes
lock_geometry(graph, G) -> GeometryLock          # HR masks, corners, DNA
plan_tiles(lock, tile_size, context) -> TilePlan # core/halo, coverage
infer_tiles(plan, backend) -> TileCores          # real Siax/gen only
elevate_whole_part(edge, donor) -> LayerRGBA     # EDGE→WHOLE
locate_layer(layer, lock) -> Placement           # 4-corner or 5D id
return_to_master(layers, placements) -> MasterHR # RETURN hardpaste
accept(master, lock, plan, provenance) -> Report # fail-closed JSON
```

CLIPPING MASK REVERSE helper:

```text
empty_bg = native_edit_remove_subjects(scene)    # Gemini-class edit, not inpaint hack
mask = reverse_clip(scene, empty_bg)             # regenerate all donors if this changes
```

---

## 10. Relation to open hub work

Treat as **siblings**, not duplicates:

- Spatial / geometry contracts: PR **#3**  
- Geometry-locked generative tiles: PR **#11**  
- Siax execution / multi-view / PBI: PRs **#7, #9, #10, #6**  
- READ / adapters: PRs **#2, #4, #5**  
- Bootstrap: PR **#1**

When implementing, cite this doc’s stage ids (`S0`–`S6`) and forbidden list in PR descriptions.

---

## 11. v0.1 acceptance for *this documentation PR*

- [x] Guidance stages + gates written  
- [x] Forbidden practices explicit  
- [x] Source transcript + EXTRACT provenance committed  
- [x] `research/shq_v9` fossils + README (not production-wired)  
- [ ] Runtime wiring into `src/ige` — **out of scope**  
- [ ] Real Siax backend proof in CI — **belongs to runner PRs**
