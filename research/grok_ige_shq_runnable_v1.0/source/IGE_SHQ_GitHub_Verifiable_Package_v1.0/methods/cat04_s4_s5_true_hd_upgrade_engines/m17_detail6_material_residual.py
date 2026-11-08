#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m17_detail6_material_residual.py
================================
[M17] DETAIL6_MATERIAL_RESIDUAL — DETAIL6 材質分區遮罩高頻投遞器（含面部皮膚零變動保護）
Category : cat04_s4_s5_true_hd_upgrade_engines (分類 04：S4–S5 真升清核心引擎（三頻分解 A/B/C/C2/C3 與多源高清轉移類）)
Stage    : S4, S5, S6, S7

Summary:
  在已驗證的 4× 母畫布上對金屬裝甲與金網絲區域投遞受控高頻能量，同時對 B1 指揮官面部皮膚與眼睛保護遮罩強制維持 0 像素變動。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m17_detail6_material_residual.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m17_detail6_material_residual.py --part P08
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m17_detail6_material_residual.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M17 --part P08
  python invoke_method.py --run DETAIL6_MATERIAL_RESIDUAL --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M17",
    "slug": "m17_detail6_material_residual",
    "method_id": "DETAIL6_MATERIAL_RESIDUAL",
    "category": "cat04_s4_s5_true_hd_upgrade_engines",
    "stage": [
        "S4",
        "S5",
        "S6",
        "S7"
    ],
    "title_zh": "DETAIL6 材質分區遮罩高頻投遞器（含面部皮膚零變動保護）",
    "summary_zh": "在已驗證的 4× 母畫布上對金屬裝甲與金網絲區域投遞受控高頻能量，同時對 B1 指揮官面部皮膚與眼睛保護遮罩強制維持 0 像素變動。",
    "core_role": "DETAIL6_PROTECTED_DELIVERY"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M17] `DETAIL6_MATERIAL_RESIDUAL` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M17] DETAIL6_MATERIAL_RESIDUAL: DETAIL6 材質分區遮罩高頻投遞器（含面部皮膚零變動保護）"
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
