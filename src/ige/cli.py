from __future__ import annotations

import argparse
from pathlib import Path

from .manifest import load_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ige",
        description="UP-engine: read images, compile constrained generation tasks, and reconstruct audited candidates.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser(
        "validate-manifest",
        help="validate a PEEP manifest JSON file",
    )
    validate.add_argument("path", type=Path)

    validate_registry = sub.add_parser(
        "validate-method-registry",
        help="validate the versioned S0-S7 Method Registry",
    )
    validate_registry.add_argument("--path", type=Path, default=None)

    audit_s0_s7 = sub.add_parser(
        "audit-s0-s7",
        help="audit source-bound S0-S7 receipts; missing evidence blocks acceptance",
    )
    audit_s0_s7.add_argument("evidence", type=Path, help="S0-S7 evidence bundle JSON")
    audit_s0_s7.add_argument("--method-registry", type=Path, default=None)
    audit_s0_s7.add_argument("--out", type=Path, default=None)

    audit_comfy = sub.add_parser(
        "audit-comfy-workflow",
        help="static ComfyUI UI/API inventory audit for FLUX_HR_TILE candidate (no GPU; never unlocks execution)",
    )
    audit_comfy.add_argument("--ui", type=Path, default=None, help="ComfyUI UI workflow graph JSON")
    audit_comfy.add_argument("--api", type=Path, default=None, help="ComfyUI API prompt JSON")
    audit_comfy.add_argument(
        "--model-inventory",
        type=Path,
        default=None,
        help=(
            "optional declared backend_model_inventory JSON (evidence_grade=declared_record); "
            "filename/pin checks only — not live disk proof; never unlocks execution"
        ),
    )
    audit_comfy.add_argument(
        "--capture-receipt",
        type=Path,
        default=None,
        help=(
            "optional model_inventory_capture receipt from `ige capture-model-inventory` "
            "(evidence_grade=disk_capture); never unlocks execution"
        ),
    )
    audit_comfy.add_argument("--out", type=Path, default=None, help="optional audit report JSON path")

    validate_inv = sub.add_parser(
        "validate-model-inventory",
        help="validate offline backend_model_inventory JSON (filenames+SHA; never unlocks execution)",
    )
    validate_inv.add_argument("--path", type=Path, required=True, help="backend_model_inventory JSON")
    validate_inv.add_argument(
        "--against-ui",
        type=Path,
        default=None,
        help="optional UI workflow to cross-check filenames",
    )
    validate_inv.add_argument(
        "--against-api",
        type=Path,
        default=None,
        help="optional API prompt to cross-check filenames",
    )

    capture_inv = sub.add_parser(
        "capture-model-inventory",
        help=(
            "read weight files from --models-root, stream SHA-256, write a disk-capture receipt "
            "(never runs GPU; never unlocks execution)"
        ),
    )
    capture_inv.add_argument(
        "--models-root",
        type=Path,
        required=True,
        help="ComfyUI models directory to read (e.g. C:\\Users\\user\\Documents\\ComfyUI\\models)",
    )
    capture_inv.add_argument("--out", type=Path, required=True, help="capture receipt JSON output path")
    capture_inv.add_argument(
        "--expect-relative",
        action="append",
        default=None,
        help="relative path under models-root to capture; repeatable (default: Dev FP8 + Siax set)",
    )
    capture_inv.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="optional JSON manifest with assets[{asset_id,role,relative_path,expected_size_bytes?}]",
    )
    capture_inv.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="SHA-256 stream chunk size in bytes (default 8MiB)",
    )

    audit_tile = sub.add_parser(
        "audit-tile-ledger",
        help="audit Core/Halo tile write-back ledger (exact-once coverage; never unlocks execution)",
    )
    audit_tile.add_argument("path", type=Path, help="tile_core_halo_ledger JSON")
    audit_tile.add_argument("--out", type=Path, default=None, help="optional audit report JSON path")

    agent_run = sub.add_parser(
        "agent-run",
        help="preflight or execute a SHQ manifest through the central fail-closed Driver",
    )
    agent_run.add_argument("manifest", type=Path, help="S0-S4 agent run manifest JSON")
    agent_run.add_argument("--execute", action="store_true", help="execute only an explicitly allowlisted and Registry-approved adapter")
    agent_run.add_argument("--method-registry", type=Path, default=None, help="optional Method Registry override")
    agent_run.add_argument("--out", type=Path, default=None, help="optional agent run report JSON path")

    comfy_manifest = sub.add_parser(
        "comfy-cloud-manifest",
        help="create a Comfy Cloud diagnostic manifest and compute tile input SHA-256 values",
    )
    comfy_manifest.add_argument("--workflow", type=Path, required=True, help="API prompt JSON")
    comfy_manifest.add_argument("--tile", action="append", required=True, metavar="NODE_ID=IMAGE_PATH", help="bind one local tile image to a LoadImage node; repeat for every tile")
    comfy_manifest.add_argument("--output-dir", type=Path, default=Path("runs/comfy-cloud-diagnostic"))
    comfy_manifest.add_argument("--run-id", default=None)
    comfy_manifest.add_argument("--out", type=Path, required=True, help="manifest JSON destination")

    comfy_preflight = sub.add_parser(
        "comfy-cloud-preflight",
        help="inspect live Comfy Cloud node/model availability and audit API workflow before submitting",
    )
    comfy_preflight.add_argument("manifest", type=Path)
    comfy_preflight.add_argument("--out", type=Path, default=None)

    comfy_diagnostic = sub.add_parser(
        "comfy-cloud-diagnostic",
        help="explicitly submit a diagnostic-only Comfy Cloud job and save actual outputs/receipts",
    )
    comfy_diagnostic.add_argument("manifest", type=Path)
    comfy_diagnostic.add_argument("--diagnostic-submit", action="store_true", help="explicit consent to submit a non-accepted diagnostic job; may consume Cloud credits")
    comfy_diagnostic.add_argument("--timeout", type=float, default=1800)
    comfy_diagnostic.add_argument("--poll-interval", type=float, default=2)
    comfy_diagnostic.add_argument("--out", type=Path, default=None)

    read = sub.add_parser(
        "read-image",
        help="inspect a still image and export auditable regions, proposals, relations and masks",
    )
    read.add_argument("image", type=Path)
    read.add_argument("--out", type=Path, required=True, help="new or empty output directory")
    read.add_argument("--regions", type=Path, help="human-reviewed normalized polygon annotations JSON")
    read.add_argument("--relations", type=Path, help="human-reviewed object/geometry relations JSON")
    read.add_argument(
        "--provider",
        choices=("none", "sam3"),
        default="none",
        help="optional segmentation proposal provider; proposals never authorize edits",
    )
    read.add_argument(
        "--prompt",
        action="append",
        default=[],
        help="segmentation text concept; repeat for multiple concepts (SAM3 only)",
    )
    read.add_argument(
        "--reasoner",
        choices=("none", "grok", "qwen"),
        default="none",
        help=(
            "optional visual reasoner. 'grok' is the active xAI Grok Vision path. "
            "'qwen' is deprecated and retained only for explicit comparison; never used as fallback"
        ),
    )
    read.add_argument(
        "--reasoning-model",
        default=None,
        help=(
            "reasoner model ID override. For grok, defaults to XAI_VISION_MODEL or grok-4. "
            "For deprecated qwen, defaults to Qwen3.8-27B"
        ),
    )
    read.add_argument(
        "--reasoning-focus",
        default="Inspect visible object parts, exact contact surfaces, occlusion boundaries and relative orientation.",
        help="focus instruction for visual reasoning",
    )
    read.add_argument("--overwrite", action="store_true", help="allow writing into a non-empty output directory")

    compile_task = sub.add_parser(
        "compile-generation",
        help="compile a task-specific pixel whitelist and human-verified geometry locks from a READ run",
    )
    compile_task.add_argument("analysis", type=Path, help="path to READ analysis.json")
    compile_task.add_argument("--out", type=Path, required=True, help="new generation packet directory")
    compile_task.add_argument("--objective", required=True, help="requested edit objective")
    compile_task.add_argument(
        "--target-region",
        action="append",
        required=True,
        help="human-approved editable region ID; repeat to include multiple regions",
    )
    compile_task.add_argument(
        "--base",
        type=Path,
        help="exact parent image; defaults to the path recorded by READ, then verifies SHA-256",
    )
    compile_task.add_argument("--overwrite", action="store_true")

    generate = sub.add_parser(
        "generate-candidate",
        help=(
            "candidate generation. Default backend=here prepares a HERE Grok Imagine job "
            "(and can ingest --candidate). Secondary backend=xai-api calls remote Images API."
        ),
    )
    generate.add_argument("packet", type=Path, help="generation_packet.json")
    generate.add_argument("base", type=Path, help="exact original BASE image")
    generate.add_argument("--out", type=Path, required=True, help="candidate output directory")
    generate.add_argument(
        "--backend",
        choices=("here", "xai-api"),
        default="here",
        help="primary: here (Grok Imagine in agent session). secondary: xai-api remote Images API",
    )
    generate.add_argument(
        "--candidate",
        type=Path,
        default=None,
        help="HERE backend only: path to a candidate image already produced by Grok Imagine tools",
    )
    generate.add_argument("--prompt", default=None, help="optional full prompt override; otherwise packet-constrained default")
    generate.add_argument("--model-id", default=None, help="model/adapter id override")
    generate.add_argument("--aspect-ratio", default=None, help="optional aspect_ratio hint, e.g. 16:9")
    generate.add_argument("--resolution", default="2k", help="xai-api only: 1k or 2k")
    generate.add_argument("--quality", default="medium", help="xai-api only: low, medium, or auto")
    generate.add_argument("--request-id", default=None, help="optional HERE asset/request id for audit metadata")
    generate.add_argument("--overwrite", action="store_true")

    accept = sub.add_parser(
        "accept-candidate",
        help="ingest a HERE Grok Imagine candidate into UP-engine audit layout (alias of generate-candidate --backend here --candidate)",
    )
    accept.add_argument("packet", type=Path)
    accept.add_argument("base", type=Path)
    accept.add_argument("candidate", type=Path)
    accept.add_argument("--out", type=Path, required=True)
    accept.add_argument("--prompt", default=None)
    accept.add_argument("--model-id", default=None)
    accept.add_argument("--request-id", default=None)
    accept.add_argument("--overwrite", action="store_true")

    register = sub.add_parser(
        "assess-registration",
        help="measure whether a candidate matches BASE dimensions (no auto-resize)",
    )
    register.add_argument("base", type=Path)
    register.add_argument("candidate", type=Path)
    register.add_argument("--expected-base-sha256", default=None)

    composite = sub.add_parser(
        "composite-generation",
        help="reconstruct a registered candidate only inside its generation packet mask",
    )
    composite.add_argument("packet", type=Path, help="generation_packet.json")
    composite.add_argument("base", type=Path, help="exact original BASE image")
    composite.add_argument("candidate", type=Path, help="already-registered candidate image")
    composite.add_argument("--out", type=Path, required=True, help="composited candidate PNG path")
    composite.add_argument("--model-id", help="candidate generator/model identifier for the audit")
    composite.add_argument(
        "--require-registration-gate",
        action="store_true",
        help="run registration assessment first and refuse composite if dimensions mismatch",
    )
    composite.add_argument("--overwrite", action="store_true")



    diagnose = sub.add_parser(
        "diagnose-image",
        help="ask Grok Vision to diagnose image defects and create an evidence-aware skill plan",
    )
    diagnose.add_argument("image", type=Path)
    diagnose.add_argument("--out", type=Path, required=True, help="new or empty diagnosis output directory")
    diagnose.add_argument("--identity-reference", type=Path, default=None, help="optional a8b or other canonical identity image")
    diagnose.add_argument("--identity-reference-id", default=None, help="asset ID for the supplied identity reference")
    diagnose.add_argument("--model-id", default=None, help="xAI vision model override; defaults to XAI_VISION_MODEL or grok-4")
    diagnose.add_argument("--detail", choices=("low", "high", "auto"), default="high")
    diagnose.add_argument("--focus", default="Assess structural integrity first, then identity, material detail and image-quality defects.")
    diagnose.add_argument("--checkpoint", type=Path, default=None)
    diagnose.add_argument("--upscaled", type=Path, default=None)
    diagnose.add_argument("--masks", type=Path, default=None)

    ref_search = sub.add_parser(
        "ref-search",
        help="search the reviewed legacy reference snapshot by asset ID, role, tags or skill",
    )
    ref_search.add_argument("--query", default="")
    ref_search.add_argument("--role", default=None)
    ref_search.add_argument("--skill", default=None)
    ref_search.add_argument("--limit", type=int, default=50)
    ref_search.add_argument("--asset-root", type=Path, default=None)

    skill_plan = sub.add_parser(
        "skill-plan",
        help="route an evidence-bearing diagnosis to documented or executable legacy skills",
    )
    skill_plan.add_argument("image", type=Path)
    skill_plan.add_argument("--diagnosis", type=Path, required=True)
    skill_plan.add_argument("--checkpoint", type=Path, default=None)
    skill_plan.add_argument("--upscaled", type=Path, default=None)
    skill_plan.add_argument("--masks", type=Path, default=None)
    skill_plan.add_argument("--method-registry", type=Path, default=None, help="override the packaged Method Registry JSON")
    skill_plan.add_argument("--license-review-acknowledged", action="store_true", help="record explicit checkpoint/license review; does not grant edit permission")
    skill_plan.add_argument("--out", type=Path, default=None)

    upscale = sub.add_parser(
        "upscale-siax",
        help="run the pinned 4x_NMKD-Siax_200k.pth model (optional upscale extra)",
    )
    upscale.add_argument("input", type=Path)
    upscale.add_argument("--checkpoint", type=Path, required=True)
    upscale.add_argument("--out", type=Path, required=True, help="lossless 4x PNG master")
    upscale.add_argument("--tile-size", type=int, default=256)
    upscale.add_argument("--tile-pad", type=int, default=16)
    upscale.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    upscale.add_argument("--confirm-model-license-review", action="store_true")

    detail6 = sub.add_parser(
        "detail6",
        help="apply region-limited DETAIL6 residual to a verified 4x Siax master and export 4:4:4 JPEGs",
    )
    detail6.add_argument("base", type=Path)
    detail6.add_argument("--upscaled", type=Path, required=True)
    detail6.add_argument("--masks", type=Path, required=True)
    detail6.add_argument("--out", type=Path, required=True)
    detail6.add_argument("--gain", type=float, default=0.15)
    detail6.add_argument("--minimum-bytes", type=int, default=6_000_000)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "comfy-cloud-manifest":
        from .comfy.workflow_runtime import create_comfy_cloud_manifest
        import json as _json

        tile_bindings = []
        for item in args.tile:
            if "=" not in item:
                parser.error(f"--tile must be NODE_ID=IMAGE_PATH, got: {item}")
            node_id, image_path = item.split("=", 1)
            if not node_id or not image_path:
                parser.error(f"--tile must have a non-empty node id and image path, got: {item}")
            tile_bindings.append((node_id, image_path))
        try:
            result = create_comfy_cloud_manifest(
                workflow_path=args.workflow,
                tile_bindings=tile_bindings,
                manifest_path=args.out,
                output_dir=args.output_dir,
                run_id=args.run_id,
            )
        except Exception as exc:
            print(f"COMFY_CLOUD_MANIFEST_FAILED: {exc}")
            return 2
        print(_json.dumps(result, ensure_ascii=False, indent=2))
        print(
            f"manifest={result['manifest_path']} sha256={result['manifest_sha256']} "
            f"tiles={len(result['manifest']['tile_inputs'])} diagnostic_only=true"
        )
        return 0

    if args.command == "comfy-cloud-preflight":
        from .comfy.workflow_runtime import preflight_comfy_cloud
        from .comfy.cloud_client import ComfyCloudClient
        import json as _json

        try:
            report = preflight_comfy_cloud(args.manifest, client=ComfyCloudClient())
        except Exception as exc:
            print(f"COMFY_CLOUD_PREFLIGHT_FAILED: {exc}")
            return 2
        rendered = _json.dumps(report, ensure_ascii=False, indent=2) + "\\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
            print(f"Comfy Cloud preflight written: {args.out}")
        else:
            print(rendered, end="")
        audit = report.get("runtime_audit") or {}
        print(
            f"workflow={report.get('workflow_sha256')} cloud={report.get('cloud', {}).get('status')} "
            f"overall={audit.get('overall_status')} blockers={','.join(audit.get('blockers') or []) or 'none'} "
            f"execution_allowed=false"
        )
        return 0 if not audit.get("blockers") else 2

    if args.command == "comfy-cloud-diagnostic":
        from .comfy.workflow_runtime import run_comfy_cloud_diagnostic
        from .comfy.cloud_client import ComfyCloudClient
        import json as _json

        try:
            receipt = run_comfy_cloud_diagnostic(
                args.manifest,
                diagnostic_submit=args.diagnostic_submit,
                client=ComfyCloudClient(),
                timeout_seconds=args.timeout,
                poll_interval_seconds=args.poll_interval,
            )
        except Exception as exc:
            print(f"COMFY_CLOUD_DIAGNOSTIC_FAILED: {exc}")
            return 2
        rendered = _json.dumps(receipt, ensure_ascii=False, indent=2) + "\\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
            print(f"Comfy Cloud diagnostic receipt written: {args.out}")
        else:
            print(rendered, end="")
        print(
            f"prompt_id={receipt['prompt_id']} outputs={len(receipt['output_receipts'])} "
            f"diagnostic_only=true candidate_accepted=false maturity={receipt['maturity_remains']}"
        )
        return 0

    if args.command == "agent-run":
        from .agent_driver import run_agent_manifest_file
        import json as _json

        report = run_agent_manifest_file(
            args.manifest,
            execute=args.execute,
            report_path=args.out,
            registry_path=args.method_registry,
        )
        rendered = _json.dumps(report, ensure_ascii=False, indent=2)
        if args.out is None:
            print(rendered)
        else:
            print(f"Agent run report written: {args.out}")
        stages = report.get("stages") or []
        summary = " | ".join(
            f"{stage.get('stage')}={stage.get('status')}" for stage in stages
        )
        print(
            f"run_id={report.get('run_id')} method={report.get('selected_method')} "
            f"status={report.get('status')} stages={summary} "
            f"execution_allowed={report.get('execution_allowed')} "
            f"edit_permission={report.get('edit_permission')}"
        )
        return 0 if report.get("status") in {"READY_FOR_EXPLICIT_EXECUTION", "S5_COMPLETE_AWAITING_S6_S7"} else 2

    if args.command == "validate-manifest":
        manifest = load_manifest(args.path)
        print(
            f"VALID: task={manifest.task_id} adapter={manifest.adapter_id} "
            f"parent={manifest.parent_asset_id}"
        )
        return 0

    if args.command == "validate-method-registry":
        from .method_registry import MethodRegistry
        registry = MethodRegistry.load(args.path)
        print(
            f"VALID: registry={registry.payload.get('registry_id')} "
            f"version={registry.payload.get('registry_version')} "
            f"methods={len(registry.methods)} policy={registry.payload['policy']} "
            "edit_permission=never-granted"
        )
        return 0

    if args.command == "audit-s0-s7":
        from .method_registry import MethodRegistry, evaluate_s0_s7
        import json as _json

        evidence = _json.loads(args.evidence.read_text(encoding="utf-8"))
        registry = MethodRegistry.load(args.method_registry)
        report = evaluate_s0_s7(evidence, registry)
        rendered = _json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
            print(f"S0-S7 audit written: {args.out}")
        else:
            print(rendered, end="")
        return 0 if report["status"] == "ACCEPTED_CANDIDATE" else 2

    if args.command == "validate-model-inventory":
        from .comfy.model_inventory import (
            backend_model_inventory_verified,
            load_model_inventory,
            summarize_inventory,
        )
        from .comfy.workflow_static_audit import audit_comfy_workflows
        import json as _json

        inventory = load_model_inventory(args.path)
        report = None
        if args.against_ui is not None or args.against_api is not None:
            report = audit_comfy_workflows(
                ui_path=args.against_ui,
                api_path=args.against_api,
                model_inventory_path=args.path,
            )
        result = backend_model_inventory_verified(inventory, static_audit_report=report)
        summary = summarize_inventory(inventory)
        siax = None
        if report is not None:
            siax = (report.get("backend_model_inventory") or {}).get("siax_registry_pin")
        print(
            f"DECLARED_RECORD: inventory_id={summary['inventory_id']} "
            f"version={summary['inventory_version']} assets={summary['asset_count']} "
            f"custom_nodes={summary['custom_node_count']} "
            f"evidence_grade={result.get('evidence_grade')} "
            f"inventory_declared_ok={result.get('inventory_declared_ok')} "
            f"inventory_live_verified={result.get('inventory_live_verified')} "
            f"execution_allowed={result['execution_allowed']}"
        )
        if siax is not None:
            print(
                f"siax_pin={siax.get('status')} matched={siax.get('matched')} "
                f"sha={(siax.get('evidence') or {}).get('inventory_sha256')}"
            )
        if result["blockers"]:
            print("blockers=" + ",".join(result["blockers"]))
        if report is not None:
            print(
                f"merged_audit inventory_status={report['inventory_status']} "
                f"overall={report['overall_status']} execution_allowed={report['execution_allowed']}"
            )
        if not result.get("inventory_declared_ok", result.get("verified")):
            return 2
        if report is not None and report.get("inventory_status") != "PASS_STATIC_INVENTORY":
            return 2
        return 0

    if args.command == "capture-model-inventory":
        from .comfy.model_inventory_capture import (
            CaptureInventoryError,
            capture_model_inventory,
            write_capture_receipt,
            DEFAULT_CHUNK_SIZE,
        )
        import json as _json

        try:
            manifest = None
            if args.manifest is not None:
                manifest = _json.loads(args.manifest.read_text(encoding="utf-8"))
            kwargs = {
                "expect_relative": args.expect_relative,
                "manifest": manifest,
            }
            if args.chunk_size is not None:
                kwargs["chunk_size"] = args.chunk_size
            receipt = capture_model_inventory(args.models_root, **kwargs)
            write_capture_receipt(receipt, args.out)
        except CaptureInventoryError as exc:
            print(f"CAPTURE_FAILED: {exc}")
            return 2
        print(
            f"CAPTURE_OK: evidence_grade={receipt['evidence_grade']} "
            f"receipt_kind={receipt['receipt_kind']} "
            f"host={receipt['host']['hostname']} "
            f"models_root={receipt['models_root']} "
            f"assets={len(receipt['assets'])} "
            f"captured_at={receipt['captured_at']} "
            f"out={args.out} execution_allowed=false"
        )
        for asset in receipt["assets"]:
            print(
                f"  {asset['asset_id']}: {asset['relative_path']} "
                f"size={asset['size_bytes']} sha256={asset['sha256'][:12]}…"
            )
        return 0

    if args.command == "audit-tile-ledger":
        from .comfy.tile_core_halo_ledger import audit_ledger, load_ledger, ledger_passes
        import json as _json

        ledger = load_ledger(args.path)
        report = audit_ledger(ledger)
        rendered = _json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
            print(f"Tile ledger audit written: {args.out}")
        else:
            print(rendered, end="")
        print(
            f"overall={report['overall_status']} blockers={','.join(report.get('blockers') or []) or 'none'} "
            f"execution_allowed={report['execution_allowed']} edit_permission={report['edit_permission']}"
        )
        return 0 if ledger_passes(report) else 2

    if args.command == "audit-comfy-workflow":
        from .comfy.workflow_static_audit import audit_comfy_workflows, structural_inventory_ok
        import json as _json

        if args.ui is None and args.api is None:
            parser.error("audit-comfy-workflow requires --ui and/or --api")
        report = audit_comfy_workflows(
            ui_path=args.ui,
            api_path=args.api,
            model_inventory_path=args.model_inventory,
            capture_receipt_path=getattr(args, "capture_receipt", None),
        )
        rendered = _json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
            print(f"Comfy workflow static audit written: {args.out}")
        else:
            print(rendered, end="")
        backend = report.get("backend_model_inventory") or {}
        backend_status = backend.get("status", "omitted")
        print(
            f"method={report['method_id']} inventory={report['inventory_status']} "
            f"backend_model_inventory={backend_status} "
            f"evidence_grade={backend.get('evidence_grade', 'omitted')} "
            f"inventory_live_verified={backend.get('inventory_live_verified', False)} "
            f"overall={report['overall_status']} execution_allowed={report['execution_allowed']} "
            f"maturity_remains={report['maturity_remains']}"
        )
        return 0 if structural_inventory_ok(report) else 2

    if args.command == "read-image":
        from .read import run_read

        segmentation_provider = None
        if args.provider == "sam3":
            from .read.providers.sam3 import Sam3TextSegmenter
            segmentation_provider = Sam3TextSegmenter()

        visual_reasoner = None
        if args.reasoner == "grok":
            from .read.providers.xai_grok import GrokSpatialReasoner
            visual_reasoner = GrokSpatialReasoner(model_id=args.reasoning_model)
        elif args.reasoner == "qwen":
            from .read.providers.qwen3_vl import QwenSpatialReasoner
            model_id = args.reasoning_model or QwenSpatialReasoner.DEFAULT_MODEL_ID
            visual_reasoner = QwenSpatialReasoner(model_id=model_id)

        report = run_read(
            args.image,
            args.out,
            regions_path=args.regions,
            relations_path=args.relations,
            provider=segmentation_provider,
            prompts=args.prompt,
            reasoner=visual_reasoner,
            reasoning_focus=args.reasoning_focus,
            overwrite=args.overwrite,
        )
        visual = report.get("visual_reasoning", {})
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
            f"Segmentation proposals: {report['semantic_segmentation']['proposal_count']} "
            f"({report['semantic_segmentation']['status']})"
        )
        print(
            f"VLM proposals: {len(visual.get('nodes', []))} regions / "
            f"{len(visual.get('relations', []))} relations "
            f"({visual.get('status', 'not_run')})"
        )
        print(
            f"Human-verified relations: "
            f"{report['scene_graph']['human_verified_relation_count']}"
        )
        return 0

    if args.command == "compile-generation":
        from .read.geometry import compile_generation_packet

        packet = compile_generation_packet(
            args.analysis,
            args.out,
            objective=args.objective,
            target_region_ids=args.target_region,
            base_image_path=args.base,
            overwrite=args.overwrite,
        )
        print(f"Generation packet compiled: {args.out}")
        print(f"BASE SHA256: {packet['base']['sha256']}")
        print(f"Target regions: {', '.join(item['region_id'] for item in packet['targets'])}")
        print(
            f"Authorized pixels: {packet['pixel_authorization']['generation_pixels']} | "
            f"Protected pixels: {packet['pixel_authorization']['protected_pixels']}"
        )
        print(f"Human geometry locks: {len(packet['geometry_locks']['relations'])}")
        return 0

    if args.command == "generate-candidate":
        if args.backend == "here":
            from .adapters.here_imagine import HereImagineAdapter

            adapter = HereImagineAdapter(model_id=args.model_id)
            if args.candidate is None:
                job = adapter.prepare_job(
                    args.packet,
                    args.base,
                    args.out,
                    prompt=args.prompt,
                    aspect_ratio=args.aspect_ratio,
                    overwrite=args.overwrite,
                )
                print(f"HERE Imagine job prepared: {job.job_path}")
                print(f"Prompt: {job.prompt_path}")
                print(f"BASE: {job.base_width}x{job.base_height} sha256={job.base_sha256}")
                print(f"Status: {job.status}")
                print("Next: generate candidate HERE with Grok Imagine tools using BASE + prompt,")
                print("then: ige generate-candidate ... --backend here --candidate <file> --out <dir> --overwrite")
                print("or:  ige accept-candidate <packet> <base> <candidate> --out <dir>")
                return 0

            artifact = adapter.ingest_candidate(
                args.packet,
                args.base,
                args.candidate,
                args.out,
                prompt=args.prompt,
                request_id=args.request_id,
                overwrite=args.overwrite,
            )
            print(f"HERE candidate ingested: {artifact.candidate_path}")
            print(f"Backend: {artifact.backend} model={artifact.model_id}")
            print(f"Candidate SHA256: {artifact.candidate_sha256}")
            print(
                f"Size: candidate {artifact.candidate_width}x{artifact.candidate_height} | "
                f"BASE {artifact.base_width}x{artifact.base_height}"
            )
            print(f"Registration quality: {artifact.registration_quality}")
            print(f"Metadata: {artifact.metadata_path}")
            print("Status: unverified candidate — not accepted, not pixel-preserving by claim")
            return 0

        if args.backend == "xai-api":
            from .adapters.xai_imagine import GrokImagineAdapter

            adapter = GrokImagineAdapter(model_id=args.model_id)
            artifact = adapter.generate_from_packet(
                args.packet,
                args.base,
                args.out,
                prompt=args.prompt,
                aspect_ratio=args.aspect_ratio,
                resolution=args.resolution,
                quality=args.quality,
                overwrite=args.overwrite,
            )
            print(f"xAI API candidate written: {artifact.candidate_path}")
            print(f"Model: {artifact.model_id} request_id={artifact.request_id}")
            print(f"Candidate SHA256: {artifact.candidate_sha256}")
            print(
                f"Size: candidate {artifact.candidate_width}x{artifact.candidate_height} | "
                f"BASE {artifact.base_width}x{artifact.base_height}"
            )
            print(f"Registration quality: {artifact.registration_quality}")
            print(f"Metadata: {artifact.metadata_path}")
            print("Status: unverified candidate — secondary xai-api backend")
            return 0

        parser.error(f"unsupported backend: {args.backend}")
        return 2

    if args.command == "accept-candidate":
        from .adapters.here_imagine import HereImagineAdapter

        adapter = HereImagineAdapter(model_id=args.model_id)
        artifact = adapter.ingest_candidate(
            args.packet,
            args.base,
            args.candidate,
            args.out,
            prompt=args.prompt,
            request_id=args.request_id,
            overwrite=args.overwrite,
        )
        print(f"HERE candidate ingested: {artifact.candidate_path}")
        print(f"Candidate SHA256: {artifact.candidate_sha256}")
        print(f"Registration quality: {artifact.registration_quality}")
        print(f"Metadata: {artifact.metadata_path}")
        return 0

    if args.command == "assess-registration":
        from .adapters.registration import assess_registration
        import json as _json

        report = assess_registration(
            args.base,
            args.candidate,
            expected_base_sha256=args.expected_base_sha256,
        )
        print(_json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if report.allowed_for_compositor else 2

    if args.command == "composite-generation":
        from .reconstruction import composite_candidate

        if args.require_registration_gate:
            from .adapters.registration import require_registration_for_composite
            require_registration_for_composite(args.base, args.candidate)

        audit = composite_candidate(
            args.packet,
            args.base,
            args.candidate,
            args.out,
            candidate_model_id=args.model_id,
            overwrite=args.overwrite,
        )
        print(f"Candidate composited: {args.out}")
        print(
            f"Changed pixels inside mask: "
            f"{audit['pixel_diff']['changed_pixels_inside_authorized_region']}"
        )
        print(
            f"Changed pixels outside mask: "
            f"{audit['pixel_diff']['changed_pixels_outside_authorized_region']}"
        )
        print(
            f"Final acceptance: {audit['final_acceptance']} "
            "(identity, pose, topology and registration checks remain separate)"
        )
        return 0



    if args.command == "diagnose-image":
        from .read.skill_diagnosis import GrokSkillDiagnoser
        from .skill_router import plan_skills
        import json as _json

        if args.identity_reference_id and not args.identity_reference:
            parser.error("--identity-reference-id requires --identity-reference")
        args.out.mkdir(parents=True, exist_ok=True)
        if any(args.out.iterdir()):
            parser.error(f"diagnosis output directory is not empty: {args.out}")
        diagnoser = GrokSkillDiagnoser(model_id=args.model_id, detail=args.detail)
        diagnosis = diagnoser.diagnose(
            args.image,
            identity_reference=args.identity_reference,
            identity_reference_id=args.identity_reference_id,
            focus=args.focus,
        )
        diagnosis_path = args.out / "diagnosis.json"
        diagnosis_path.write_text(
            _json.dumps(diagnosis, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        skill_plan = plan_skills(
            args.image,
            diagnosis_path,
            checkpoint_path=args.checkpoint,
            upscaled_path=args.upscaled,
            masks_path=args.masks,
        )
        plan_path = args.out / "skill_plan.json"
        plan_path.write_text(
            _json.dumps(skill_plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        present = [
            name for name, item in diagnosis["observations"].items()
            if item["state"] == "present"
        ]
        print(f"Grok diagnosis written: {diagnosis_path}")
        print(f"Skill plan written: {plan_path}")
        print(f"Model: {diagnosis['diagnosis_meta']['model_id']} request={diagnosis['diagnosis_meta']['request_id']}")
        print(f"Candidate findings: {', '.join(present) if present else 'none; manual review may be needed'}")
        print(f"Router status: {skill_plan['overall_status']}")
        print("All Grok findings remain candidate; no skill is human-verified or finally accepted.")
        return 0

    if args.command == "ref-search":
        from .references import ReferenceCatalog
        import json as _json

        catalog = ReferenceCatalog.load()
        results = catalog.search(args.query, role=args.role, skill=args.skill, limit=args.limit)
        if args.asset_root:
            for item in results:
                resolved = catalog.inspect(item["asset_id"], asset_root=args.asset_root)
                item.update({"materialization": resolved["materialization"], "local_file": resolved["local_file"]})
        print(_json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if results else 2

    if args.command == "skill-plan":
        from .skill_router import plan_skills
        import json as _json

        report = plan_skills(
            args.image, args.diagnosis, checkpoint_path=args.checkpoint,
            upscaled_path=args.upscaled, masks_path=args.masks,
            method_registry_path=args.method_registry,
            license_review_acknowledged=args.license_review_acknowledged,
        )
        rendered = _json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
            print(f"Skill plan written: {args.out}")
        else:
            print(rendered, end="")
        return 0 if report["overall_status"] == "READY_FOR_EXECUTION" else 2

    if args.command == "upscale-siax":
        from .upscale.siax import run_siax_upscale

        report = run_siax_upscale(
            args.input, args.checkpoint, args.out, tile_size=args.tile_size,
            tile_pad=args.tile_pad,
            confirm_model_license_review=args.confirm_model_license_review,
            device=args.device,
        )
        print(f"Siax 4x master: {report['output_path']}")
        print(f"SHA256: {report['output_sha256']}")
        print(f"Size: {report['output_dimensions']['width']}x{report['output_dimensions']['height']}")
        print(f"Metadata: {report['metadata_path']}")
        print("Status: candidate only; identity/topology/visual gates remain separate")
        return 0

    if args.command == "detail6":
        from .upscale.detail6 import run_detail6
        import json as _json

        report = run_detail6(
            args.base, args.upscaled, args.masks, args.out,
            gain=args.gain, minimum_bytes=args.minimum_bytes,
        )
        print(_json.dumps(report, ensure_ascii=False, indent=2))
        print("Visual quality review:", report["visual_quality_review"])
        print("Note: HF-energy change is diagnostic only, not an acceptance score.")
        return 0 if report["execution_complete"] else 2

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
