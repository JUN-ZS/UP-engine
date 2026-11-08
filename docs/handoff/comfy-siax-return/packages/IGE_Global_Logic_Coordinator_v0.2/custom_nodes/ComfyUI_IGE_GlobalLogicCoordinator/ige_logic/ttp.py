"""Reference-compatible adapter for Comfyui_TTP_Toolset's public tile outputs."""
from __future__ import annotations
import math
from .core import ContractError


def positions_from_ttp_tile_dimensions(width: int, height: int, tile_width: int, tile_height: int):
    """Mirror TTP_Image_Tile_Batch.calculate_step and row-major positions.

    Production nodes should prefer the actual POSITIONS output from TTP. This
    helper exists for offline replay/tests and verifies our coordinate adapter.
    """
    width,height,tile_width,tile_height=map(int,(width,height,tile_width,tile_height))
    if min(width,height,tile_width,tile_height)<=0: raise ContractError("Image and tile dimensions must be positive")
    def calculate_step(size, tile_size):
        if size<=tile_size: return 1,0
        num=(size+tile_size-1)//tile_size
        overlap=(num*tile_size-size)//(num-1)
        step=tile_size-overlap
        return num,step
    cols,step_x=calculate_step(width,tile_width)
    rows,step_y=calculate_step(height,tile_height)
    out=[]
    for y in range(rows):
        for x in range(cols):
            left=x*step_x; upper=y*step_y
            right=min(left+tile_width,width); lower=min(upper+tile_height,height)
            if right-left<tile_width: left=max(0,width-tile_width)
            if lower-upper<tile_height: upper=max(0,height-tile_height)
            out.append((left,upper,right,lower))
    return out,(cols,rows)
