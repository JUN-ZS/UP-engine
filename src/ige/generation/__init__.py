"""Geometry-first high-resolution tiled generation primitives."""

from .geometry_tiles import (
    GeometryTileError,
    audit_tile_observations,
    plan_two_tile_generation,
    stitch_two_tile_cores,
)

__all__ = [
    "GeometryTileError",
    "audit_tile_observations",
    "plan_two_tile_generation",
    "stitch_two_tile_cores",
]
