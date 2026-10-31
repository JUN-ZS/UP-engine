"""PREVENT BLUE INJECTION (PBI) · material-aware chroma guard.

Goal: when generating 4×/HR pixels, do not inject wrong chroma into silver/metal mesh.
Post-hoc blue wash is NOT acceptance — this guard runs at synthesis time.

Core metal formula (linear-ish RGB, float 0–255):
    RGB_metal = C(LP) × Y(SR)
where C is chrominance of the locked parent/LP, Y is luminance from SR.

Applies to:
  1) SIAX 4× compose (optional metal mask + LP base)
  2) DETAIL6 metal residual (Y-only HF; no RGB chroma residual)
"""
from __future__ import annotations

from typing import Any

import numpy as np

EPS = 1e-3

# Rec.601-style luminance on RGB order (engine uses RGB, not BGR)
def to_y_rgb(rgb: np.ndarray) -> np.ndarray:
    f = rgb.astype(np.float32)
    return 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]


def chrom_rgb(rgb: np.ndarray, y: np.ndarray | None = None) -> np.ndarray:
    f = rgb.astype(np.float32)
    if y is None:
        y = to_y_rgb(f)
    return f / (y[..., None] + EPS)


def luma_only_compose(lp_rgb: np.ndarray, sr_rgb: np.ndarray) -> np.ndarray:
    """Full-frame: chrom from LP, Y from SR."""
    y_sr = to_y_rgb(sr_rgb)
    out = chrom_rgb(lp_rgb) * y_sr[..., None]
    return np.clip(out, 0, 255).astype(np.float32)


def apply_material_chroma_guard(
    lp_rgb: np.ndarray,
    sr_rgb: np.ndarray,
    metal_mask: np.ndarray,
    *,
    feather: float = 1.5,
    strength: float = 1.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Lock metal pixels to C(LP)×Y(SR); leave non-metal as SR.

    metal_mask: HxW float/bool in [0,1] at SR resolution.
    """
    if lp_rgb.shape != sr_rgb.shape:
        raise ValueError(f"lp and sr shape mismatch: {lp_rgb.shape} vs {sr_rgb.shape}")
    m = metal_mask.astype(np.float32)
    if m.ndim != 2 or m.shape != sr_rgb.shape[:2]:
        raise ValueError("metal_mask must be HxW matching sr")
    m = np.clip(m, 0, 1)
    if feather > 0:
        try:
            from PIL import Image, ImageFilter
            mf = Image.fromarray((m * 255).astype("uint8"), "L").filter(
                ImageFilter.GaussianBlur(radius=float(feather))
            )
            m = np.asarray(mf, dtype=np.float32) / 255.0
        except Exception:
            pass
    m = np.clip(m * float(strength), 0, 1)
    locked = luma_only_compose(lp_rgb, sr_rgb)
    sr_f = sr_rgb.astype(np.float32)
    out = sr_f * (1.0 - m[..., None]) + locked * m[..., None]
    out = np.clip(out, 0, 255)
    # diagnostics: mean |Δchrom| on metal (proxy for blue inject risk if using raw SR)
    y_sr = to_y_rgb(sr_f)
    chrom_sr = chrom_rgb(sr_f, y_sr)
    chrom_lp = chrom_rgb(lp_rgb)
    d = np.abs(chrom_sr - chrom_lp).mean(axis=2)
    metal_sel = m > 0.5
    meta = {
        "guard": "material_chroma_guard",
        "formula": "RGB_metal = C(LP) * Y(SR)",
        "metal_frac": float(m.mean()),
        "metal_pixels": int(metal_sel.sum()),
        "mean_abs_chrom_delta_sr_vs_lp_on_metal": float(d[metal_sel].mean()) if np.any(metal_sel) else 0.0,
        "feather": feather,
        "strength": strength,
    }
    return out, meta


def detail6_y_only_residual(
    source: np.ndarray,
    low: np.ndarray,
    metal_mask: np.ndarray,
    other_alpha: np.ndarray,
    *,
    gain: float,
) -> np.ndarray:
    """DETAIL6 synthesis with PREVENT BLUE INJECTION on metal.

    - metal: inject only Y high-frequency residual; chrom stays source chrom
    - non-metal detail alpha: keep RGB residual (stone/text/fire)
    source/low: float32 HxWx3 RGB 0–255
    metal_mask/other_alpha: HxW float 0–1 (already protected-cleared as needed)
    """
    src = source.astype(np.float32)
    lo = low.astype(np.float32)
    metal = np.clip(metal_mask.astype(np.float32), 0, 1)
    other = np.clip(other_alpha.astype(np.float32), 0, 1)
    # non-metal residual path
    res_rgb = src - lo
    out = src + res_rgb * (gain * other[..., None])
    # metal Y-only path
    y_src = to_y_rgb(src)
    y_lo = to_y_rgb(lo)
    dy = y_src - y_lo
    chrom = chrom_rgb(src, y_src)
    y_new = y_src + dy * (gain * metal)
    metal_out = chrom * y_new[..., None]
    mw = metal[..., None]
    out = out * (1.0 - mw) + metal_out * mw
    return np.clip(out, 0, 255)
