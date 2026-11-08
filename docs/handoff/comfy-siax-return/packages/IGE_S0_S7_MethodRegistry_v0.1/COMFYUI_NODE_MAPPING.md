# ComfyUI Workflow Mapping — S0–S7 contract

This mapping refers to the node IDs in the workflow JSON pasted in the conversation. It is not a replacement workflow JSON and does not assume undocumented custom-node behavior.

| Existing node(s) | Current role | Correct contract stage | Required change / proof |
|---|---|---|---|
| 233 LoadImage | Source image | S0 | Freeze file SHA + decoded-pixel SHA, EXIF and colour profile before processing |
| 134 ImageUpscaleWithModel | 4x NMKD-Siax | S4/S5 | Capture checkpoint SHA, model ID, exact 4x output dimensions and runtime receipt |
| 34 ImageScaleToTotalPixels | 16MP delivery resize | S5/S6 transform boundary | Record explicit delivery transform; do not call its output an unmodified native 4x master |
| 111 TTP_Tile_image_size; 36 TTP_Image_Tile_Batch | Tile planner and metadata | S4 | Save actual `POSITIONS`, `ORIGINAL_SIZE`, `GRID_SIZE`, core/halo maps and coverage receipt |
| 77 UNETLoader; 78 DualCLIPLoader; 31 VAELoader | Flux stack | S5 | Fix widget-value/name mismatches; record model inventory, exact dtype and file SHA; no CC_V1/LoRA parity claim |
| 129 VAEEncode; 67 SamplerCustomAdvanced; 96 VAEDecodeTiled | A diffusion baseline | S5 | Save per-tile inputs, conditioning, sampler profile, seed, raw outputs and hashes |
| 300 IGE_GlobalLogicCompiler | Global contract + prompts | S2/S3/S4 | Compile geometry + permissions + method ID from registry; candidate observations cannot self-authorize |
| 301 IGE_TTPSubsetProjector | Contract to tile subsets | S4 | Verify each tile inherits global coordinate frame, approved/protected masks, guard, actions and parent digest |
| 308 IGE_TileNoiseMask; 309 SetLatentNoiseMask | Latent noise mask | S5 | Label as soft noise control only; produce per-tile mask stats and confirm exact batch ordering |
| 313 CLIPTextEncode; 314 FluxGuidance; 315 BasicGuider | One global B conditioning | S5 | This is not a per-subset Conditioning Router. Add one only after registry and compatibility grouping are implemented |
| 310 SamplerCustomAdvanced; 311 VAEDecodeTiled; 312 ImageListToImageBatch | B diffusion | S5 | Preserve raw decoded tile candidates before gates; receipt each tile separately |
| 302 IGE_ApplyLogicGate | Candidate tile gate | S6 | Feed explicit approved/protected permission masks; verify no auto-derived mask creates its own permission |
| 303 IGE_GlobalReconciler | Global reconcile | S6 | Enforce write-core-only semantics; no halo writes, no feather to conceal geometry drift |
| 127 TTP_Image_Assy | A assembly | S6 | Audit implementation; `padding=125` alone does not prove disjoint core-only return |
| 304 IGE_GlobalAcceptanceAudit | Candidate audit | S7 | Require complete observations, masks, geometry and source hashes; empty `{}` must BLOCK acceptance |
| 305 IGE_IterationFeedback | Next-state compiler | S7/S0 next run | Persist next state atomically, hash it, and load it on next run; currently output is not wired to storage |
| 306 IGE_LogicMapPreview; 307 SaveImage | Visual/debug outputs | Diagnostic | Save logic map and audit boards as evidence; preview is never acceptance |

## Graph-level corrections required before RUN

1. Synchronize node 77 `widgets_values` and `widgets_values_named` to `flux1-dev.safetensors`; synchronize node 31 to `ae.safetensors`. Confirm the serialized API prompt uses these same values.
2. Prove whether node 300's `GLOBAL_ACTION_MAP` and `GEOMETRY_GUARD` are embedded in `GLOBAL_CONTRACT`. If not, wire them explicitly into node 301 and all downstream subset consumers.
3. Add an S3 Permission Compiler output to the contract: `approved_edit_mask` and `protected_preserve_mask`, bound to source SHA and coordinate frame.
4. Make node 304 reject missing/empty observations and any non-human-verified geometry where the gate requires human verification.
5. Save per-tile backend receipts and raw outputs before any Gate/Assembly/Reconciler modifies them.
6. Add a core coverage ledger. For each authorized pixel: exactly one core writer, or an explicit `omit_reason`. Halo never writes.
7. Persist node 305 output to a versioned state file and reload it in node 300. A constant `{}` is not cross-run memory.
8. Do not claim shared noise from one seed. The current graph does not show a coordinate-indexed global noise tensor or per-subset synchronized denoising.

## Required tile record (minimum)

```json
{
  "tile_id": "tile_r_c",
  "contract_id": "sha256:...",
  "parent_state_sha256": "...",
  "global_canvas_wh": [0, 0],
  "read_window_xyxy": [0, 0, 0, 0],
  "write_core_xyxy": [0, 0, 0, 0],
  "halo_xyxy": [0, 0, 0, 0],
  "geometry_digest": "...",
  "permission_digest": "...",
  "method_id": "FLUX_HR_TILE_IMG2IMG",
  "conditioning_group_id": "global_or_group_id",
  "seed": 0,
  "backend_receipt_id": "...",
  "input_sha256": "...",
  "raw_output_sha256": "..."
}
```

The above is a contract example. It is not emitted by the current workflow until implemented.
