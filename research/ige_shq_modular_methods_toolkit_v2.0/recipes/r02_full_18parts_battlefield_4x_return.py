#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
r02_full_18parts_battlefield_4x_return.py
=========================================
[R02] 組合應用 R02：全戰場 18 部件完整「生・除・扣・洞 → 密集光流真升清 → 併回 5504×3072 大圖 → S7 反驗」

Summary:
  串聯 M01→M04→M05→M08→M11→M12→M13→M21→M22，一次完成全圖 18 個自身部件升清併回大圖並通過磁碟重讀反驗。
  Chained Methods: M01 -> M04 -> M05 -> M08 -> M11 -> M12 -> M13 -> M21 -> M22

Usage:
  python recipes/r02_full_18parts_battlefield_4x_return.py --part P08
  python invoke_method.py --recipe R02 --part P08
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from invoke_method import METHOD_INDEX, run_single_method_by_key
from methods.common_runtime import resolve_part_id

RECIPE_META: Dict[str, Any] = {
    "code": "R02",
    "slug": "r02_full_18parts_battlefield_4x_return",
    "title_zh": "組合應用 R02：全戰場 18 部件完整「生・除・扣・洞 → 密集光流真升清 → 併回 5504×3072 大圖 → S7 反驗」",
    "summary_zh": "串聯 M01→M04→M05→M08→M11→M12→M13→M21→M22，一次完成全圖 18 個自身部件升清併回大圖並通過磁碟重讀反驗。",
    "chain": [
        "M01",
        "M04",
        "M05",
        "M08",
        "M11",
        "M12",
        "M13",
        "M21",
        "M22"
    ]
}


def run_recipe(
    part_id: str = "B1_P08_GOLDMESH_CARBON_TORSO",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute the chained methods in Recipe `R02` sequentially and return the combined receipt."""
    pid = resolve_part_id(part_id)
    out_base = Path(output_dir) if output_dir else (_PKG_ROOT / "outputs" / "per_recipe")
    out_base.mkdir(parents=True, exist_ok=True)

    step_receipts: List[Dict[str, Any]] = []
    for m_code in RECIPE_META["chain"]:
        rec = run_single_method_by_key(m_code, part_id=pid, gamma=gamma, output_dir=out_base / RECIPE_META["code"])
        step_receipts.append({
            "code": rec["code"],
            "method_id": rec["method_id"],
            "module_file": rec["module_file"],
            "status": rec["status"],
            "preview_image_file": rec["preview_image_file"],
            "key_metrics": rec["metrics"],
        })

    all_pass = all(s["status"] == "PASS" for s in step_receipts)
    recipe_receipt = {
        "recipe_code": RECIPE_META["code"],
        "slug": RECIPE_META["slug"],
        "title_zh": RECIPE_META["title_zh"],
        "summary_zh": RECIPE_META["summary_zh"],
        "target_part_id": pid,
        "chained_method_codes": RECIPE_META["chain"],
        "step_count": len(step_receipts),
        "all_steps_passed": all_pass,
        "status": "PASS" if all_pass else "FAIL",
        "steps": step_receipts,
    }
    out_json = out_base / f"{RECIPE_META['code']}_{RECIPE_META['slug']}_receipt.json"
    out_json.write_text(json.dumps(recipe_receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    recipe_receipt["receipt_json_file"] = str(out_json.relative_to(_PKG_ROOT)) if out_json.is_relative_to(_PKG_ROOT) else str(out_json)
    return recipe_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="[R02] 組合應用 R02：全戰場 18 部件完整「生・除・扣・洞 → 密集光流真升清 → 併回 5504×3072 大圖 → S7 反驗」")
    parser.add_argument("--part", type=str, default="B1_P08_GOLDMESH_CARBON_TORSO", help="Target part ID (P01..P18)")
    parser.add_argument("--gamma", type=float, default=0.45, help="HF attenuation gamma for Skill C3")
    parser.add_argument("--output-dir", type=str, default=None, help="Optional output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir) if args.output_dir else None
    res = run_recipe(part_id=args.part, gamma=args.gamma, output_dir=out_dir)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
