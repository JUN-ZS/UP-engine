#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m22_skill_d_immutable_alpha_geometry_guard.py
=============================================
[M22] SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD — 技能 D：不可變 Alpha 幾何守衛 + 規則 01380 全洞滿填併回大圖 + S7 磁碟重讀反驗
Category : cat05_s6_s7_geometry_locked_return_and_audit (分類 05：S6–S7 規則 01380 鎖幾何併回大圖與磁碟重讀反驗類)
Stage    : S1, S5, S6

Summary:
  執行 I_4x = L_base + M_material + H_detail 全洞 100% 硬邊合成（eroded_low_res_border=0、soft_alpha=0、洞外差異=0），寫出 5504×3072 大圖並從磁碟重讀執行反扣驗收。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat05_s6_s7_geometry_locked_return_and_audit/m22_skill_d_immutable_alpha_geometry_guard.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat05_s6_s7_geometry_locked_return_and_audit/m22_skill_d_immutable_alpha_geometry_guard.py --part P08
  python methods/cat05_s6_s7_geometry_locked_return_and_audit/m22_skill_d_immutable_alpha_geometry_guard.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M22 --part P08
  python invoke_method.py --run SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M22",
    "slug": "m22_skill_d_immutable_alpha_geometry_guard",
    "method_id": "SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD",
    "category": "cat05_s6_s7_geometry_locked_return_and_audit",
    "stage": [
        "S1",
        "S5",
        "S6"
    ],
    "title_zh": "技能 D：不可變 Alpha 幾何守衛 + 規則 01380 全洞滿填併回大圖 + S7 磁碟重讀反驗",
    "summary_zh": "執行 I_4x = L_base + M_material + H_detail 全洞 100% 硬邊合成（eroded_low_res_border=0、soft_alpha=0、洞外差異=0），寫出 5504×3072 大圖並從磁碟重讀執行反扣驗收。",
    "core_role": "SKILL_D_RULE01380_AND_S7_QA"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M22] `SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M22] SKILL_D_IMMUTABLE_ALPHA_GEOMETRY_GUARD: 技能 D：不可變 Alpha 幾何守衛 + 規則 01380 全洞滿填併回大圖 + S7 磁碟重讀反驗"
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
