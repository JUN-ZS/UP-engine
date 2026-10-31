"""xAI Grok Vision adapter for UP-engine READ spatial proposals.

This provider replaces Qwen as the active READ visual reasoner path.
All outputs remain unreviewed model candidates and never grant geometry locks
or edit permission.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ..reasoner_prompt import REASONER_OUTPUT_SCHEMA_PROMPT
from ..reasoning import ReasoningProposalSet, parse_reasoning_response


class GrokVisionError(RuntimeError):
    """Grok Vision request failed or returned an unusable response."""


class GrokSpatialReasoner:
    """HTTP adapter for xAI Grok models that accept image input.

    Required environment:
      XAI_API_KEY — API bearer token (never logged or written to artifacts)

    Optional environment:
      XAI_VISION_MODEL — model ID with image understanding
                         default: grok-4
      XAI_API_BASE — override API host (default https://api.x.ai/v1)

    No silent fallback to Qwen or any other provider occurs.
    """

    provider_id = "xai.grok.vision"
    DEFAULT_MODEL_ID = "grok-4"
    DEFAULT_API_BASE = "https://api.x.ai/v1"
    RESPONSES_PATH = "/responses"

    def __init__(
        self,
        model_id: str | None = None,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        detail: str = "high",
        timeout_seconds: float = 180.0,
        transport: Any | None = None,
    ) -> None:
        resolved_key = (api_key if api_key is not None else os.environ.get("XAI_API_KEY", "")).strip()
        if not resolved_key:
            raise GrokVisionError(
                "XAI_API_KEY is missing. Set the environment variable before running "
                "Grok Vision READ. There is no silent fallback to Qwen."
            )
        env_model = os.environ.get("XAI_VISION_MODEL", "").strip()
        self.model_id = (model_id or env_model or self.DEFAULT_MODEL_ID).strip()
        if not self.model_id:
            raise GrokVisionError("Vision model ID is empty")
        self.api_key = resolved_key
        self.api_base = (api_base or os.environ.get("XAI_API_BASE") or self.DEFAULT_API_BASE).rstrip("/")
        if detail not in {"low", "high", "auto"}:
            raise ValueError("detail must be one of: low, high, auto")
        self.detail = detail
        self.timeout_seconds = timeout_seconds
        self._transport = transport  # optional injectable for unit tests
        self.last_request_meta: dict[str, Any] = {}

    def propose(
        self,
        image_path: str | Path,
        *,
        focus: str = "Inspect the whole image, including object parts, boundaries, contact and occlusion.",
    ) -> ReasoningProposalSet:
        source = Path(image_path)
        if not source.is_file():
            raise FileNotFoundError(source)
        image_bytes = source.read_bytes()
        if len(image_bytes) > 20 * 1024 * 1024:
            raise GrokVisionError("image exceeds xAI 20 MiB limit")
        mime = _guess_image_mime(source, image_bytes)
        data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        prompt = (
            f"Inspection focus: {focus.strip() or 'whole image'}\n\n"
            + REASONER_OUTPUT_SCHEMA_PROMPT
        )
        payload = {
            "model": self.model_id,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": data_uri,
                            "detail": self.detail,
                        },
                        {
                            "type": "input_text",
                            "text": prompt,
                        },
                    ],
                }
            ],
            # Avoid server-side history storage when images are present.
            "store": False,
        }
        started = time.perf_counter()
        response_body, response_headers = self._post_json(
            self.api_base + self.RESPONSES_PATH,
            payload,
        )
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        request_id = (
            response_headers.get("x-request-id")
            or response_headers.get("X-Request-Id")
            or response_body.get("id")
            or response_body.get("request_id")
        )
        text = _extract_response_text(response_body)
        self.last_request_meta = {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "request_id": request_id,
            "latency_ms": latency_ms,
            "detail": self.detail,
            "endpoint": self.api_base + self.RESPONSES_PATH,
            "status": "ok",
            # Never record API keys or image bytes.
            "image_sha256_prefix": _sha256_prefix(image_bytes),
            "image_bytes": len(image_bytes),
        }
        return parse_reasoning_response(
            text,
            provider_id=self.provider_id,
            model_id=self.model_id,
        )

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
                "User-Agent": "UP-engine-GrokVision/0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                headers = {k: v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            raise GrokVisionError(
                f"Grok Vision HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise GrokVisionError(f"Grok Vision network error: {exc.reason}") from exc
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise GrokVisionError("Grok Vision returned non-JSON response body") from exc
        if not isinstance(parsed, dict):
            raise GrokVisionError("Grok Vision response root must be an object")
        return parsed, headers


def _guess_image_mime(path: Path, data: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    raise GrokVisionError("xAI image understanding accepts only jpg/jpeg or png")


def _sha256_prefix(data: bytes, n: int = 12) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()[:n]


def _extract_response_text(body: dict[str, Any]) -> str:
    """Normalize Responses API / chat-style payloads into a single text string."""
    if isinstance(body.get("output_text"), str) and body["output_text"].strip():
        return body["output_text"]
    # Responses API: output -> content parts
    output = body.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                        chunks.append(part["text"])
                    elif isinstance(part.get("text"), str):
                        chunks.append(part["text"])
            elif isinstance(item.get("text"), str):
                chunks.append(item["text"])
        joined = "\n".join(part for part in chunks if part.strip())
        if joined.strip():
            return joined
    # Chat completions style fallback
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        parts.append(part["text"])
                if parts:
                    return "\n".join(parts)
    if isinstance(body.get("content"), str) and body["content"].strip():
        return body["content"]
    raise GrokVisionError("Grok Vision response did not contain extractable text content")
