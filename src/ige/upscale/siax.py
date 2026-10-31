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


def allocate_output_canvas(width: int, height: int, scale: int = 4):
    """Allocate the final RGB uint8 canvas; avoid a full-resolution float32 output buffer."""
    if width < 1 or height < 1 or scale < 1:
        raise ValueError("canvas dimensions and scale must be positive")
    import numpy as np

    return np.empty((height * scale, width * scale, 3), dtype=np.uint8)


def run_siax_upscale(input_path: str | Path, checkpoint_path: str | Path, output_path: str | Path, *, tile_size: int = 128, tile_pad: int = 8, confirm_model_license_review: bool = False, device: str = "auto") -> dict[str, Any]:
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
    # A 4x RGB float32 canvas scales to ~331 MiB at 1792x1008 input.
    # Use the final uint8 RGB canvas instead; this is ~83 MiB and avoids a second
    # full-size float conversion during PNG encoding.
    output_canvas = allocate_output_canvas(w, h, scale=4)
    tile_count = 0
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
                patch = tile_out[0, :, cy0:cy1, cx0:cx1].permute(1, 2, 0).numpy()
                patch = np.clip(patch * 255.0 + 0.5, 0, 255).astype(np.uint8)
                output_canvas[y0 * 4:y1 * 4, x0 * 4:x1 * 4] = patch
                tile_count += 1
                del tile, tile_out, patch
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(output_canvas, "RGB").save(output, format="PNG", compress_level=3)
    metadata = {
        "upscale_version": "1.0", "model_id": MODEL_ID, "scale": 4,
        "architecture": architecture, "checkpoint_path": str(checkpoint.resolve()),
        "checkpoint_sha256": weight_sha, "checkpoint_source": MODEL_URL,
        "license_review": "user_confirmed", "input_path": str(source.resolve()),
        "input_sha256": file_sha256(source), "input_dimensions": {"width": w, "height": h},
        "output_path": str(output.resolve()), "output_sha256": file_sha256(output),
        "output_dimensions": {"width": w * 4, "height": h * 4},
        "runtime": {"torch": torch.__version__, "device": selected_device, "tile_size": tile_size, "tile_pad": tile_pad, "tile_count": tile_count, "output_canvas_dtype": "uint8", "output_canvas_bytes": int(output_canvas.nbytes)},
        "acceptance": "candidate_only",
        "limitations": ["Model inference does not prove identity, topology or perceptual quality.", "Checkpoint must be recognized as ESRGAN and expose exact 4x scale; otherwise it is rejected.", "The Hugging Face mirror labels its repository MIT; original upstream model terms still require user review."]
    }
    sidecar = output.with_suffix(".upscale.json")
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata | {"metadata_path": str(sidecar.resolve())}
