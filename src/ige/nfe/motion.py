from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MotionDelta:
    """C0.1 — allowed change for this step (not a full physics sim)."""

    phase: str
    static_lock: list[str] = field(default_factory=lambda: ["camera", "horizon", "ground_plane"])
    dynamic_allow: dict[str, str] = field(default_factory=dict)
    # e.g. {"hair": "small_wind_phase", "splash": "expand_slightly", "hammer": "sink_hair"}
    identity_lock: list[str] = field(default_factory=lambda: ["face", "armor_pattern", "body_pose_family"])
    max_global_flow_p50_hint: float = 2.0
    prompt_suffix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def scene_lock_prompt(self) -> str:
        dyn = ", ".join(f"{k}:{v}" for k, v in self.dynamic_allow.items()) or "micro_phase_only"
        return (
            "Same photoreal locked camera and composition as previous frame. "
            "Same woman identity, same golden mesh armor, same warhammer grip family. "
            f"Allowed motion only: {dyn}. "
            "Do not reframe, do not new shot, do not change body pose family. "
            "One continuous next still only. "
            + self.prompt_suffix
        ).strip()


class MotionCompiler:
    """Compile a simple phase index into MotionDelta."""

    PHASES = (
        "hold_micro_rain",
        "splash_expand",
        "hair_wind_left",
        "hammer_sink_hair",
        "splash_settle",
        "hair_wind_right",
    )

    def compile(self, t_index: int, phase_name: str | None = None) -> MotionDelta:
        name = phase_name or self.PHASES[t_index % len(self.PHASES)]
        table = {
            "hold_micro_rain": MotionDelta(name, dynamic_allow={"rain": "streak_phase", "sheen": "subtle"}),
            "splash_expand": MotionDelta(name, dynamic_allow={"splash": "expand_slightly", "droplets": "higher"}),
            "hair_wind_left": MotionDelta(name, dynamic_allow={"hair": "wind_left_small", "rain": "streak_phase"}),
            "hammer_sink_hair": MotionDelta(name, dynamic_allow={"hammer": "sink_hair", "ripples": "outward"}),
            "splash_settle": MotionDelta(name, dynamic_allow={"splash": "settle", "droplets": "fall"}),
            "hair_wind_right": MotionDelta(name, dynamic_allow={"hair": "wind_right_small", "rain": "streak_phase"}),
        }
        return table.get(name, MotionDelta(name, dynamic_allow={"micro": "phase"}))
