from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ige-comfy-shq",
        description="SHQ geometry-bound Comfy candidate runner (Cloud diagnostic + local core-only S6).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser(
        "prepare",
        help="freeze source/canvas/masks/tile plan and generate deterministic Comfy LoadImage crops",
    )
    prepare.add_argument("--workflow", type=Path, required=True, help="Comfy API prompt JSON")
    prepare.add_argument("--source", type=Path, required=True, help="original source image (identity/S0 bind)")
    prepare.add_argument("--canvas", type=Path, required=True, help="full-resolution baseline canvas (S2 coordinate canvas)")
    prepare.add_argument("--geometry-contract", type=Path, required=True, help="human-verified S2 geometry contract JSON used by the SHQ Agent Driver")
    prepare.add_argument("--approved-mask", type=Path, required=True, help="binary 0/255 approved edit mask at canvas size")
    prepare.add_argument("--protected-mask", type=Path, required=True, help="binary 0/255 protected mask at canvas size")
    prepare.add_argument("--tile-plan", type=Path, required=True, help="S4 JSON tile plan in global canvas coordinates")
    prepare.add_argument("--output-dir", type=Path, required=True, help="new run directory for inputs, outputs and receipts")
    prepare.add_argument("--out", type=Path, required=True, help="geometry-locked run manifest JSON")
    prepare.add_argument("--permission-template", type=Path, default=None, help="human S3 review template (default: <manifest>.permission-review.json)")
    prepare.add_argument("--run-id", default=None)
    prepare.add_argument("--overwrite", action="store_true")

    preflight = sub.add_parser("preflight", help="live Cloud node/model preflight; does not submit a job")
    preflight.add_argument("manifest", type=Path)
    preflight.add_argument("--out", type=Path, default=None)

    run = sub.add_parser("run", help="submit explicit diagnostic Cloud job, download tiles, run S6 core-only compositor")
    run.add_argument("manifest", type=Path)
    run.add_argument("--permission", type=Path, required=True, help="reviewed S3 permission receipt JSON")
    run.add_argument("--diagnostic-submit", action="store_true", help="explicit consent; may consume Comfy Cloud credits")
    run.add_argument("--timeout", type=float, default=1800)
    run.add_argument("--poll-interval", type=float, default=2)
    run.add_argument("--out", type=Path, default=None, help="optional copy of the final run receipt")
    run.add_argument("--overwrite", action="store_true")
    return parser


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            from .geometry_locked_runtime import create_geometry_locked_comfy_manifest
            result = create_geometry_locked_comfy_manifest(
                workflow_path=args.workflow,
                source_path=args.source,
                canvas_path=args.canvas,
                geometry_contract_path=args.geometry_contract,
                approved_mask_path=args.approved_mask,
                protected_mask_path=args.protected_mask,
                tile_plan_path=args.tile_plan,
                manifest_path=args.out,
                output_dir=args.output_dir,
                permission_template_path=args.permission_template,
                run_id=args.run_id,
                overwrite=args.overwrite,
            )
            print(json.dumps({k: v for k, v in result.items() if k != "manifest"}, ensure_ascii=False, indent=2))
            print("status=PREPARED_AWAITING_HUMAN_S3_REVIEW execution_allowed=false edit_permission=false")
            return 0

        if args.command == "preflight":
            from .cloud_client import ComfyCloudClient
            from .geometry_locked_runtime import preflight_comfy_geometry_locked
            report = preflight_comfy_geometry_locked(args.manifest, client=ComfyCloudClient())
            if args.out:
                _write_json(args.out, report)
                print(f"preflight_report={args.out}")
            else:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            print(
                f"status={report['status']} diagnostic_blockers="
                f"{','.join(report['diagnostic_blockers_retained']) or 'none'} execution_allowed=false"
            )
            return 0

        if args.command == "run":
            from .cloud_client import ComfyCloudClient
            from .geometry_locked_runtime import run_comfy_geometry_locked
            receipt = run_comfy_geometry_locked(
                args.manifest,
                permission_path=args.permission,
                diagnostic_submit=args.diagnostic_submit,
                client=ComfyCloudClient(),
                timeout_seconds=args.timeout,
                poll_interval_seconds=args.poll_interval,
                overwrite=args.overwrite,
            )
            if args.out:
                _write_json(args.out, receipt)
                print(f"run_receipt_copy={args.out}")
            print(
                f"prompt_id={receipt['prompt_id']} master={receipt['s6_local_compositor']['master_path']} "
                f"s6={receipt['s6_local_compositor']['status']} s7={receipt['s7_status']} "
                "candidate_accepted=false execution_allowed=false"
            )
            return 0
    except Exception as exc:
        print(f"IGE_COMFY_SHQ_FAILED: {exc}")
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
