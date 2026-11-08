#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m07_path1e_identity_ecc_lock.py
===============================
[M07] PATH1E_IDENTITY_ECC_LOCK — 人物面部與關鍵部件 ECC 亞像素身分地標對齊鎖
Category : cat02_s1_s2_part_read_and_5d_lock (分類 02：S1–S2 自身 18 部件流線拆解、無框 5D 定位與 4× 幾何鎖定類)
Stage    : S2, S4, S6

Summary:
  針對 B1 指揮官面部與關鍵感測器部件執行亞像素相位與 ECC 結構對齊並防水平翻轉；若缺失身分參考圖則強制阻斷並標記 unknown。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat02_s1_s2_part_read_and_5d_lock/m07_path1e_identity_ecc_lock.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat02_s1_s2_part_read_and_5d_lock/m07_path1e_identity_ecc_lock.py --part P08
  python methods/cat02_s1_s2_part_read_and_5d_lock/m07_path1e_identity_ecc_lock.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M07 --part P08
  python invoke_method.py --run PATH1E_IDENTITY_ECC_LOCK --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M07",
    "slug": "m07_path1e_identity_ecc_lock",
    "method_id": "PATH1E_IDENTITY_ECC_LOCK",
    "category": "cat02_s1_s2_part_read_and_5d_lock",
    "stage": [
        "S2",
        "S4",
        "S6"
    ],
    "title_zh": "人物面部與關鍵部件 ECC 亞像素身分地標對齊鎖",
    "summary_zh": "針對 B1 指揮官面部與關鍵感測器部件執行亞像素相位與 ECC 結構對齊並防水平翻轉；若缺失身分參考圖則強制阻斷並標記 unknown。",
    "core_role": "IDENTITY_ECC_LOCK"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M07] `PATH1E_IDENTITY_ECC_LOCK` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M07] PATH1E_IDENTITY_ECC_LOCK: 人物面部與關鍵部件 ECC 亞像素身分地標對齊鎖"
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
