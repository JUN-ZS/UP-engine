#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m18_hole_scalelock_hf_residual.py
=================================
[M18] HOLE_SCALELOCK_HF_RESIDUAL — 非生成式比例鎖定高頻殘差對照基準 (Deterministic Control)
Category : cat04_s4_s5_true_hd_upgrade_engines (分類 04：S4–S5 真升清核心引擎（三頻分解 A/B/C/C2/C3 與多源高清轉移類）)
Stage    : S5, S6, S7

Summary:
  僅使用純數學比例鎖定高頻殘差而不引入 AI 母本材質，作為衡量真 AI 升清（M12+M13）增益幅度的科學非生成式對照組。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m18_hole_scalelock_hf_residual.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m18_hole_scalelock_hf_residual.py --part P08
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m18_hole_scalelock_hf_residual.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M18 --part P08
  python invoke_method.py --run HOLE_SCALELOCK_HF_RESIDUAL --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M18",
    "slug": "m18_hole_scalelock_hf_residual",
    "method_id": "HOLE_SCALELOCK_HF_RESIDUAL",
    "category": "cat04_s4_s5_true_hd_upgrade_engines",
    "stage": [
        "S5",
        "S6",
        "S7"
    ],
    "title_zh": "非生成式比例鎖定高頻殘差對照基準 (Deterministic Control)",
    "summary_zh": "僅使用純數學比例鎖定高頻殘差而不引入 AI 母本材質，作為衡量真 AI 升清（M12+M13）增益幅度的科學非生成式對照組。",
    "core_role": "NON_GEN_HF_CONTROL"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M18] `HOLE_SCALELOCK_HF_RESIDUAL` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M18] HOLE_SCALELOCK_HF_RESIDUAL: 非生成式比例鎖定高頻殘差對照基準 (Deterministic Control)"
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
