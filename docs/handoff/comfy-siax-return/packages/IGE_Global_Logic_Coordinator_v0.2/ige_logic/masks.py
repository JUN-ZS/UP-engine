from __future__ import annotations

import numpy as np
from .core import ACTIONS, ContractError


def _min_pool_to_shape(mask: np.ndarray, latent_hw: tuple[int, int]) -> tuple[np.ndarray, tuple[int, int]]:
    """Conservative image-mask -> latent-mask projection using actual VAE latent shape."""
    image_h, image_w = mask.shape
    latent_h, latent_w = map(int, latent_hw)
    if latent_h <= 0 or latent_w <= 0 or image_h % latent_h or image_w % latent_w:
        raise ContractError(
            f"Tile image {(image_w, image_h)} cannot map exactly to latent {(latent_w, latent_h)}; "
            "refusing to guess/interpolate the VAE mask transform"
        )
    scale_y, scale_x = image_h // latent_h, image_w // latent_w
    pooled = mask.reshape(latent_h, scale_y, latent_w, scale_x).min(axis=(1, 3))
    return pooled, (scale_x, scale_y)


def build_tile_noise_masks(
    subsets: dict,
    latent_shape: tuple[int, ...],
    refine_noise_weight: float = 1.0,
    guarded_refine_noise_weight: float = 0.25,
    generate_noise_weight: float = 1.0,
) -> tuple[np.ndarray, dict]:
    """Build per-tile ComfyUI MASKs using the *actual encoded latent dimensions*.

    latent_shape must be B,C,H,W from the VAEEncode output. This removes the
    assumption that every VAE is exactly 8x downsampled.

    ComfyUI's SetLatentNoiseMask attaches this BHW mask to the LATENT batch;
    SamplerCustomAdvanced consumes the optional latent `noise_mask`.

    Spatial semantics:
      PRESERVE / REJECT -> 0.0 (no denoising; pixel gate restores exact source after decode)
      REFINE            -> refine_noise_weight
      GENERATE          -> generate_noise_weight
      geometry_guard    -> guarded_refine_noise_weight, but only after both
                           geometry and source-coordinate registration are operator-confirmed.

    Reduction uses conservative min pooling: if any source pixel inside a latent
    cell is protected, that latent cell gets no more noise permission than the
    protected pixel. Boundary expansion is measured from the actual VAE scale.
    """
    if len(latent_shape) != 4:
        raise ContractError(f"Expected encoded LATENT samples shape B,C,H,W, got {latent_shape}")
    batch, _channels, latent_h, latent_w = map(int, latent_shape)
    if batch != len(subsets["tiles"]):
        raise ContractError(f"Latent batch {batch} != TTP subset count {len(subsets['tiles'])}")
    for name, value in {
        "refine_noise_weight": refine_noise_weight,
        "guarded_refine_noise_weight": guarded_refine_noise_weight,
        "generate_noise_weight": generate_noise_weight,
    }.items():
        if not np.isfinite(value) or not 0.0 <= float(value) <= 1.0:
            raise ContractError(f"{name} must be finite and within [0,1]")

    contract = subsets["contract"]
    geometry_guard_enabled = (
        contract.get("geometry_status") == "operator_confirmed"
        and contract.get("source_alignment_status") == "operator_confirmed"
    )

    masks = []
    counts = {name: 0 for name in ACTIONS}
    guarded_pixels = 0
    tile_reports = []
    latent_scales = []
    for entry in subsets["tiles"]:
        action = np.asarray(entry["action_map"], dtype=np.uint8)
        guard = np.asarray(entry["geometry_guard"], dtype=np.uint8) > 0
        if action.shape != guard.shape:
            raise ContractError("Tile action_map and geometry_guard dimensions differ")

        weight = np.zeros(action.shape, dtype=np.float32)
        refine = action == ACTIONS["REFINE"]
        generate = action == ACTIONS["GENERATE"]
        # PRESERVE, REJECT and unknown codes remain zero (fail closed).
        weight[refine] = float(refine_noise_weight)
        weight[generate] = float(generate_noise_weight)
        if geometry_guard_enabled:
            guarded = refine & guard
            weight[guarded] = np.minimum(weight[guarded], float(guarded_refine_noise_weight))
            guarded_pixels += int(guarded.sum())
        else:
            guarded = np.zeros_like(guard)

        pooled, scale_xy = _min_pool_to_shape(weight, (latent_h, latent_w))
        masks.append(pooled)
        latent_scales.append(scale_xy)
        for name, code in ACTIONS.items():
            counts[name] += int((action == code).sum())
        tile_reports.append({
            "tile_id": entry["task"]["tile_id"],
            "image_mask_hw": list(weight.shape),
            "latent_mask_hw": list(pooled.shape),
            "latent_scale_xy": list(scale_xy),
            "zero_noise_pixels_image_space": int((weight == 0).sum()),
            "guarded_refine_pixels_image_space": int(guarded.sum()),
            "latent_mask_min": float(pooled.min()) if pooled.size else 0.0,
            "latent_mask_max": float(pooled.max()) if pooled.size else 0.0,
        })
    if len(set(latent_scales)) != 1:
        raise ContractError(f"Tile latent scales differ within one batch: {latent_scales}")

    batch_mask = np.stack(masks).astype(np.float32, copy=False)
    scale_x, scale_y = latent_scales[0]
    report = {
        "schema_version": "ige-tile-noise-mask/0.2",
        "contract_id": contract["contract_id"],
        "rules_digest": contract["rules_digest"],
        "tile_count": int(batch_mask.shape[0]),
        "latent_shape_bhw": [batch, latent_h, latent_w],
        "latent_scale_xy": [scale_x, scale_y],
        "action_pixel_counts": counts,
        "geometry_guard_enabled": bool(geometry_guard_enabled),
        "geometry_guard_disable_reason": None if geometry_guard_enabled else "geometry_or_source_alignment_not_operator_confirmed",
        "guarded_refine_pixels_image_space": int(guarded_pixels),
        "weights": {
            "preserve": 0.0,
            "reject": 0.0,
            "refine": float(refine_noise_weight),
            "guarded_refine": float(guarded_refine_noise_weight),
            "generate": float(generate_noise_weight),
        },
        "reduction": "conservative_min_pool_to_actual_vae_latent_shape",
        "boundary_expansion_max_xy_px": [scale_x - 1, scale_y - 1],
        "tiles": tile_reports,
        "non_claims": [
            "A noise mask limits/weights denoising; it does not prove silhouette or identity preservation.",
            "Exact PRESERVE/REJECT pixels must still be restored by the post-decode pixel gate.",
            "Geometry guard is inactive until both object geometry and source coordinate registration are operator-confirmed.",
        ],
    }
    return batch_mask, report
