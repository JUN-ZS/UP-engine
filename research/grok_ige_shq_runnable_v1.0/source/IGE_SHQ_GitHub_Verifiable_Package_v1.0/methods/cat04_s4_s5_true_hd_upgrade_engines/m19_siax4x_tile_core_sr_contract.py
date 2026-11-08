#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m19_siax4x_tile_core_sr_contract.py
===================================
[M19] SIAX4X_TILE_CORE_SR — Siax 4× Tile-Core 超分契約與反插值偽造守衛
Category : cat04_s4_s5_true_hd_upgrade_engines (分類 04：S4–S5 真升清核心引擎（三頻分解 A/B/C/C2/C3 與多源高清轉移類）)
Stage    : S4, S5, S6, S7

Summary:
  生成 Siax 4× 分塊 Core+Halo 幾何契約並檢查模型權重 Sidecar；無實體 .pth 權重時明確標記離線契約模式，嚴禁以 Lanczos 插值冒充 Siax 推理。

Standalone CLI Usage (for other AI users or developers to try individually):
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m19_siax4x_tile_core_sr_contract.py --part B0_P02_TITANIUM_CHEST_CORE
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m19_siax4x_tile_core_sr_contract.py --part P08
  python methods/cat04_s4_s5_true_hd_upgrade_engines/m19_siax4x_tile_core_sr_contract.py --info

Unified Dispatcher Usage:
  python invoke_method.py --run M19 --part P08
  python invoke_method.py --run SIAX4X_TILE_CORE_SR --part B1_P08_GOLDMESH_CARBON_TORSO
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
    "code": "M19",
    "slug": "m19_siax4x_tile_core_sr_contract",
    "method_id": "SIAX4X_TILE_CORE_SR",
    "category": "cat04_s4_s5_true_hd_upgrade_engines",
    "stage": [
        "S4",
        "S5",
        "S6",
        "S7"
    ],
    "title_zh": "Siax 4× Tile-Core 超分契約與反插值偽造守衛",
    "summary_zh": "生成 Siax 4× 分塊 Core+Halo 幾何契約並檢查模型權重 Sidecar；無實體 .pth 權重時明確標記離線契約模式，嚴禁以 Lanczos 插值冒充 Siax 推理。",
    "core_role": "SIAX4X_CONTRACT_GUARD"
}


def run_method(
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute [M19] `SIAX4X_TILE_CORE_SR` on `part_id` and return its verification receipt."""
    return execute_core_role(
        meta=METHOD_META,
        part_id=part_id,
        gamma=gamma,
        output_dir=output_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="[M19] SIAX4X_TILE_CORE_SR: Siax 4× Tile-Core 超分契約與反插值偽造守衛"
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
