#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
invoke_method.py
================
Unified CLI Dispatcher & Python SDK for trying all 22 categorized SHQ methods (`M01`–`M22`)
and 3 end-to-end composite recipes (`R01`–`R03`) one by one or by category.

Examples for other AI users:
  1. List all 22 categorized methods and 3 recipes:
     python invoke_method.py --list

  2. List all 18 selectable battlefield self-parts (P01..P18):
     python invoke_method.py --list-parts

  3. Inspect detailed inputs/outputs/claims of a single method:
     python invoke_method.py --info M12
     python invoke_method.py --info SKILL_B_GEOMETRY_LOCKED_MATERIAL_GEN

  4. Run a single method on a chosen self-part (e.g. P08 Gold-Mesh Torso or P02 Mecha Chest):
     python invoke_method.py --run M12 --part P08
     python invoke_method.py --run M22 --part P02

  5. Run an entire category of methods (e.g. cat04 true HD upgrade engines):
     python invoke_method.py --category cat04 --part P08

  6. Run an end-to-end composite recipe (e.g. R01 single part upgrade & return):
     python invoke_method.py --recipe R01 --part P08
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PKG_ROOT = Path(__file__).resolve().parent
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))
if str(PKG_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PKG_ROOT / "src"))

from methods.common_runtime import CANONICAL_18_PARTS, resolve_part_id

CATALOG_PATH = PKG_ROOT / "methods" / "method_catalog_index.json"
CATALOG_DATA = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

CATEGORIES_MAP: Dict[str, Dict[str, Any]] = CATALOG_DATA["categories"]
METHODS_LIST: List[Dict[str, Any]] = CATALOG_DATA["methods"]
RECIPES_LIST: List[Dict[str, Any]] = CATALOG_DATA["recipes"]

METHOD_INDEX: Dict[str, Dict[str, Any]] = {}
for m in METHODS_LIST:
    METHOD_INDEX[m["code"].upper()] = m
    METHOD_INDEX[m["method_id"].upper()] = m
    METHOD_INDEX[m["slug"].upper()] = m

RECIPE_INDEX: Dict[str, Dict[str, Any]] = {}
for r in RECIPES_LIST:
    RECIPE_INDEX[r["code"].upper()] = r
    RECIPE_INDEX[r["slug"].upper()] = r


def run_single_method_by_key(
    key: str,
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Import the categorized `.py` module for `key` (`M01`..`M22` or `method_id`) and call `run_method()`."""
    k = key.strip().upper()
    if k not in METHOD_INDEX:
        raise KeyError(f"Unknown method '{key}'. Use `python invoke_method.py --list` to see M01..M22.")
    m = METHOD_INDEX[k]
    mod_name = f"methods.{m['category']}.{m['slug']}"
    mod = importlib.import_module(mod_name)
    return mod.run_method(part_id=part_id, gamma=gamma, output_dir=output_dir)


def run_category_by_key(
    cat_query: str,
    part_id: str = "B0_P02_TITANIUM_CHEST_CORE",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run all methods belonging to a category (e.g., `cat01`..`cat05`)."""
    cq = cat_query.strip().lower()
    matched_cat = None
    for cid in CATEGORIES_MAP:
        if cq == cid.lower() or cid.lower().startswith(cq):
            matched_cat = cid
            break
    if not matched_cat:
        raise KeyError(f"Unknown category '{cat_query}'. Valid categories: {list(CATEGORIES_MAP.keys())}")

    cat_methods = [m for m in METHODS_LIST if m["category"] == matched_cat]
    results = []
    for m in cat_methods:
        res = run_single_method_by_key(m["code"], part_id=part_id, gamma=gamma, output_dir=output_dir)
        results.append(res)
    return {
        "category": matched_cat,
        "title_zh": CATEGORIES_MAP[matched_cat]["title_zh"],
        "method_count": len(results),
        "all_passed": all(r["status"] == "PASS" for r in results),
        "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
        "results": results,
    }


def run_recipe_by_key(
    recipe_key: str,
    part_id: str = "B1_P08_GOLDMESH_CARBON_TORSO",
    gamma: float = 0.45,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Import the recipe `.py` module (`R01`..`R03`) and call `run_recipe()`."""
    rk = recipe_key.strip().upper()
    if rk not in RECIPE_INDEX:
        raise KeyError(f"Unknown recipe '{recipe_key}'. Valid recipes: R01, R02, R03.")
    r = RECIPE_INDEX[rk]
    mod = importlib.import_module(f"recipes.{r['slug']}")
    return mod.run_recipe(part_id=part_id, gamma=gamma, output_dir=output_dir)


def print_catalog_table() -> None:
    print("=" * 108)
    print("IGE-SHQ 模組化「真升清 → 鎖幾何併回大圖」方法庫 (共 5 大分類 / 22 個獨立方法 PY / 3 個端到端組合 Recipes)")
    print("=" * 108)
    for cid, cinfo in CATEGORIES_MAP.items():
        print(f"\n【{cinfo['title_zh']}】 (目錄: methods/{cid}/)")
        print(f"  說明: {cinfo['desc_zh']}")
        print("-" * 108)
        for m in METHODS_LIST:
            if m["category"] == cid:
                st = ",".join(m["stage"])
                print(f"  [{m['code']}] {m['method_id']:38s} | Stage: {st:10s} | File: methods/{cid}/{m['slug']}.py")
                print(f"        -> {m['title_zh']}")
    print("\n" + "=" * 108)
    print("【分類 06：端到端組合應用 Recipes】 (目錄: recipes/)")
    print("-" * 108)
    for r in RECIPES_LIST:
        chain_s = " -> ".join(r["chain"])
        print(f"  [{r['code']}] recipes/{r['slug']}.py")
        print(f"        -> {r['title_zh']} (串聯: {chain_s})")
    print("=" * 108)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified CLI Invoker for IGE-SHQ 22 Categorized Methods & 3 Recipes"
    )
    parser.add_argument("--list", action="store_true", help="List all 22 categorized methods and 3 recipes")
    parser.add_argument("--list-parts", action="store_true", help="List all 18 selectable self-parts (P01..P18)")
    parser.add_argument("--info", type=str, default=None, help="Show detailed metadata for a method (e.g. M12 or SKILL_B_...)")
    parser.add_argument("--run", type=str, default=None, help="Run a single method by code (M01..M22) or method_id")
    parser.add_argument("--category", type=str, default=None, help="Run all methods in a category (cat01..cat05)")
    parser.add_argument("--recipe", type=str, default=None, help="Run an end-to-end composite recipe (R01..R03)")
    parser.add_argument("--part", type=str, default="B0_P02_TITANIUM_CHEST_CORE", help="Target self-part (P01..P18)")
    parser.add_argument("--gamma", type=float, default=0.45, help="HF attenuation gamma for M15 (Skill C3)")
    parser.add_argument("--output-dir", type=str, default=None, help="Optional output directory")
    args = parser.parse_args()

    if args.list:
        print_catalog_table()
        return 0

    if args.list_parts:
        for i, pid in enumerate(CANONICAL_18_PARTS, 1):
            print(f"P{i:02d} : {pid}")
        return 0

    if args.info:
        k = args.info.strip().upper()
        if k in METHOD_INDEX:
            print(json.dumps(METHOD_INDEX[k], indent=2, ensure_ascii=False))
            return 0
        if k in RECIPE_INDEX:
            print(json.dumps(RECIPE_INDEX[k], indent=2, ensure_ascii=False))
            return 0
        print(f"Error: Unknown method or recipe '{args.info}'", file=sys.stderr)
        return 1

    out_dir = Path(args.output_dir) if args.output_dir else None

    if args.run:
        res = run_single_method_by_key(args.run, part_id=args.part, gamma=args.gamma, output_dir=out_dir)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["status"] == "PASS" else 1

    if args.category:
        res = run_category_by_key(args.category, part_id=args.part, gamma=args.gamma, output_dir=out_dir)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["status"] == "PASS" else 1

    if args.recipe:
        res = run_recipe_by_key(args.recipe, part_id=args.part, gamma=args.gamma, output_dir=out_dir)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["status"] == "PASS" else 1

    print_catalog_table()
    return 0


if __name__ == "__main__":
    sys.exit(main())