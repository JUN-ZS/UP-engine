from __future__ import annotations

import argparse
from pathlib import Path

from .manifest import load_manifest


def main() -> int:
    parser = argparse.ArgumentParser(prog="ige")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-manifest", help="validate a PEEP manifest JSON file")
    validate.add_argument("path", type=Path)

    read = sub.add_parser(
        "read-image",
        help="inspect a still image and export auditable region masks and a preview",
    )
    read.add_argument("image", type=Path)
    read.add_argument("--out", type=Path, required=True, help="new or empty output directory")
    read.add_argument("--regions", type=Path, help="human-reviewed normalized polygon annotations JSON")
    read.add_argument(
        "--provider", choices=("none", "sam3"), default="none",
        help="optional semantic proposal provider; proposals never authorize edits",
    )
    read.add_argument(
        "--prompt", action="append", default=[],
        help="text concept to segment; repeat to request multiple concepts (SAM3 only)",
    )
    read.add_argument("--overwrite", action="store_true", help="allow writing into a non-empty output directory")

    args = parser.parse_args()
    if args.command == "validate-manifest":
        manifest = load_manifest(args.path)
        print(
            f"VALID: task={manifest.task_id} adapter={manifest.adapter_id} "
            f"parent={manifest.parent_asset_id}"
        )
        return 0

    if args.command == "read-image":
        from .read import run_read

        segmentation_provider = None
        if args.provider == "sam3":
            from .read.providers.sam3 import Sam3TextSegmenter
            segmentation_provider = Sam3TextSegmenter()
        report = run_read(
            args.image,
            args.out,
            regions_path=args.regions,
            provider=segmentation_provider,
            prompts=args.prompt,
            overwrite=args.overwrite,
        )
        print(f"READ complete: {args.out}")
        print(
            f"Image: {report['source']['width']}x{report['source']['height']} "
            f"SHA256={report['source']['sha256']}"
        )
        print(
            f"Human-editable pixels: {report['mask_policy']['editable_pixels']} | "
            f"Effective protected pixels: {report['mask_policy']['effective_protected_pixels']}"
        )
        print(
            f"Semantic proposals: {report['semantic_segmentation']['proposal_count']} "
            f"({report['semantic_segmentation']['status']})"
        )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
