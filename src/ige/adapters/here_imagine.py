"""HERE Grok Imagine primary generation path.

Primary candidate generation is performed by the Grok agent session (HERE)
using Grok Imagine tools against the BASE reference and the constrained prompt
exported from a generation packet.

This adapter:
1. prepares an Imagine job package (prompt + hashes + instructions), and/or
2. ingests a HERE-produced candidate image into UP-engine audit layout.

It never:
- calls the remote xAI Images API (that is the secondary backend),
- claims geometric validation or pixel preservation,
- overwrites BASE or the generation packet,
- promotes candidates to final acceptance.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .imagine_prompt import nearest_supported_aspect, prompt_from_packet
from .registration import assess_registration


class HereImagineError(RuntimeError):
    """HERE Imagine prepare/ingest path failed."""


@dataclass(frozen=True)
class HereImagineJob:
    adapter_id: str
    backend: str
    model_id: str
    status: str
    prompt: str
    base_path: str
    base_sha256: str
    base_width: int
    base_height: int
    aspect_ratio_hint: str | None
    packet_path: str
    packet_sha256: str
    job_path: str
    prompt_path: str
    instructions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "backend": self.backend,
            "model_id": self.model_id,
            "status": self.status,
            "prompt": self.prompt,
            "base": {
                "path": self.base_path,
                "sha256": self.base_sha256,
                "width": self.base_width,
                "height": self.base_height,
            },
            "aspect_ratio_hint": self.aspect_ratio_hint,
            "packet_path": self.packet_path,
            "packet_sha256": self.packet_sha256,
            "job_path": self.job_path,
            "prompt_path": self.prompt_path,
            "instructions": list(self.instructions),
            "claims": {
                "generated": False,
                "pixel_aligned": False,
                "geometrically_validated": False,
                "pixel_preserving": False,
                "final_acceptance": False,
            },
            "limitations": [
                "HERE job package is not a completed generation.",
                "Grok Imagine tool output remains an unverified candidate.",
                "Protected-region preservation is enforced later by UP-engine compositor.",
                "Registration quality is measured only after ingest-candidate.",
            ],
        }


@dataclass(frozen=True)
class HereImagineArtifact:
    adapter_id: str
    backend: str
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
    registration_quality: str
    registration_report: dict[str, Any]
    metadata_path: str
    source_candidate_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "backend": self.backend,
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
            "registration_quality": self.registration_quality,
            "registration_report": self.registration_report,
            "metadata_path": self.metadata_path,
            "source_candidate_path": self.source_candidate_path,
            "status": "unverified_candidate",
            "claims": {
                "pixel_aligned": False,
                "geometrically_validated": False,
                "pixel_preserving": False,
                "final_acceptance": False,
            },
            "limitations": [
                "HERE Imagine free-text compliance is not a permission system.",
                "Protected-region preservation is enforced later by UP-engine compositor.",
                "Registration quality may be pending or failed; mismatch blocks composite.",
            ],
        }


class HereImagineAdapter:
    """Primary candidate path: prepare HERE job and/or ingest HERE candidate files."""

    adapter_id = "grok.imagine.here"
    backend = "here"
    DEFAULT_MODEL_ID = "grok-imagine-here"

    def __init__(self, model_id: str | None = None) -> None:
        self.model_id = (model_id or self.DEFAULT_MODEL_ID).strip() or self.DEFAULT_MODEL_ID

    def prepare_job(
        self,
        packet_path: str | Path,
        base_image_path: str | Path,
        output_dir: str | Path,
        *,
        prompt: str | None = None,
        aspect_ratio: str | None = None,
        overwrite: bool = False,
    ) -> HereImagineJob:
        packet_file, base_path, destination, packet, base_sha, base_w, base_h = _load_packet_and_base(
            packet_path, base_image_path, output_dir, overwrite=overwrite
        )
        built_prompt = prompt_from_packet(packet, prompt_override=prompt)
        ratio = aspect_ratio or nearest_supported_aspect(base_w, base_h)
        packet_sha = _sha256(packet_file)

        prompt_path = destination / "imagine_prompt.txt"
        job_path = destination / "imagine_job.json"
        prompt_path.write_text(built_prompt + "\n", encoding="utf-8")

        instructions = (
            "Primary generation backend is HERE (Grok agent session + Grok Imagine tools).",
            "Use the BASE image as the sole visual reference for image-to-image / edit.",
            "Paste or load imagine_prompt.txt as the constrained edit prompt.",
            "Do not free-redesign; do not expand editable regions on model authority.",
            "Save one full-frame candidate image, then run: ige generate-candidate ... --backend here --candidate <file>",
            "Or: ige accept-candidate <packet> <base> <candidate> --out <dir>",
            "Never overwrite BASE or generation_packet.json.",
            "Do not claim pixel-alignment, geometry validation, or final acceptance.",
        )
        job = HereImagineJob(
            adapter_id=self.adapter_id,
            backend=self.backend,
            model_id=self.model_id,
            status="awaiting_here_imagine_candidate",
            prompt=built_prompt,
            base_path=str(base_path.resolve()),
            base_sha256=base_sha,
            base_width=base_w,
            base_height=base_h,
            aspect_ratio_hint=ratio,
            packet_path=str(packet_file.resolve()),
            packet_sha256=packet_sha,
            job_path=str(job_path.resolve()),
            prompt_path=str(prompt_path.resolve()),
            instructions=instructions,
        )
        job_path.write_text(json.dumps(job.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Convenience copy of BASE path reference only — never mutate original BASE.
        ref_note = destination / "BASE_REFERENCE.txt"
        ref_note.write_text(
            f"BASE path: {base_path.resolve()}\n"
            f"BASE sha256: {base_sha}\n"
            f"BASE size: {base_w}x{base_h}\n"
            f"Do not overwrite this file's source image.\n",
            encoding="utf-8",
        )
        return job

    def ingest_candidate(
        self,
        packet_path: str | Path,
        base_image_path: str | Path,
        candidate_image_path: str | Path,
        output_dir: str | Path,
        *,
        prompt: str | None = None,
        request_id: str | None = None,
        overwrite: bool = False,
    ) -> HereImagineArtifact:
        packet_file, base_path, destination, packet, base_sha, base_w, base_h = _load_packet_and_base(
            packet_path, base_image_path, output_dir, overwrite=overwrite
        )
        source_candidate = Path(candidate_image_path)
        if not source_candidate.is_file():
            raise FileNotFoundError(source_candidate)
        if source_candidate.resolve() in {base_path.resolve(), packet_file.resolve()}:
            raise HereImagineError("candidate path collides with BASE or packet")

        built_prompt = prompt_from_packet(packet, prompt_override=prompt)
        # Also refresh job sidecar if missing so the prompt is auditable.
        prompt_path = destination / "imagine_prompt.txt"
        if not prompt_path.is_file() or overwrite:
            prompt_path.write_text(built_prompt + "\n", encoding="utf-8")

        candidate_path = destination / "candidate.png"
        if candidate_path.resolve() == source_candidate.resolve():
            # Already in place; still normalize to PNG below.
            pass
        else:
            if candidate_path.exists() and not overwrite:
                raise FileExistsError(candidate_path)
            shutil.copy2(source_candidate, candidate_path)

        with Image.open(candidate_path) as opened:
            cand = ImageOps.exif_transpose(opened)
            cand_w, cand_h = cand.size
            if opened.format != "PNG" or candidate_path.suffix.lower() != ".png":
                rgb = cand.convert("RGBA" if "A" in cand.getbands() else "RGB")
                rgb.save(candidate_path, format="PNG")
                with Image.open(candidate_path) as reopened:
                    cand_w, cand_h = ImageOps.exif_transpose(reopened).size

        candidate_sha = _sha256(candidate_path)
        registration = assess_registration(
            base_path,
            candidate_path,
            expected_base_sha256=base_sha,
        )
        meta_path = destination / "imagine_candidate.meta.json"
        artifact = HereImagineArtifact(
            adapter_id=self.adapter_id,
            backend=self.backend,
            model_id=self.model_id,
            request_id=request_id,
            prompt=built_prompt,
            base_sha256=base_sha,
            candidate_path=str(candidate_path.resolve()),
            candidate_sha256=candidate_sha,
            candidate_width=cand_w,
            candidate_height=cand_h,
            base_width=base_w,
            base_height=base_h,
            registration_quality=registration.registration_quality,
            registration_report=registration.to_dict(),
            metadata_path=str(meta_path.resolve()),
            source_candidate_path=str(source_candidate.resolve()),
        )
        meta_path.write_text(
            json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return artifact


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_packet_and_base(
    packet_path: str | Path,
    base_image_path: str | Path,
    output_dir: str | Path,
    *,
    overwrite: bool,
) -> tuple[Path, Path, Path, dict[str, Any], str, int, int]:
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
        raise HereImagineError("unsupported generation packet version")
    base_spec = packet.get("base", {})
    expected_sha = base_spec.get("sha256")
    base_sha = _sha256(base_path)
    if expected_sha and base_sha != expected_sha:
        raise HereImagineError("BASE SHA-256 does not match generation packet")

    with Image.open(base_path) as opened:
        base_image = ImageOps.exif_transpose(opened)
        base_w, base_h = base_image.size
    if base_spec.get("width") and int(base_spec["width"]) != base_w:
        raise HereImagineError("BASE width does not match generation packet")
    if base_spec.get("height") and int(base_spec["height"]) != base_h:
        raise HereImagineError("BASE height does not match generation packet")
    return packet_file, base_path, destination, packet, base_sha, base_w, base_h
