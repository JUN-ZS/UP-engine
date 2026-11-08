#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m08_bf_s3_human_permission_compiler.py
======================================
[M08] BF_S3_HUMAN_PERMISSION_COMPILER — S3 人類核實權限編譯器（互斥修改區與保護區編譯）
Category : cat03_s3_s4_permission_and_routing (分類 03：S3–S4 人類核實權限編譯、拓撲守門與狀態技能路由類)
Stage    : S3

Summary:
  將人類核實後的 4× 部件契約編譯為嚴格互斥的 edit_mask_4x 與 preserve_mask_4x；當 human_verified=False 時強制攔截一切生成與寫回操作。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat03_s3_s4_permission_and_routing/m08_bf_s3_human_permission_compiler.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat03_s3_s4_permission_and_routing/m08_bf_s3_human_permission_compiler.py --part P08
  python methods/cat03_s3_s4_permission_and_routing/m08_bf_s3_human_permission_compiler.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M08 --part P08
  python invoke_method.py --run BF_S3_HUMAN_PERMISSION_COMPILER --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M08",
    "slug": "m08_bf_s3_human_permission_compiler",
    "method_id": "BF_S3_HUMAN_PERMISSION_COMPILER",
    "category": "cat03_s3_s4_permission_and_routing",
    "stage": [
        "S3"
    ],
    "title_zh": "S3 人類核實權限編譯器（互斥修改區與保護區編譯）",
    "summary_zh": "將人類核實後的 4× 部件契約編譯為嚴格互斥的 edit_mask_4x 與 preserve_mask_4x；當 human_verified=False 時強制攔截一切生成與寫回操作。",
    "core_role": "PERMISSION_COMPILER"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M08] `BF_S3_HUMAN_PERMISSION_COMPILER` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M08] BF_S3_HUMAN_PERMISSION_COMPILER: S3 人類核實權限編譯器（互斥修改區與保護區編譯）"
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
