from __future__ import annotations

import json
import os
import mimetypes
from io import BytesIO
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler, urlopen


class ComfyCloudError(RuntimeError):
    pass


class ComfyCloudHTTPError(ComfyCloudError):
    def __init__(self, status: int, endpoint: str, detail: str):
        super().__init__(f"Comfy Cloud HTTP {status} at {endpoint}: {detail}")
        self.status = status
        self.endpoint = endpoint
        self.detail = detail


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class ComfyCloudConfig:
    base_url: str = "https://cloud.comfy.org"
    api_key_env: str = "COMFY_CLOUD_API_KEY"
    timeout_seconds: float = 30.0
    user_agent: str = "UP-engine-SHQ-ComfyCloudAdapter/0.1"

    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise ComfyCloudError(
                f"missing Comfy Cloud API key; set environment variable {self.api_key_env}"
            )
        return key


class ComfyCloudClient:
    """Small stdlib-only Comfy Cloud client. Secrets never enter manifests or receipts."""

    def __init__(
        self,
        config: ComfyCloudConfig | None = None,
        *,
        opener: Any = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.config = config or ComfyCloudConfig()
        self.base_url = self.config.base_url.rstrip("/")
        self._opener = opener
        self._sleeper = sleeper
        self._monotonic = monotonic
        self._key: str | None = None

    def _auth(self) -> str:
        if self._key is None:
            self._key = self.config.api_key()
        return self._key

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
        accept: str = "application/json",
        timeout: float | None = None,
    ) -> tuple[int, Mapping[str, str], bytes]:
        url = self.base_url + endpoint
        headers = {
            "X-API-Key": self._auth(),
            "Accept": accept,
            "User-Agent": self.config.user_agent,
        }
        if content_type:
            headers["Content-Type"] = content_type
        request = Request(url, data=body, headers=headers, method=method.upper())
        try:
            opener = self._opener or build_opener()
            with opener.open(request, timeout=timeout or self.config.timeout_seconds) as response:
                return int(response.status), dict(response.headers.items()), response.read()
        except HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            raise ComfyCloudHTTPError(exc.code, endpoint, detail[:1000]) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ComfyCloudError(f"Comfy Cloud request failed at {endpoint}: {exc}") from exc

    def _json(self, method: str, endpoint: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        _, _, raw = self._request(
            method, endpoint, body=body,
            content_type="application/json" if body is not None else None,
        )
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ComfyCloudError(f"invalid JSON response from {endpoint}") from exc
        if not isinstance(value, (dict, list)):
            raise ComfyCloudError(f"unexpected JSON response type from {endpoint}")
        return value

    def health(self) -> dict[str, Any]:
        info = self._json("GET", "/api/object_info")
        if not isinstance(info, dict):
            raise ComfyCloudError("/api/object_info did not return a node map")
        features: dict[str, Any] = {}
        try:
            value = self._json("GET", "/api/features")
            if isinstance(value, dict):
                features = value
        except ComfyCloudError:
            # Feature flags are supplementary; object_info is the required control plane.
            features = {"status": "unavailable"}
        return {
            "status": "reachable",
            "node_count": len(info),
            "object_info": info,
            "features": features,
        }

    def list_model_folders(self) -> list[dict[str, Any]]:
        value = self._json("GET", "/api/experiment/models")
        if not isinstance(value, list):
            raise ComfyCloudError("/api/experiment/models did not return a list")
        return [x for x in value if isinstance(x, dict)]

    def list_models(self, folder: str) -> list[dict[str, Any]]:
        value = self._json("GET", f"/api/experiment/models/{quote(folder, safe='')}")
        if not isinstance(value, list):
            raise ComfyCloudError(f"model folder {folder!r} did not return a list")
        return [x for x in value if isinstance(x, dict)]

    def model_inventory(self) -> dict[str, Any]:
        folders = self.list_model_folders()
        inventory: dict[str, list[dict[str, Any]]] = {}
        for item in folders:
            name = item.get("name") or item.get("folder") or item.get("id")
            if not isinstance(name, str) or not name:
                continue
            try:
                inventory[name] = self.list_models(name)
            except ComfyCloudHTTPError as exc:
                if exc.status != 404:
                    raise
                inventory[name] = []
        return {"folders": folders, "models_by_folder": inventory}

    def upload_image(self, path: str | Path) -> dict[str, Any]:
        image_path = Path(path)
        if not image_path.is_file():
            raise ComfyCloudError(f"input image not found: {image_path}")
        boundary = "----UPEngine" + uuid.uuid4().hex
        filename = image_path.name.replace('"', "_").replace("\\r", "_").replace("\\n", "_")
        data = image_path.read_bytes()
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks = [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {media_type}\r\n\r\n".encode(),
            data,
            b"\r\n",
            f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\ninput\r\n'.encode(),
            f"--{boundary}--\r\n".encode(),
        ]
        # Cloud stores uploads content-addressably; subfolder/overwrite are not relied on.
        _, _, raw = self._request(
            "POST", "/api/upload/image", body=b"".join(chunks),
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ComfyCloudError("invalid image-upload response") from exc
        if not isinstance(result, dict) or not isinstance(result.get("name"), str):
            raise ComfyCloudError(f"unexpected image-upload response: {str(result)[:500]}")
        return result

    def submit_prompt(self, workflow: Mapping[str, Any]) -> str:
        result = self._json("POST", "/api/prompt", {"prompt": workflow})
        if not isinstance(result, dict):
            raise ComfyCloudError("prompt submission response is not an object")
        if result.get("error") or result.get("node_errors"):
            raise ComfyCloudError(
                "Comfy Cloud rejected workflow: "
                + json.dumps({"error": result.get("error"), "node_errors": result.get("node_errors")}, ensure_ascii=False)[:1500]
            )
        prompt_id = result.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyCloudError(f"prompt submission did not return prompt_id: {result}")
        return prompt_id

    def get_job(self, prompt_id: str) -> dict[str, Any]:
        result = self._json("GET", f"/api/jobs/{quote(prompt_id, safe='')}")
        if not isinstance(result, dict):
            raise ComfyCloudError("job detail response is not an object")
        return result

    def wait_for_job(
        self,
        prompt_id: str,
        *,
        timeout_seconds: float = 1800,
        poll_interval_seconds: float = 2.0,
    ) -> dict[str, Any]:
        if timeout_seconds <= 0 or poll_interval_seconds <= 0:
            raise ValueError("timeout and poll interval must be positive")
        start = self._monotonic()
        while True:
            job = self.get_job(prompt_id)
            status = str(job.get("status") or job.get("state") or "").lower()
            if status in {"completed", "success", "succeeded"}:
                return job
            if status in {"failed", "error", "cancelled", "canceled"}:
                raise ComfyCloudError(
                    f"Comfy Cloud job {prompt_id} ended with status={status}: "
                    f"{json.dumps(job.get('error') or job.get('messages') or {}, ensure_ascii=False)[:1500]}"
                )
            if self._monotonic() - start >= timeout_seconds:
                raise ComfyCloudError(f"Comfy Cloud job timed out after {timeout_seconds:.1f}s: {prompt_id}")
            self._sleeper(poll_interval_seconds)

    @staticmethod
    def collect_images(job: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Collect output images while preserving the originating SaveImage node ID."""
        found: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()

        def append_image(value: Mapping[str, Any], node_id: str | None) -> None:
            filename = value.get("filename") or value.get("name")
            if not isinstance(filename, str) or not filename:
                return
            subfolder = str(value.get("subfolder") or "")
            media_type = str(value.get("type") or "output")
            source_node = node_id or ""
            key = (source_node, filename, subfolder, media_type)
            if key in seen:
                return
            seen.add(key)
            found.append({
                "node_id": node_id,
                "filename": filename,
                "subfolder": subfolder,
                "type": media_type,
            })

        outputs = job.get("outputs")
        if isinstance(outputs, Mapping):
            for node_id, node_output in outputs.items():
                if not isinstance(node_output, Mapping):
                    continue
                images = node_output.get("images")
                if isinstance(images, list):
                    for item in images:
                        if isinstance(item, Mapping):
                            append_image(item, str(node_id))
            if found:
                return found

        # Compatibility fallback for history-style responses. Parent node identity
        # is intentionally unknown here; callers must not infer tile attribution.
        def visit(value: Any, under_outputs: bool = False) -> None:
            if isinstance(value, Mapping):
                is_image = isinstance(value.get("filename"), str) or isinstance(value.get("name"), str)
                if is_image and (under_outputs or str(value.get("type", "")).lower() == "output"):
                    append_image(value, None)
                for key, child in value.items():
                    visit(child, under_outputs or key == "outputs")
            elif isinstance(value, list):
                for child in value:
                    visit(child, under_outputs)

        visit(job)
        return found

    def download_output(self, output: Mapping[str, Any], destination: str | Path) -> dict[str, Any]:
        filename = output.get("filename")
        if not isinstance(filename, str) or not filename:
            raise ComfyCloudError("output record lacks filename")
        query = urlencode({
            "filename": filename,
            "subfolder": str(output.get("subfolder") or ""),
            "type": str(output.get("type") or "output"),
        })
        endpoint = f"/api/view?{query}"
        request = Request(
            self.base_url + endpoint,
            headers={"X-API-Key": self._auth(), "Accept": "*/*", "User-Agent": self.config.user_agent},
            method="GET",
        )
        no_redirect = build_opener(_NoRedirect())
        try:
            with no_redirect.open(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            if exc.code != 302:
                detail = exc.read(4096).decode("utf-8", errors="replace")
                raise ComfyCloudHTTPError(exc.code, endpoint, detail[:1000]) from exc
            location = exc.headers.get("Location")
            if not location:
                raise ComfyCloudError("Cloud /api/view returned a redirect without Location")
            # IMPORTANT: signed object-storage URL is fetched without forwarding the API key.
            try:
                with urlopen(Request(location, headers={"Accept": "*/*"}), timeout=self.config.timeout_seconds) as response:
                    raw = response.read()
            except (HTTPError, URLError, TimeoutError, OSError) as fetch_exc:
                raise ComfyCloudError(f"failed to fetch signed output URL: {fetch_exc}") from fetch_exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ComfyCloudError(f"failed to download output {filename}: {exc}") from exc
        if not raw:
            raise ComfyCloudError(f"empty output returned for {filename}")
        try:
            from PIL import Image
            with Image.open(BytesIO(raw)) as opened:
                image_format = opened.format
                image_size = opened.size
                opened.verify()
            if image_format not in {"PNG", "JPEG", "WEBP"}:
                raise ComfyCloudError(f"unexpected image format returned for {filename}: {image_format}")
        except ComfyCloudError:
            raise
        except Exception as exc:
            raise ComfyCloudError(f"Cloud output is not a decodable image ({filename}): {exc}") from exc
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        import hashlib
        digest = hashlib.sha256(raw).hexdigest()
        return {
            "path": str(path.resolve()), "size_bytes": len(raw), "sha256": digest,
            "source_file": filename, "image_format": image_format,
            "width": int(image_size[0]), "height": int(image_size[1]),
        }
