#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m21_geometry_locked_tile_plan_return.py
=======================================
[M21] GEOMETRY_LOCKED_TILE_PLAN_RETURN — 全局幾何分塊規劃與 Disjoint Write-Core 零疊影精確回位器
Category : cat05_s6_s7_geometry_locked_return_and_audit (分類 05：S6–S7 規則 01380 鎖幾何併回大圖與磁碟重讀反驗類)
Stage    : S2, S4, S6, S7

Summary:
  將 5504×3072 大圖切分為含 Halo 上下文之讀取塊 (Read Tile = Core + Halo)，寫回時嚴格裁除 Halo、僅寫入互斥且無縫拼接的 Write-Core，驗證 Core 重疊=0、缺口=0。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat05_s6_s7_geometry_locked_return_and_audit/m21_geometry_locked_tile_plan_return.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat05_s6_s7_geometry_locked_return_and_audit/m21_geometry_locked_tile_plan_return.py --part P08
  python methods/cat05_s6_s7_geometry_locked_return_and_audit/m21_geometry_locked_tile_plan_return.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M21 --part P08
  python invoke_method.py --run GEOMETRY_LOCKED_TILE_PLAN_RETURN --part B1_P08_GOLDMESH_CARBON_TORSO
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_PKG_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from methods.common_runtime import CANONICAL_18_PARTS, execute_core_role

METHOD_META: Dict[str, Any] = {
    "code": "M21",
    "slug": "m21_geometry_locked_tile_plan_return",
    "method_id": "GEOMETRY_LOCKED_TILE_PLAN_RETURN",
    "category": "cat05_s6_s7_geometry_locked_return_and_audit",
    "stage": [
        "S2",
        "S4",
        "S6",
        "S7"
    ],
    "title_zh": "全局幾何分塊規劃與 Disjoint Write-Core 零疊影精確回位器",
    "summary_zh": "將 5504×3072 大圖切分為含 Halo 上下文之讀取塊 (Read Tile = Core + Halo)，寫回時嚴格裁除 Halo、僅寫入互斥且無縫拼接的 Write-Core，驗證 Core 重疊=0、缺口=0。",
    "core_role": "TILE_PLAN_EXACT_CORE_RETURN"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M21] `GEOMETRY_LOCKED_TILE_PLAN_RETURN` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M21] GEOMETRY_LOCKED_TILE_PLAN_RETURN: 全局幾何分塊規劃與 Disjoint Write-Core 零疊影精確回位器"
    )
    parser.add_argument(
        "--part",
        type=str,
        default="B0_P02_TITANIUM_CHEST_CORE",
        help="Target self-part ID (e.g. P01..P18 or B0_P02_TITANIUM_CHEST_CORE)",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=0.45,
        help="Attenuation factor for HF detail rollback (used in M15 / Skill C3)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Optional directory for saving preview PNG and JSON receipt",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print method metadata and exit without running",
    )
    parser.add_argument(
        "--list-parts",
        action="store_true",
        help="List all 18 canonical battlefield self-parts",
    )
    args = parser.parse_args()

    if args.list_parts:
        for i, p in enumerate(CANONICAL_18_PARTS, 1):
            print(f"P{i:02d} -> {p}")
        return 0

    if args.info:
        print(json.dumps(METHOD_META, indent=2, ensure_ascii=False))
        return 0

    out_dir = Path(args.output_dir) if args.output_dir else None
    receipt = run_method(part_id=args.part, gamma=args.gamma, output_dir=out_dir)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt.get("status") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
