#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m06_box_free_5d_locate_proxy.py
===============================
[M06] BOX_FREE_5D_LOCATE_PROXY — 無框 (Box-Free) 5D 測地線 UV 與球頂深度代理定位器
Category : cat02_s1_s2_part_read_and_5d_lock (分類 02：S1–S2 自身 18 部件流線拆解、無框 5D 定位與 4× 幾何鎖定類)
Stage    : S2, S6

Summary:
  由 2D 閉合部件剪影計算距離變換測地線 (u, v)、PCA 主軸角度 θ 與球頂深度/法線代理 (Normal/Depth Proxy)，輔助非矩形曲面結構對位。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat02_s1_s2_part_read_and_5d_lock/m06_box_free_5d_locate_proxy.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat02_s1_s2_part_read_and_5d_lock/m06_box_free_5d_locate_proxy.py --part P08
  python methods/cat02_s1_s2_part_read_and_5d_lock/m06_box_free_5d_locate_proxy.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M06 --part P08
  python invoke_method.py --run BOX_FREE_5D_LOCATE_PROXY --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M06",
    "slug": "m06_box_free_5d_locate_proxy",
    "method_id": "BOX_FREE_5D_LOCATE_PROXY",
    "category": "cat02_s1_s2_part_read_and_5d_lock",
    "stage": [
        "S2",
        "S6"
    ],
    "title_zh": "無框 (Box-Free) 5D 測地線 UV 與球頂深度代理定位器",
    "summary_zh": "由 2D 閉合部件剪影計算距離變換測地線 (u, v)、PCA 主軸角度 θ 與球頂深度/法線代理 (Normal/Depth Proxy)，輔助非矩形曲面結構對位。",
    "core_role": "BOX_FREE_5D_UV"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M06] `BOX_FREE_5D_LOCATE_PROXY` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M06] BOX_FREE_5D_LOCATE_PROXY: 無框 (Box-Free) 5D 測地線 UV 與球頂深度代理定位器"
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
