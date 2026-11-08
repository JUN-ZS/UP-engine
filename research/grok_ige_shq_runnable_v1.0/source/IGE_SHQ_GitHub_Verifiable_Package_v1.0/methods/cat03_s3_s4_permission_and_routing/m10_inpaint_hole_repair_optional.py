#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m10_inpaint_hole_repair_optional.py
===================================
[M10] INPAINT_HOLE_REPAIR_OPTIONAL — 受控選用之遮擋缺損低頻修補器（禁止充當主升清引擎）
Category : cat03_s3_s4_permission_and_routing (分類 03：S3–S4 人類核實權限編譯、拓撲守門與狀態技能路由類)
Stage    : S2

Summary:
  僅在部件存在被遮擋孔洞缺損時執行局部低頻結構補洞（Navier-Stokes/Telea 結構修補），並在路由層強制禁止 Inpaint 取代 A+B+C+D 主升清鏈。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat03_s3_s4_permission_and_routing/m10_inpaint_hole_repair_optional.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat03_s3_s4_permission_and_routing/m10_inpaint_hole_repair_optional.py --part P08
  python methods/cat03_s3_s4_permission_and_routing/m10_inpaint_hole_repair_optional.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M10 --part P08
  python invoke_method.py --run INPAINT_HOLE_REPAIR_OPTIONAL --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M10",
    "slug": "m10_inpaint_hole_repair_optional",
    "method_id": "INPAINT_HOLE_REPAIR_OPTIONAL",
    "category": "cat03_s3_s4_permission_and_routing",
    "stage": [
        "S2"
    ],
    "title_zh": "受控選用之遮擋缺損低頻修補器（禁止充當主升清引擎）",
    "summary_zh": "僅在部件存在被遮擋孔洞缺損時執行局部低頻結構補洞（Navier-Stokes/Telea 結構修補），並在路由層強制禁止 Inpaint 取代 A+B+C+D 主升清鏈。",
    "core_role": "OPTIONAL_INPAINT"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M10] `INPAINT_HOLE_REPAIR_OPTIONAL` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M10] INPAINT_HOLE_REPAIR_OPTIONAL: 受控選用之遮擋缺損低頻修補器（禁止充當主升清引擎）"
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
