from __future__ import annotations

import argparse
from pathlib import Path
from .manifest import load_manifest


def main() -> int:
    parser = argparse.ArgumentParser(prog="ige")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-manifest", help="validate a PEEP manifest JSON file")
    validate.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "validate-manifest":
        manifest = load_manifest(args.path)
        print(f"VALID: task={manifest.task_id} adapter={manifest.adapter_id} parent={manifest.parent_asset_id}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
