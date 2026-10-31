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
        help="call Grok Imagine to produce an unverified candidate from a generation packet + BASE",
    )
    generate.add_argument("packet", type=Path, help="generation_packet.json")
    generate.add_argument("base", type=Path, help="exact original BASE image")
    generate.add_argument("--out", type=Path, required=True, help="candidate output directory")
    generate.add_argument("--prompt", default=None, help="optional full prompt override; otherwise packet-constrained default")
    generate.add_argument("--model-id", default=None, help="Imagine model ID override (or XAI_IMAGINE_MODEL)")
    generate.add_argument("--aspect-ratio", default=None, help="optional Imagine aspect_ratio, e.g. 16:9")
    generate.add_argument("--resolution", default="2k", help="Imagine resolution: 1k or 2k")
    generate.add_argument("--quality", default="medium", help="Imagine quality: low, medium, or auto")
    generate.add_argument("--overwrite", action="store_true")

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

    return parser


def main() -> int:
    parser = build_parser()
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
        print(f"Imagine candidate written: {artifact.candidate_path}")
        print(f"Model: {artifact.model_id} request_id={artifact.request_id}")
        print(f"Candidate SHA256: {artifact.candidate_sha256}")
        print(
            f"Size: candidate {artifact.candidate_width}x{artifact.candidate_height} | "
            f"BASE {artifact.base_width}x{artifact.base_height}"
        )
        print(f"Registration quality: {artifact.registration_quality}")
        print(f"Metadata: {artifact.metadata_path}")
        print("Status: unverified candidate — not accepted, not pixel-preserving by claim")
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

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
