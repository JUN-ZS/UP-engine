from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskType(StrEnum):
    NEW_IMAGE = "new_image"
    EDIT = "edit"
    RETEXTURE = "retexture"
    UPSCALE = "upscale"
    TEMPORAL = "temporal"


class AssetRole(StrEnum):
    BASE = "base"
    IDENTITY_REFERENCE = "identity_reference"
    POSE_REFERENCE = "pose_reference"
    GEOMETRY_REFERENCE = "geometry_reference"
    GARMENT_DONOR = "garment_donor"
    MATERIAL_SWATCH = "material_swatch"
    CONTEXT_REFERENCE = "context_reference"
    OUTPUT_CANDIDATE = "output_candidate"


@dataclass(frozen=True)
class AssetRef:
    asset_id: str
    role: AssetRole
    uri: str
    sha256: str | None = None
    width: int | None = None
    height: int | None = None

    def validate(self) -> None:
        if not self.asset_id.strip() or not self.uri.strip():
            raise ValueError("asset_id and uri must be non-empty")
        if (self.width is None) != (self.height is None):
            raise ValueError("width and height must be supplied together")
        if self.width is not None and (self.width <= 0 or self.height <= 0):
            raise ValueError("image dimensions must be positive")
        if self.sha256 is not None and len(self.sha256) != 64:
            raise ValueError("sha256 must contain 64 hexadecimal characters")


@dataclass(frozen=True)
class Invariants:
    identity_locked: bool = True
    pose_locked: bool = True
    topology_locked: bool = True
    protected_regions: tuple[str, ...] = ()
    allowed_regions: tuple[str, ...] = ()
    expected_part_counts: dict[str, int] = field(default_factory=dict)

    def validate(self) -> None:
        if self.identity_locked and "identity_reference" not in self.protected_regions:
            # The semantic lock may be expressed through a reference asset instead;
            # this check only rejects an entirely unrecorded protected area.
            if not self.protected_regions:
                raise ValueError("identity lock requires at least one protected region")
        if any(v < 0 for v in self.expected_part_counts.values()):
            raise ValueError("expected part counts cannot be negative")
        if set(self.allowed_regions) & set(self.protected_regions):
            raise ValueError("a region cannot be both allowed and protected")


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    task_type: TaskType
    objective: str
    assets: tuple[AssetRef, ...]
    invariants: Invariants
    target_regions: tuple[str, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.task_id.strip() or not self.objective.strip():
            raise ValueError("task_id and objective must be non-empty")
        for asset in self.assets:
            asset.validate()
        roles = {asset.role for asset in self.assets}
        if self.task_type != TaskType.NEW_IMAGE and AssetRole.BASE not in roles:
            raise ValueError("non-new-image tasks require a BASE asset")
        if self.task_type == TaskType.RETEXTURE and not (
            AssetRole.MATERIAL_SWATCH in roles or AssetRole.GARMENT_DONOR in roles
        ):
            raise ValueError("retexture tasks require a MATERIAL_SWATCH or GARMENT_DONOR")
        self.invariants.validate()
        if self.target_regions and self.invariants.protected_regions:
            overlap = set(self.target_regions) & set(self.invariants.protected_regions)
            if overlap:
                raise ValueError(f"target regions overlap protected regions: {sorted(overlap)}")
