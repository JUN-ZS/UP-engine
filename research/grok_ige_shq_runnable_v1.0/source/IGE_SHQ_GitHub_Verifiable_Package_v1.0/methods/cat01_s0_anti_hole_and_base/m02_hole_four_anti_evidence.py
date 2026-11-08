#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m02_hole_four_anti_evidence.py
==============================
[M02] HOLE_FOUR_ANTI_EVIDENCE — 四反防呆差分證據驗收器（反偷縮放・反平移・反背景異動・反軟羽化）
Category : cat01_s0_anti_hole_and_base (分類 01：S0 原圖凍結與正反對照空背景「生・除・扣・洞・反洞」類)
Stage    : S1, S2, S3, S4, S6, S7

Summary:
  嚴格驗證正反差分對偶圖之相機零平移 (<=0.1px)、禁止偷縮放、禁止軟邊羽化，並強制規定差分圖僅為幾何證據而不自動授予修改權。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat01_s0_anti_hole_and_base/m02_hole_four_anti_evidence.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat01_s0_anti_hole_and_base/m02_hole_four_anti_evidence.py --part P08
  python methods/cat01_s0_anti_hole_and_base/m02_hole_four_anti_evidence.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M02 --part P08
  python invoke_method.py --run HOLE_FOUR_ANTI_EVIDENCE --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M02",
    "slug": "m02_hole_four_anti_evidence",
    "method_id": "HOLE_FOUR_ANTI_EVIDENCE",
    "category": "cat01_s0_anti_hole_and_base",
    "stage": [
        "S1",
        "S2",
        "S3",
        "S4",
        "S6",
        "S7"
    ],
    "title_zh": "四反防呆差分證據驗收器（反偷縮放・反平移・反背景異動・反軟羽化）",
    "summary_zh": "嚴格驗證正反差分對偶圖之相機零平移 (<=0.1px)、禁止偷縮放、禁止軟邊羽化，並強制規定差分圖僅為幾何證據而不自動授予修改權。",
    "core_role": "FOUR_ANTI_GUARD"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M02] `HOLE_FOUR_ANTI_EVIDENCE` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M02] HOLE_FOUR_ANTI_EVIDENCE: 四反防呆差分證據驗收器（反偷縮放・反平移・反背景異動・反軟羽化）"
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
