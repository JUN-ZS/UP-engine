from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

MODEL_ID = "4x_NMKD-Siax_200k"
MODEL_SHA256 = "560424d9f68625713fc47e9e7289a98aabe1d744e1cd6a9ae5a35e9957fd127e"
MODEL_URL = "https://huggingface.co/uwg/upscaler/resolve/aadb8d07077a0818db0f43000b05442074b413be/ESRGAN/4x_NMKD-Siax_200k.pth"


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


sha256_file = file_sha256


def run_siax_upscale(input_path: str | Path, checkpoint_path: str | Path, output_path: str | Path, *, tile_size: int = 256, tile_pad: int = 16, confirm_model_license_review: bool = False, device: str = "auto", metal_mask_path: str | Path | None = None, apply_material_chroma_guard: bool = False, chroma_guard_feather: float = 1.5) -> dict[str, Any]:
    """Run the pinned 4x Siax model via Spandrel; never silently substitute a model."""
    source, checkpoint, output = Path(input_path), Path(checkpoint_path), Path(output_path)
    if not source.is_file() or not checkpoint.is_file():
        raise FileNotFoundError("input image or Siax checkpoint is missing")
    if output.suffix.lower() != ".png":
        raise ValueError("Siax master output must be lossless PNG")
    if tile_size < 32 or tile_pad < 0 or tile_pad >= tile_size:
        raise ValueError("tile_size must be >=32 and tile_pad must be in [0, tile_size)")
    if not confirm_model_license_review:
        raise PermissionError("review checkpoint provenance and license before enabling this model")
    weight_sha = file_sha256(checkpoint)
    if weight_sha != MODEL_SHA256:
        raise ValueError(f"checkpoint hash mismatch: expected {MODEL_SHA256}, got {weight_sha}")
    try:
        import numpy as np
        import torch
        from spandrel import ImageModelDescriptor, ModelLoader
    except ImportError as exc:
        raise RuntimeError("install the optional upscale extra to run Siax inference") from exc
    if device == "auto":
        selected_device = "cuda" if torch.cuda.is_available() else "cpu"
    elif device in {"cpu", "cuda"}:
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        selected_device = device
    else:
        raise ValueError("device must be auto, cpu or cuda")
    descriptor = ModelLoader(device=selected_device).load_from_file(str(checkpoint))
    if not isinstance(descriptor, ImageModelDescriptor):
        raise ValueError("checkpoint is not a supported image-to-image model")
    architecture = str(getattr(descriptor.architecture, "name", descriptor.architecture))
    if "esrgan" not in architecture.lower():
        raise ValueError(f"unexpected Siax architecture: {architecture}")
    if int(descriptor.scale) != 4:
        raise ValueError(f"expected a 4x Siax model, detected scale={descriptor.scale}")
    descriptor.eval()
    with Image.open(source) as opened:
        base = ImageOps.exif_transpose(opened).convert("RGB")
    array = np.asarray(base, dtype=np.float32).copy() / 255.0
    tensor = torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(selected_device)
    h, w = int(tensor.shape[-2]), int(tensor.shape[-1])
    result = torch.empty((1, 3, h * 4, w * 4), dtype=torch.float32, device="cpu")
    with torch.inference_mode():
        for y0 in range(0, h, tile_size):
            y1 = min(y0 + tile_size, h)
            for x0 in range(0, w, tile_size):
                x1 = min(x0 + tile_size, w)
                ey0, ey1 = max(0, y0 - tile_pad), min(h, y1 + tile_pad)
                ex0, ex1 = max(0, x0 - tile_pad), min(w, x1 + tile_pad)
                tile = tensor[:, :, ey0:ey1, ex0:ex1]
                tile_out = descriptor(tile).float().cpu()
                cy0, cx0 = (y0 - ey0) * 4, (x0 - ex0) * 4
                cy1, cx1 = cy0 + (y1 - y0) * 4, cx0 + (x1 - x0) * 4
                result[:, :, y0 * 4:y1 * 4, x0 * 4:x1 * 4] = tile_out[:, :, cy0:cy1, cx0:cx1]
    output_array = result.squeeze(0).clamp(0, 1).permute(1, 2, 0).numpy()
    chroma_guard_meta = None
    if apply_material_chroma_guard:
        if metal_mask_path is None:
            raise ValueError("apply_material_chroma_guard requires metal_mask_path at 4x or base size")
        from .material_chroma_guard import apply_material_chroma_guard as _guard
        import numpy as _np
        sr_u8 = (output_array * 255 + 0.5).astype("uint8")
        lp_u8 = _np.asarray(base.resize((w * 4, h * 4), Image.Resampling.LANCZOS), dtype="uint8")
        mask_path = Path(metal_mask_path)
        if not mask_path.is_file():
            raise FileNotFoundError(mask_path)
        with Image.open(mask_path) as mo:
            mask_im = ImageOps.exif_transpose(mo).convert("L")
        if mask_im.size == (w, h):
            mask_im = mask_im.resize((w * 4, h * 4), Image.Resampling.NEAREST)
        elif mask_im.size != (w * 4, h * 4):
            raise ValueError(f"metal mask size must be base or 4x, got {mask_im.size}")
        mask = _np.asarray(mask_im, dtype=_np.float32) / 255.0
        guarded, chroma_guard_meta = _guard(lp_u8, sr_u8, mask, feather=chroma_guard_feather)
        # keep raw SR diagnostic next to master when guard applied
        raw_path = output.with_name(output.stem + "_RAW_SR.png")
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(sr_u8, "RGB").save(raw_path, format="PNG")
        output_array = guarded.astype("float32") / 255.0
        chroma_guard_meta["raw_sr_path"] = str(raw_path.resolve())
        chroma_guard_meta["policy"] = "PREVENT_BLUE_INJECTION · C(LP)*Y(SR) on metal"
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((output_array * 255 + 0.5).astype("uint8"), "RGB").save(output, format="PNG")
    metadata = {
        "upscale_version": "1.0", "model_id": MODEL_ID, "scale": 4,
        "architecture": architecture, "checkpoint_path": str(checkpoint.resolve()),
        "checkpoint_sha256": weight_sha, "checkpoint_source": MODEL_URL,
        "license_review": "user_confirmed", "input_path": str(source.resolve()),
        "input_sha256": file_sha256(source), "input_dimensions": {"width": w, "height": h},
        "output_path": str(output.resolve()), "output_sha256": file_sha256(output),
        "output_dimensions": {"width": w * 4, "height": h * 4},
        "runtime": {"torch": torch.__version__, "device": selected_device, "tile_size": tile_size, "tile_pad": tile_pad},
        "acceptance": "candidate_only",
        "material_chroma_guard": chroma_guard_meta,
        "prevent_blue_injection": bool(apply_material_chroma_guard),
        "limitations": [
            "Model inference does not prove identity, topology or perceptual quality.",
            "Checkpoint must be recognized as ESRGAN and expose exact 4x scale; otherwise it is rejected.",
            "The Hugging Face mirror labels its repository MIT; original upstream model terms still require user review.",
            "Without apply_material_chroma_guard, full RGB SR may inject metal chroma noise (navy blotch); enable guard for silver/metal.",
        ]
    }
    sidecar = output.with_suffix(".upscale.json")
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata | {"metadata_path": str(sidecar.resolve())}
