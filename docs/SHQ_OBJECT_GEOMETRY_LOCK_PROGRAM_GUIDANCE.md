# SHQ Object Geometry Lock — Program Guidance v0.1

**Latest source conversation:** Gemini share `XMyk6HVn2J9S` → `381865631306` (**20 turns**)  
**Prior packs (kept):** `nutrRjsw676R` → `f5fb21d16408` (19); `hC9HlUpskKK9` → `49fb97a58dbe` (17); `47yxULPlPy0W` → `970343afbbef` (15)  
**Title:** 物件導向幾何約束升頻架構  
**Transcript (latest):** [`docs/sources/gemini-share-XMyk6HVn2J9S/Gemini-完整對話.md`](./sources/gemini-share-XMyk6HVn2J9S/Gemini-完整對話.md)  
**AI agent usage guide:** [`docs/SHQ_AI_USAGE_GUIDE.md`](./SHQ_AI_USAGE_GUIDE.md)  
**Research fossils:** [`research/shq_v9/`](../research/shq_v9/) (10 scripts; + battlefield self-part traceability)  
**Status:** implementer contract / design lock. Not a runtime merge.

**v0.1 refresh note:** packs through XMyk add (1) **Method Registry** + Skill Router / holdout, (2) **true generative 8K** donors, (3) **strict claim boundary** + anti-tautology + `delivery_transform`, (4) **Rule 01380** + four-skill frequency layers \(L+M+H\), (5) **battlefield self-part** chain 生/除/扣/洞/反 with **1:1 method→program→test→accept** traceability. Stage naming emphasizes **S7 independent ACCEPT**; this doc’s S0–S6 map still applies — cover freeze→read→lock→route→infer→return→independent accept.

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
| `delivery_transform` | Optional resample for delivery / preview only | **No** — never rewrite native `model_scale` provenance |

**Forbidden confusion:** increasing `-t` / tile size must **not** be treated as “make the object larger.”

**Forbidden claim:** a downsampled delivery plate must **not** be labeled “unmodified native 4×”; mark `delivery_resampled_…_NOT_unmodified_native_4x`.

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
10. **Rule 01380 violation:** leaving the hole border at low-res / eroding an `interior_core` / using feather to fake a correct edge. Every pixel **inside** \(M_{hole}\) is a legal upgrade site; freeze **boundary geometry**, not near-edge resolution.
11. **Tautological proofs:** `m_hole` vs `m_hole` IoU=1.0, or copying source alpha, sold as geometry lock evidence.
12. Auto-promoting `DIFF` masks to `edit_permission=True` without S3 human compile.
13. Method Registry / entrypoint / test / acceptance IDs that do **not** line up 1:1.
14. Claiming “master composed from self HR parts” without the full 生/除/扣/洞/反 + traceability table PASS.

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
| READ + Skill Router / Method Registry | `shq_read_and_skill_router.py`, `shq_5group_test_and_holdout_suite.py` | READ / REF router (#2, #5); failure memory ↔ registry |
| Hole / anti-debug audits (S7) | `shq_edit_hole_four_anti_debug.py` | Acceptance boards / strict CI gates |
| True generative 8K → locked return | `shq_all24_true_generative_upscale_return.py` | Geometry-locked tiles (#11) + real Siax/Comfy donors (#7, #9, #10) |
| Real 4× inference | *(early share faked; latest demo uses true AI donors — still wire production via runners)* | Siax runners (#7, #9), DDXX/Comfy (#10), PBI (#6) |

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
- [x] AI usage guide (`SHQ_AI_USAGE_GUIDE.md`)  
- [x] Latest source pack `hC9HlUpskKK9` (17 turns) + prior pack retained  
- [x] `research/shq_v9` fossils ×7 + README (not production-wired)  
- [ ] Runtime wiring into `src/ige` — **out of scope**  
- [ ] Real Siax backend proof in CI — **belongs to runner PRs**

---

## 10. Additive rules from nutr / XMyk packs (v0.1 refresh)

These do **not** replace §§0–9; they tighten acceptance language.

### 10.1 Rule 01380 — hole border is not a low-res protect zone

- \(M_{hole}\) marks **where RGB may change**; it does **not** prescribe the generative method.  
- Do **not** leave a low-res ring inside the hole (`eroded_low_res_border_pixels = 0`, `boundary_ring_upgraded_ratio = 1.0`, `feather_px = 0`).  
- Soft feather is **not** a substitute for a correct hard edge.

### 10.2 Frequency-layer composite

\[
\mathrm{RGB}_{\mathrm{final}} = L_{\mathrm{base}} + M_{\mathrm{material}} + H_{\mathrm{detail}}
\]

Layers must be independently controllable and rollback-able (attenuate \(H\) without blurring \(L\)/\(M\)). Map to skills A/B/C + guard D; demote `INPAINT` to optional hole-fill only.

### 10.3 Strict claim boundary

Publish **Verified Claims** vs **Explicit Non-Claims** in every S7 / traceability report. Disk re-read + SHA evidence required for any claim that a master is rebuilt from **self** HR parts.

### 10.4 1:1 method traceability (battlefield pattern)

For each stage, record the same quartet:

`method_id` → `entrypoint` → `test_id` → `acceptance_gate_id`

Reference fossil: `research/shq_v9/shq_battlefield_self_part_traceability_engine.py` (生/除/扣/洞 → self-part \(L+M+H\) → 01380 return → 反 / anti_diff).

### 10.5 Four-state edit evidence

Prefer the explicit chain **KEEP → REMOVE → DIFF → HOLE** (生/除/扣/洞) with `diff_grants_edit_permission = False` until S3 compiles permission. When a verified closed silhouette already exists, skipping REMOVE→DIFF is allowed only if recorded (`four_state_remove_diff_skipped_because_mask_verified=True`).
