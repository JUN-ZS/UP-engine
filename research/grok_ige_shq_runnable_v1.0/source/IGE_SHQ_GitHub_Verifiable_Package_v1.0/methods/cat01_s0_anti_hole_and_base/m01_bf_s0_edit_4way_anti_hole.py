#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m01_bf_s0_edit_4way_anti_hole.py
================================
[M01] BF_S0_EDIT_4WAY_ANTI_HOLE — 戰場 S0 四向正反空背景求洞與反洞凍結
Category : cat01_s0_anti_hole_and_base (分類 01：S0 原圖凍結與正反對照空背景「生・除・扣・洞・反洞」類)
Stage    : S0

Summary:
  對照同鏡頭戰場原圖 (Keep) 與移除人物機甲之空背景圖 (Remove)，精確求出 3 主體閉合剪影洞 M_hole 與反洞保護區 M_anti_hole (M_hole ^ M_anti_hole == 255)。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat01_s0_anti_hole_and_base/m01_bf_s0_edit_4way_anti_hole.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat01_s0_anti_hole_and_base/m01_bf_s0_edit_4way_anti_hole.py --part P08
  python methods/cat01_s0_anti_hole_and_base/m01_bf_s0_edit_4way_anti_hole.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M01 --part P08
  python invoke_method.py --run BF_S0_EDIT_4WAY_ANTI_HOLE --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M01",
    "slug": "m01_bf_s0_edit_4way_anti_hole",
    "method_id": "BF_S0_EDIT_4WAY_ANTI_HOLE",
    "category": "cat01_s0_anti_hole_and_base",
    "stage": [
        "S0"
    ],
    "title_zh": "戰場 S0 四向正反空背景求洞與反洞凍結",
    "summary_zh": "對照同鏡頭戰場原圖 (Keep) 與移除人物機甲之空背景圖 (Remove)，精確求出 3 主體閉合剪影洞 M_hole 與反洞保護區 M_anti_hole (M_hole ^ M_anti_hole == 255)。",
    "core_role": "S0_FOUR_WAY_ANTI_HOLE"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M01] `BF_S0_EDIT_4WAY_ANTI_HOLE` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M01] BF_S0_EDIT_4WAY_ANTI_HOLE: 戰場 S0 四向正反空背景求洞與反洞凍結"
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
