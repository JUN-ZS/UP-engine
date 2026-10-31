"""xAI Grok Imagine adapter for constrained candidate generation.

Imagine produces unverified candidates only. It never:
- decides geometric correctness,
- expands editable regions on its own authority,
- overwrites BASE or the generation packet,
- grants final acceptance.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .base import GenerationRequest, GenerationResult
from .registration import assess_registration


class GrokImagineError(RuntimeError):
    """Grok Imagine request or persistence failed."""


@dataclass(frozen=True)
class ImagineGenerationArtifact:
    adapter_id: str
    model_id: str
    request_id: str | None
    prompt: str
    base_sha256: str
    candidate_path: str
    candidate_sha256: str
    candidate_width: int
    candidate_height: int
    base_width: int
    base_height: int
    latency_ms: float
    resolution_requested: str | None
    aspect_ratio_requested: str | None
    registration_quality: str
    registration_report: dict[str, Any]
    metadata_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "model_id": self.model_id,
            "request_id": self.request_id,
            "prompt": self.prompt,
            "base_sha256": self.base_sha256,
            "candidate_path": self.candidate_path,
            "candidate_sha256": self.candidate_sha256,
            "candidate_size": {
                "width": self.candidate_width,
                "height": self.candidate_height,
            },
            "base_size": {
                "width": self.base_width,
                "height": self.base_height,
            },
            "latency_ms": self.latency_ms,
            "resolution_requested": self.resolution_requested,
            "aspect_ratio_requested": self.aspect_ratio_requested,
            "registration_quality": self.registration_quality,
            "registration_report": self.registration_report,
            "metadata_path": self.metadata_path,
            "status": "unverified_candidate",
            "claims": {
                "pixel_aligned": False,
                "geometrically_validated": False,
                "pixel_preserving": False,
                "final_acceptance": False,
            },
            "limitations": [
                "Imagine free-text compliance is not a permission system.",
                "Protected-region preservation is enforced later by UP-engine compositor.",
                "Registration quality is measured separately and may be failed/pending.",
            ],
        }


class GrokImagineAdapter:
    """Generate/edit a candidate image from a generation packet + BASE reference.

    Environment:
      XAI_API_KEY — required
      XAI_IMAGINE_MODEL — optional, default grok-imagine-image-2.0
      XAI_API_BASE — optional, default https://api.x.ai/v1
    """

    adapter_id = "xai.grok.imagine"
    DEFAULT_MODEL_ID = "grok-imagine-image-2.0"
    DEFAULT_API_BASE = "https://api.x.ai/v1"
    EDITS_PATH = "/images/edits"

    def __init__(
        self,
        model_id: str | None = None,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout_seconds: float = 300.0,
        transport: Any | None = None,
    ) -> None:
        resolved_key = (api_key if api_key is not None else os.environ.get("XAI_API_KEY", "")).strip()
        if not resolved_key:
            raise GrokImagineError(
                "XAI_API_KEY is missing. Set the environment variable before running "
                "Grok Imagine. There is no silent success without a key."
            )
        env_model = os.environ.get("XAI_IMAGINE_MODEL", "").strip()
        self.model_id = (model_id or env_model or self.DEFAULT_MODEL_ID).strip()
        self.api_key = resolved_key
        self.api_base = (api_base or os.environ.get("XAI_API_BASE") or self.DEFAULT_API_BASE).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._transport = transport
        self.last_request_meta: dict[str, Any] = {}

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Protocol-compatible thin wrapper. Prefer generate_from_packet for full audit."""
        raise GrokImagineError(
            "Use generate_from_packet(...) for UP-engine constrained generation. "
            "The bare GenerationRequest path is intentionally not a free redesign API."
        )

    def generate_from_packet(
        self,
        packet_path: str | Path,
        base_image_path: str | Path,
        output_dir: str | Path,
        *,
        prompt: str | None = None,
        aspect_ratio: str | None = None,
        resolution: str = "2k",
        quality: str = "medium",
        overwrite: bool = False,
    ) -> ImagineGenerationArtifact:
        packet_file = Path(packet_path)
        base_path = Path(base_image_path)
        destination = Path(output_dir)
        if not packet_file.is_file():
            raise FileNotFoundError(packet_file)
        if not base_path.is_file():
            raise FileNotFoundError(base_path)
        if destination.exists() and not destination.is_dir():
            raise NotADirectoryError(destination)
        if destination.exists() and any(destination.iterdir()) and not overwrite:
            raise FileExistsError(f"output directory is not empty: {destination}")
        destination.mkdir(parents=True, exist_ok=True)

        packet = json.loads(packet_file.read_text(encoding="utf-8"))
        if packet.get("packet_version") != "0.1.0":
            raise GrokImagineError("unsupported generation packet version")
        base_spec = packet.get("base", {})
        expected_sha = base_spec.get("sha256")
        base_bytes = base_path.read_bytes()
        base_sha = hashlib.sha256(base_bytes).hexdigest()
        if expected_sha and base_sha != expected_sha:
            raise GrokImagineError("BASE SHA-256 does not match generation packet")

        with Image.open(base_path) as opened:
            base_image = ImageOps.exif_transpose(opened)
            base_w, base_h = base_image.size
        if base_spec.get("width") and int(base_spec["width"]) != base_w:
            raise GrokImagineError("BASE width does not match generation packet")
        if base_spec.get("height") and int(base_spec["height"]) != base_h:
            raise GrokImagineError("BASE height does not match generation packet")

        objective = str(packet.get("objective") or "").strip()
        if not objective and not (prompt and prompt.strip()):
            raise GrokImagineError("generation packet objective is empty and no prompt was supplied")

        geometry_locks = packet.get("geometry_locks", {})
        lock_relations = geometry_locks.get("relations", []) if isinstance(geometry_locks, dict) else []
        lock_text = _format_geometry_locks(lock_relations)
        targets = packet.get("targets", [])
        target_text = _format_targets(targets)
        protected_ids = []
        if isinstance(geometry_locks, dict):
            protected_ids = list(geometry_locks.get("protected_region_ids") or [])

        built_prompt = prompt.strip() if prompt and prompt.strip() else _default_constrained_prompt(
            objective=objective,
            target_text=target_text,
            protected_region_ids=protected_ids,
            geometry_lock_text=lock_text,
        )

        # Prefer matching BASE aspect if caller did not force one.
        ratio = aspect_ratio or _nearest_supported_aspect(base_w, base_h)
        mime, data_uri = _image_data_uri(base_path, base_bytes)
        payload = {
            "model": self.model_id,
            "prompt": built_prompt,
            "image": {"url": data_uri, "type": "image_url"},
            "response_format": "b64_json",
            "n": 1,
            "quality": quality,
            "resolution": resolution,
        }
        if ratio:
            payload["aspect_ratio"] = ratio

        started = time.perf_counter()
        response_body, response_headers = self._post_json(
            self.api_base + self.EDITS_PATH,
            payload,
        )
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        request_id = (
            response_headers.get("x-request-id")
            or response_headers.get("X-Request-Id")
            or response_body.get("id")
            or response_body.get("request_id")
        )
        image_b64 = _extract_b64_image(response_body)
        candidate_bytes = base64.b64decode(image_b64)
        candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
        candidate_path = destination / "candidate.png"
        # Always store PNG bytes after decode; reject empty payloads.
        if not candidate_bytes:
            raise GrokImagineError("Imagine returned empty image bytes")
        candidate_path.write_bytes(candidate_bytes)
        # Re-encode to PNG for stable lossless path if JPEG was returned.
        with Image.open(candidate_path) as opened:
            cand = ImageOps.exif_transpose(opened)
            cand_w, cand_h = cand.size
            if opened.format != "PNG":
                rgb = cand.convert("RGBA" if "A" in cand.getbands() else "RGB")
                rgb.save(candidate_path, format="PNG")
                candidate_bytes = candidate_path.read_bytes()
                candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()

        # Never overwrite BASE or packet.
        if candidate_path.resolve() in {base_path.resolve(), packet_file.resolve()}:
            raise GrokImagineError("candidate path collides with BASE or packet")

        registration = assess_registration(
            base_path,
            candidate_path,
            expected_base_sha256=base_sha,
        )
        meta_path = destination / "imagine_candidate.meta.json"
        artifact = ImagineGenerationArtifact(
            adapter_id=self.adapter_id,
            model_id=self.model_id,
            request_id=str(request_id) if request_id is not None else None,
            prompt=built_prompt,
            base_sha256=base_sha,
            candidate_path=str(candidate_path.resolve()),
            candidate_sha256=candidate_sha,
            candidate_width=cand_w,
            candidate_height=cand_h,
            base_width=base_w,
            base_height=base_h,
            latency_ms=latency_ms,
            resolution_requested=resolution,
            aspect_ratio_requested=ratio,
            registration_quality=registration.registration_quality,
            registration_report=registration.to_dict(),
            metadata_path=str(meta_path.resolve()),
        )
        meta_path.write_text(
            json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.last_request_meta = {
            "adapter_id": self.adapter_id,
            "model_id": self.model_id,
            "request_id": artifact.request_id,
            "latency_ms": latency_ms,
            "endpoint": self.api_base + self.EDITS_PATH,
            "registration_quality": registration.registration_quality,
            "candidate_sha256_prefix": candidate_sha[:12],
            "base_sha256_prefix": base_sha[:12],
        }
        return artifact

    def _post_json(self, url: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        if self._transport is not None:
            return self._transport(url, payload)
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "UP-engine-GrokImagine/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                headers = {k: v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            raise GrokImagineError(
                f"Grok Imagine HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise GrokImagineError(f"Grok Imagine network error: {exc.reason}") from exc
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise GrokImagineError("Grok Imagine returned non-JSON response body") from exc
        if not isinstance(parsed, dict):
            raise GrokImagineError("Grok Imagine response root must be an object")
        return parsed, headers


def _image_data_uri(path: Path, data: bytes) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"} or data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif suffix == ".png" or data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    else:
        # Re-encode unknown formats to PNG for API compatibility.
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            from io import BytesIO
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            data = buffer.getvalue()
            mime = "image/png"
    return mime, f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _extract_b64_image(body: dict[str, Any]) -> str:
    data = body.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            if isinstance(first.get("b64_json"), str) and first["b64_json"].strip():
                return first["b64_json"]
            # Some gateways may still return url only — refuse temporary-only success.
            if isinstance(first.get("url"), str) and first["url"].strip():
                raise GrokImagineError(
                    "Imagine returned a temporary URL without b64_json. "
                    "Request response_format=b64_json and persist image bytes."
                )
    raise GrokImagineError("Imagine response did not contain b64_json image data")


def _format_targets(targets: Any) -> str:
    if not isinstance(targets, list) or not targets:
        return "human-approved editable regions from generation packet"
    parts = []
    for item in targets:
        if not isinstance(item, dict):
            continue
        rid = item.get("region_id") or "?"
        label = item.get("label") or rid
        semantic = item.get("semantic_type") or "object"
        parts.append(f"{rid} ({label}, type={semantic})")
    return "; ".join(parts) if parts else "human-approved editable regions"


def _format_geometry_locks(relations: Any) -> str:
    if not isinstance(relations, list) or not relations:
        return "None supplied beyond the packet's protected-region complement."
    lines = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        lines.append(
            f"- {relation.get('subject_id')} {relation.get('predicate')} "
            f"{relation.get('object_id')}; evidence={relation.get('evidence') or relation.get('visual_evidence') or 'n/a'}"
        )
    return "\n".join(lines) if lines else "None."


def _default_constrained_prompt(
    *,
    objective: str,
    target_text: str,
    protected_region_ids: list[str],
    geometry_lock_text: str,
) -> str:
    protected = ", ".join(protected_region_ids) if protected_region_ids else "all non-target pixels"
    return f"""Use the supplied BASE image as the authoritative visual reference. This is a controlled image-editing task, NOT a free redesign.

TASK
* Objective: {objective}
* Editable regions: {target_text}
* Protected regions: {protected}
* Human-verified geometry constraints:
{geometry_lock_text}
* Required visual state: apply only the objective above.

STRICT PRESERVATION RULES
1. Preserve the original camera position, viewing angle, perspective, framing, and composition.
2. Preserve the identity, silhouette, topology, proportions, and material identity of every object unless the task explicitly authorizes a change.
3. Do not redesign, replace, duplicate, merge, remove, or invent objects.
4. Do not modify protected content intentionally. The final pixel-level protection will be enforced separately by the UP-engine compositor.
5. Do not treat uncertain or model-inferred relationships as confirmed geometry.
6. Do not introduce extra objects, decorative elements, text, labels, watermarks, borders, or a collage.
7. Return one full-frame candidate image. Do not return a contact sheet or multiple alternative designs.

GEOMETRY RULES
* Follow every human-verified geometry constraint exactly.
* Physical contact must occur only at the specified surfaces.
* Do not create false contact between nearby or crossing objects.
* Preserve rigid-object geometry. Do not bend, melt, stretch, fuse, or deform rigid parts.
* Do not change the camera to hide a geometry error.
* If a requested edit cannot be represented without violating a locked constraint, prioritize the locked constraint.

OUTPUT
* Produce a single candidate image for this request.
* Do not claim that the output is pixel-aligned, geometrically validated, or pixel-preserving.
* The output is an unverified candidate for UP-engine registration and audit.
"""


def _nearest_supported_aspect(width: int, height: int) -> str | None:
    if width <= 0 or height <= 0:
        return None
    value = width / float(height)
    # Supported ratios documented by xAI Imagine API (approx matches).
    candidates = {
        "1:1": 1.0,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "3:2": 3 / 2,
        "2:3": 2 / 3,
        "2:1": 2.0,
        "1:2": 0.5,
        "21:9": 21 / 9,
        "5:2": 2.5,
    }
    best = min(candidates.items(), key=lambda item: abs(item[1] - value))
    # If far from all named ratios, omit and let API auto-select.
    if abs(best[1] - value) / value > 0.08:
        return None
    return best[0]
