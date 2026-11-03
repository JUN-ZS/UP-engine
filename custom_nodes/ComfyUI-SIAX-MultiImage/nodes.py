from __future__ import annotations

import json
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from ige.registration import register_multiview, warp_image_to_canvas


IMAGE_SLOTS = tuple(f"image_{index}" for index in range(8))


def _comfy_image_to_rgb_array(value: Any, image_id: str) -> np.ndarray:
    if not hasattr(value, "detach"):
        raise TypeError(f"{image_id} must be a ComfyUI IMAGE tensor")
    array = value.detach().to("cpu").numpy()
    if not np.isfinite(array).all():
        raise ValueError(f"{image_id} contains NaN or infinite tensor values")
    if array.ndim != 4 or array.shape[0] != 1 or array.shape[-1] not in (3, 4):
        raise ValueError(f"{image_id} must be one RGB/RGBA image with shape [1,H,W,C]")
    rgb = array[0, :, :, :3]
    if np.issubdtype(rgb.dtype, np.floating):
        rgb = np.clip(rgb, 0.0, 1.0) * 255.0
    return np.clip(rgb, 0, 255).astype(np.uint8)


def _comfy_image_to_pil(value: Any, image_id: str) -> Image.Image:
    return Image.fromarray(_comfy_image_to_rgb_array(value, image_id), mode="RGB")


def _pil_to_comfy_image(image: Image.Image):
    import torch
    array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(array.copy()).unsqueeze(0)


def _pil_mask_to_comfy_mask(mask: Image.Image):
    import torch
    array = np.asarray(mask.convert("L"), dtype=np.float32) / 255.0
    return torch.from_numpy(array.copy()).unsqueeze(0)


class SIAXMultiImageFeatureMatches:
    """Build candidate feature correspondences with mutual SIFT + RANSAC."""

    CATEGORY = "SIAX/Multi-Image Geometry"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("anchors_json", "feature_report_json")
    FUNCTION = "build_matches"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_0": ("IMAGE",),
                "image_1": ("IMAGE",),
                "matcher_backend": (["flann", "brute_force"], {"default": "flann"}),
                "max_features": ("INT", {"default": 5000, "min": 100, "max": 20000, "step": 100}),
                "ratio_threshold": ("FLOAT", {"default": 0.72, "min": 0.1, "max": 0.99, "step": 0.01}),
                "ransac_reprojection_px": ("FLOAT", {"default": 3.0, "min": 0.1, "max": 30.0, "step": 0.1}),
                "min_inliers": ("INT", {"default": 12, "min": 3, "max": 500, "step": 1}),
            },
            "optional": {f"image_{i}": ("IMAGE",) for i in range(2, 8)},
        }

    def build_matches(self, image_0, image_1, matcher_backend, max_features,
                      ratio_threshold, ransac_reprojection_px, min_inliers, **kwargs):
        from ige.registration.features import build_sift_match_graph
        images = {"image_0": _comfy_image_to_rgb_array(image_0, "image_0"),
                  "image_1": _comfy_image_to_rgb_array(image_1, "image_1")}
        for i in range(2, 8):
            tensor = kwargs.get(f"image_{i}")
            if tensor is not None:
                images[f"image_{i}"] = _comfy_image_to_rgb_array(tensor, f"image_{i}")
        payload = build_sift_match_graph(
            images, max_features=max_features, ratio_threshold=ratio_threshold,
            ransac_reprojection_px=ransac_reprojection_px, min_inliers=min_inliers,
            matcher_backend=matcher_backend,
        )
        report = {
            "schema_version": "siaux-feature-report/0.1",
            "provider": payload["correspondence_provider"],
            "matcher_backend": payload["matcher_backend"],
            "pair_diagnostics": payload["pair_diagnostics"],
            "candidate_edges": len(payload["matches"]),
            "limitations": payload["limitations"],
        }
        return (json.dumps(payload, ensure_ascii=False),
                json.dumps(report, ensure_ascii=False, indent=2))


class SIAXMultiImageGeometryRegistration:
    """Fit pair transforms and globally solve the image-pose graph."""

    CATEGORY = "SIAX/Multi-Image Geometry"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("transform_json", "registration_report_json")
    FUNCTION = "register"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_0": ("IMAGE",),
                "image_1": ("IMAGE",),
                "anchors_json": ("STRING", {"multiline": True, "default": "{}"}),
                "root_image_id": ("STRING", {"default": "image_0"}),
                "huber_px": ("FLOAT", {"default": 10.0, "min": 0.1, "max": 100.0, "step": 0.1}),
                "acceptance_threshold_px": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "max_canvas_megapixels": ("FLOAT", {"default": 100.0, "min": 1.0, "max": 400.0, "step": 1.0}),
                "allow_unverified_bridge_edges": ("BOOLEAN", {"default": False}),
            },
            "optional": {f"image_{i}": ("IMAGE",) for i in range(2, 8)},
        }

    def register(self, image_0, image_1, anchors_json, root_image_id, huber_px,
                 acceptance_threshold_px, max_canvas_megapixels,
                 allow_unverified_bridge_edges, **kwargs):
        tensors = {"image_0": image_0, "image_1": image_1}
        for i in range(2, 8):
            if kwargs.get(f"image_{i}") is not None:
                tensors[f"image_{i}"] = kwargs[f"image_{i}"]
        specs = []
        for image_id, tensor in tensors.items():
            array = _comfy_image_to_rgb_array(tensor, image_id)
            specs.append({"id": image_id, "width": int(array.shape[1]), "height": int(array.shape[0])})
        try:
            payload = json.loads(anchors_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"anchors_json is invalid JSON: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") not in {
            "siaux-multiview-anchors/1.0", "siaux-multiview-anchors/1.0-manual"
        }:
            raise ValueError("anchors_json schema_version must be siax-multiview-anchors/1.0")
        provided = {item["id"] for item in specs}
        referenced = {x for edge in payload.get("matches", [])
                      for x in (edge.get("image_a"), edge.get("image_b"))}
        if referenced - provided:
            raise ValueError(f"anchors_json references unconnected image ports: {sorted(referenced-provided)}")
        result = register_multiview(
            specs, payload.get("matches", []), root_image_id=root_image_id,
            huber_px=float(huber_px),
            acceptance_threshold_px=float(acceptance_threshold_px) if float(acceptance_threshold_px) > 0 else None,
            max_canvas_pixels=int(float(max_canvas_megapixels) * 1_000_000),
            allow_unverified_bridge_edges=bool(allow_unverified_bridge_edges),
        )
        report = {
            "schema_version": "siaux-registration-report/0.1",
            "status": "solved_candidate",
            "geometry_gate": result["geometry_gate"],
            "algorithm_id": result["algorithm_id"],
            "graph": result["graph"],
            "global_residual": result["global_residual"],
            "edge_reports": result["edge_reports"],
            "acceptance_threshold_px": result["acceptance_threshold_px"],
            "allow_unverified_bridge_edges": result["allow_unverified_bridge_edges"],
            "limitations": result["limitations"],
            "correspondence_provider": payload.get("correspondence_provider", "manual_semantic_or_visual_anchors"),
            "feature_pair_diagnostics": payload.get("pair_diagnostics", []),
        }
        return (json.dumps(result, ensure_ascii=False),
                json.dumps(report, ensure_ascii=False, indent=2))


class SIAXApplyGeometryTransform:
    """Apply one approved image-to-canvas transform; return its valid mask."""

    CATEGORY = "SIAX/Multi-Image Geometry"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("registered_image", "valid_mask")
    FUNCTION = "apply_transform"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "transform_json": ("STRING", {"default": "{}"}),
            "image_id": ("STRING", {"default": "image_0"}),
            "resample": (["bicubic", "bilinear", "lanczos", "nearest"], {"default": "bicubic"}),
        }}

    def apply_transform(self, image, transform_json, image_id, resample):
        source = _comfy_image_to_pil(image, image_id)
        registered, mask = warp_image_to_canvas(source, transform_json, image_id, resample=resample)
        return (_pil_to_comfy_image(registered), _pil_mask_to_comfy_mask(mask))


class SIAXMultiImageStitch:
    """Feather candidate layers and expose coverage/overlap masks separately."""

    CATEGORY = "SIAX/Multi-Image Geometry"
    RETURN_TYPES = ("IMAGE", "MASK", "MASK")
    RETURN_NAMES = ("composite_candidate", "coverage_mask", "overlap_mask")
    FUNCTION = "stitch"

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "image_0": ("IMAGE",), "mask_0": ("MASK",),
            "image_1": ("IMAGE",), "mask_1": ("MASK",),
            "feather_radius": ("INT", {"default": 24, "min": 0, "max": 256, "step": 1}),
        }
        optional = {}
        for i in range(2, 8):
            optional[f"image_{i}"] = ("IMAGE",)
            optional[f"mask_{i}"] = ("MASK",)
        return {"required": required, "optional": optional}

    def stitch(self, image_0, mask_0, image_1, mask_1, feather_radius, **kwargs):
        layers = [("image_0", image_0, mask_0), ("image_1", image_1, mask_1)]
        for i in range(2, 8):
            image, mask = kwargs.get(f"image_{i}"), kwargs.get(f"mask_{i}")
            if image is None and mask is None:
                continue
            if image is None or mask is None:
                raise ValueError(f"image_{i} and mask_{i} must be connected together")
            layers.append((f"image_{i}", image, mask))
        arrays, masks, expected_shape = [], [], None
        for image_id, image_tensor, mask_tensor in layers:
            rgb = _comfy_image_to_rgb_array(image_tensor, image_id).astype(np.float32) / 255.0
            mask = mask_tensor.detach().to("cpu").numpy()
            if mask.ndim != 3 or mask.shape[0] != 1:
                raise ValueError(f"{image_id} mask must have shape [1,H,W]")
            mask = np.clip(mask[0].astype(np.float32), 0.0, 1.0)
            if rgb.shape[:2] != mask.shape:
                raise ValueError(f"{image_id} image and mask dimensions differ")
            if expected_shape is None:
                expected_shape = rgb.shape[:2]
            elif rgb.shape[:2] != expected_shape:
                raise ValueError("all registered layers must share the same canvas dimensions")
            arrays.append(rgb)
            masks.append(mask)
        height, width = expected_shape
        sum_rgb = np.zeros((height, width, 3), dtype=np.float32)
        sum_weight = np.zeros((height, width), dtype=np.float32)
        coverage_count = np.zeros((height, width), dtype=np.uint8)
        for rgb, raw_mask in zip(arrays, masks):
            binary = (raw_mask > 0.05).astype(np.uint8)
            coverage_count += binary
            if feather_radius > 0:
                blurred = Image.fromarray((raw_mask*255.0+0.5).astype(np.uint8), mode="L").filter(
                    ImageFilter.GaussianBlur(radius=float(feather_radius))
                )
                weight = np.asarray(blurred, dtype=np.float32) / 255.0
            else:
                weight = raw_mask
            weight *= raw_mask
            sum_rgb += rgb * weight[:, :, None]
            sum_weight += weight
        composite = np.zeros_like(sum_rgb)
        valid = sum_weight > 1e-6
        composite[valid] = sum_rgb[valid] / sum_weight[valid, None]
        coverage = (coverage_count > 0).astype(np.float32)
        overlap = (coverage_count > 1).astype(np.float32)
        import torch
        return (
            torch.from_numpy(np.clip(composite, 0.0, 1.0).copy()).unsqueeze(0),
            torch.from_numpy(coverage.copy()).unsqueeze(0),
            torch.from_numpy(overlap.copy()).unsqueeze(0),
        )


class SIAXJSONReportPreview:
    """Show a JSON execution report in the ComfyUI output panel."""

    CATEGORY = "SIAX/Multi-Image Geometry"
    RETURN_TYPES = ()
    FUNCTION = "show_report"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"report_json": ("STRING", {"forceInput": True, "multiline": True})}}

    def show_report(self, report_json):
        try:
            text = json.dumps(json.loads(str(report_json)), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            text = str(report_json)
        return {"ui": {"text": [text]}}


NODE_CLASS_MAPPINGS = {
    "SIAXMultiImageFeatureMatches": SIAXMultiImageFeatureMatches,
    "SIAXMultiImageGeometryRegistration": SIAXMultiImageGeometryRegistration,
    "SIAXApplyGeometryTransform": SIAXApplyGeometryTransform,
    "SIAXMultiImageStitch": SIAXMultiImageStitch,
    "SIAXJSONReportPreview": SIAXJSONReportPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SIAXMultiImageFeatureMatches": "SIAX Multi-Image Feature Matches (SIFT/RANSAC)",
    "SIAXMultiImageGeometryRegistration": "SIAX Multi-Image Geometry Registration (DDXX Graph)",
    "SIAXApplyGeometryTransform": "SIAX Apply Geometry Transform",
    "SIAXMultiImageStitch": "SIAX Multi-Image Stitch (Feather Candidate)",
    "SIAXJSONReportPreview": "SIAX JSON Report Preview",
}
