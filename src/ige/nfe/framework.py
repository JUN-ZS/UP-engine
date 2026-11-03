"""NFE ALL framework bolt — single import surface.

Wires:
  C0 TemporalState · C0.1 Motion · C0.2 Generator protocol
  C0.3 Validator · C0.4 Loop
  C1–C5 still_sequence (optional import)
  DDXX registration hooks (optional)
  STICK evolve pack
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .loop import NextFrameLoop, StepResult
from .motion import MotionCompiler, MotionDelta
from .state import FrameRef, TemporalState, sha256_file
from .validate import TemporalValidator, ValidationReport

ROOT = Path(__file__).resolve().parents[3]  # up-engine root

# --- Registry of callable tools (paths relative to repo) ---
TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "nfe_pilot": {
        "path": "tools/nfe_next_frame_pilot.py",
        "role": "C0 bootstrap/plan/accept/procedural",
        "slot": "C0-C0.4",
    },
    "nfe_one_click": {
        "path": "tools/nfe_one_click.py",
        "role": "one-click bootstrap+plan+stick+optional steps",
        "slot": "ORCH",
    },
    "still_sequence_f2f_kit": {
        "path": "tools/still_sequence_f2f_kit.py",
        "role": "C1-C5 FrameBank/Metrics/Layout/Encode/Report",
        "slot": "C1-C5",
    },
    "siax_next_frame_f2f_verify": {
        "path": "tools/siax_next_frame_f2f_verify.py",
        "role": "ordered-still F2F metrics + DDXX consecutive",
        "slot": "C0.3_ext",
    },
    "siax_cinema_frame_chain_verify": {
        "path": "tools/siax_cinema_frame_chain_verify.py",
        "role": "cinema chain verify (legacy research)",
        "slot": "RESEARCH",
    },
    "siax_self_gen_cinema_chain": {
        "path": "tools/siax_self_gen_cinema_chain.py",
        "role": "self-gen cinema chain (legacy)",
        "slot": "RESEARCH",
    },
    "siax_multiview_model_holdout": {
        "path": "tools/siax_multiview_model_holdout_compare.py",
        "role": "DDXX multiview holdout compare",
        "slot": "DDXX",
    },
}

MODULE_REGISTRY: dict[str, str] = {
    "ige.nfe.state": "C0 TemporalState / FrameRef",
    "ige.nfe.motion": "C0.1 MotionCompiler",
    "ige.nfe.validate": "C0.3 TemporalValidator",
    "ige.nfe.loop": "C0.4 NextFrameLoop Accept/Reject",
    "ige.nfe.framework": "ALL bolt + STICK + manifest",
    "ige.nfe.stick": "STICK evolve attach pack",
    "ige.registration.multiview": "DDXX multiview static geometry",
    "ige.registration.geometry_models": "Similarity/Homography/LocalMesh",
}

FORBIDDEN_AS_G = [
    "i2v",
    "image_to_video",
    "optical_flow_morph_as_generation",
    "spatial_extend_as_time",
]


@dataclass
class FrameworkManifest:
    format: str = "ige.nfe.framework_manifest"
    format_version: str = "0.2"
    formula: str = "F_{t+1}=G(F_t,F_{t-1},K,ΔS_t,C_t)"
    generator_G: str = "i2i_next_still_only"
    forbidden_as_G: list[str] = field(default_factory=lambda: list(FORBIDDEN_AS_G))
    tools: dict[str, Any] = field(default_factory=lambda: dict(TOOL_REGISTRY))
    modules: dict[str, str] = field(default_factory=lambda: dict(MODULE_REGISTRY))
    slots: list[str] = field(
        default_factory=lambda: [
            "C0",
            "C0.1",
            "C0.2",
            "C0.3",
            "C0.4",
            "C1",
            "C2",
            "C3",
            "C4",
            "C5",
            "STICK",
        ]
    )
    not_image_to_video: bool = True
    quality_qualified: bool = False
    final_acceptance: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_tool(name: str, root: Path | None = None) -> Path:
    root = root or ROOT
    if name not in TOOL_REGISTRY:
        raise KeyError(f"unknown tool {name}; known={list(TOOL_REGISTRY)}")
    p = root / TOOL_REGISTRY[name]["path"]
    if not p.exists():
        raise FileNotFoundError(str(p))
    return p


def bolt_check(root: Path | None = None) -> dict[str, Any]:
    """Fail-soft inventory of bolted paths."""
    root = root or ROOT
    tools = {}
    for k, meta in TOOL_REGISTRY.items():
        p = root / meta["path"]
        tools[k] = {"path": str(p), "exists": p.exists(), **{x: meta[x] for x in meta if x != "path"}}
    modules = {}
    for mod, role in MODULE_REGISTRY.items():
        try:
            __import__(mod)
            modules[mod] = {"importable": True, "role": role}
        except Exception as e:
            modules[mod] = {"importable": False, "role": role, "error": str(e)[:120]}
    core = ["nfe_pilot", "nfe_one_click", "still_sequence_f2f_kit", "siax_next_frame_f2f_verify"]
    core_ok = all(tools[c]["exists"] for c in core if c in tools)
    return {
        "format": "ige.nfe.bolt_check",
        "core_ok": core_ok,
        "tools": tools,
        "modules": modules,
        "forbidden_as_G": FORBIDDEN_AS_G,
        "not_image_to_video": True,
        "quality_qualified": False,
        "final_acceptance": False,
    }
