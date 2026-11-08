#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m15_skill_c3_attenuate_hf_detail_layer.py
=========================================
[M15] SKILL_C3_ATTENUATE_HF_DETAIL_LAYER — 技能 C3：高頻細節層獨立無損衰減與降噪回退器
Category : cat04_s4_s5_true_hd_upgrade_engines (分類 04：S4–S5 真升清核心引擎（三頻分解 A/B/C/C2/C3 與多源高清轉移類）)
Stage    : S4

Summary:
  當高頻表面噪點過強時，僅對 H_detail 乘上衰減係數 γ (如 0.45)，驗證 L_base 與 M_material 保持 Bit-Identical 零損壞。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m15_skill_c3_attenuate_hf_detail_layer.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m15_skill_c3_attenuate_hf_detail_layer.py --part P08
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m15_skill_c3_attenuate_hf_detail_layer.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M15 --part P08
  python invoke_method.py --run SKILL_C3_ATTENUATE_HF_DETAIL_LAYER --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M15",
    "slug": "m15_skill_c3_attenuate_hf_detail_layer",
    "method_id": "SKILL_C3_ATTENUATE_HF_DETAIL_LAYER",
    "category": "cat04_s4_s5_true_hd_upgrade_engines",
    "stage": [
        "S4"
    ],
    "title_zh": "技能 C3：高頻細節層獨立無損衰減與降噪回退器",
    "summary_zh": "當高頻表面噪點過強時，僅對 H_detail 乘上衰減係數 γ (如 0.45)，驗證 L_base 與 M_material 保持 Bit-Identical 零損壞。",
    "core_role": "SKILL_C3_ATTENUATE"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M15] `SKILL_C3_ATTENUATE_HF_DETAIL_LAYER` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M15] SKILL_C3_ATTENUATE_HF_DETAIL_LAYER: 技能 C3：高頻細節層獨立無損衰減與降噪回退器"
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
