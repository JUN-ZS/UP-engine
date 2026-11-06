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

    dist_plan = sub.add_parser(
        "siax-distribute-plan",
        help="prepare a shared filesystem queue of halo-padded Siax 4x tile tasks",
    )
    dist_plan.add_argument("input", type=Path)
    dist_plan.add_argument("--job-dir", type=Path, required=True)
    dist_plan.add_argument("--tile-size", type=int, default=128)
    dist_plan.add_argument("--tile-pad", type=int, default=8)

    dist_worker = sub.add_parser(
        "siax-distribute-worker",
        help="claim and process queued Siax tiles; each process loads the model once",
    )
    dist_worker.add_argument("job_dir", type=Path)
    dist_worker.add_argument("--checkpoint", type=Path, required=True)
    dist_worker.add_argument("--worker-id", default=None)
    dist_worker.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    dist_worker.add_argument("--max-tasks", type=int, default=None)
    dist_worker.add_argument("--confirm-model-license-review", action="store_true")

    dist_stitch = sub.add_parser(
        "siax-distribute-stitch",
        help="verify tile receipts and stitch the distributed Siax 4x PNG master",
    )
    dist_stitch.add_argument("job_dir", type=Path)
    dist_stitch.add_argument("--out", type=Path, required=True)

    geometry_plan = sub.add_parser(
        "geometry-tile-plan",
        help="plan two overlapping high-resolution generation tiles from a human-verified global object contract",
    )
    geometry_plan.add_argument("source_image", type=Path)
    geometry_plan.add_argument("contract", type=Path, help="ige-object-geometry/1.0 JSON")
    geometry_plan.add_argument("--out", type=Path, required=True)
    geometry_plan.add_argument("--split-x", type=int, required=True, help="global canvas x-coordinate crossed by the object")
    geometry_plan.add_argument("--overlap-px", type=int, required=True, help="shared context width on each side of split_x")

    geometry_audit = sub.add_parser(
        "geometry-tile-audit",
        help="audit measured geometry from two generated tiles against the global contract and overlap",
    )
    geometry_audit.add_argument("plan", type=Path, help="plan.json produced by geometry-tile-plan")
    geometry_audit.add_argument("observations", type=Path, help="JSON containing per-tile local bbox, polygon and landmarks")
    geometry_audit.add_argument("--out", type=Path, required=True, help="audit JSON output")

    geometry_stitch = sub.add_parser(
        "geometry-tile-stitch",
        help="reconstruct a candidate by copying only the two disjoint planned tile cores",
    )
    geometry_stitch.add_argument("plan", type=Path)
    geometry_stitch.add_argument("left_generated", type=Path)
    geometry_stitch.add_argument("right_generated", type=Path)
    geometry_stitch.add_argument("--out", type=Path, required=True)

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

    if args.command == "siax-distribute-plan":
        from .upscale.distributed import prepare_siax_job
        import json as _json

        manifest = prepare_siax_job(
            args.input, args.job_dir, tile_size=args.tile_size, tile_pad=args.tile_pad
        )
        print(_json.dumps({
            "job_id": manifest["job_id"],
            "job_dir": str(args.job_dir.resolve()),
            "tile_count": manifest["tiling"]["task_count"],
            "grid": [manifest["tiling"]["grid_width"], manifest["tiling"]["grid_height"]],
            "base_rgb_sha256": manifest["source"]["base_rgb_sha256"],
            "checkpoint_sha256": manifest["checkpoint_sha256"],
            "status": "planned",
        }, ensure_ascii=False, indent=2))
        return 0

    if args.command == "siax-distribute-worker":
        from .upscale.distributed import run_siax_worker
        import json as _json

        if args.max_tasks is not None and args.max_tasks < 1:
            parser.error("--max-tasks must be >= 1")
        report = run_siax_worker(
            args.job_dir, args.checkpoint, worker_id=args.worker_id,
            device=args.device, max_tasks=args.max_tasks,
            confirm_model_license_review=args.confirm_model_license_review,
        )
        print(_json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.command == "siax-distribute-stitch":
        from .upscale.distributed import stitch_siax_job
        import json as _json

        report = stitch_siax_job(args.job_dir, args.out)
        print(_json.dumps(report, ensure_ascii=False, indent=2))
        print("Status: candidate only; no identity/topology/perceptual acceptance is implied.")
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

    if args.command == "geometry-tile-plan":
        from .generation.geometry_tiles import plan_two_tile_generation
        import json as _json

        plan = plan_two_tile_generation(
            args.source_image,
            args.contract,
            args.out,
            split_x=args.split_x,
            overlap_px=args.overlap_px,
        )
        print(_json.dumps({
            "plan": str((args.out / "plan.json").resolve()),
            "status": plan["status"],
            "source_sha256": plan["source"]["sha256"],
            "canvas": [plan["source"]["width"], plan["source"]["height"]],
            "tile_count": len(plan["tiles"]),
            "tiles": [
                {"tile_id": tile["tile_id"], "crop_xyxy": tile["crop_xyxy"],
                 "core_xyxy_global": tile["core_xyxy_global"], "image": tile["image_path"],
                 "task": tile["task_path"]}
                for tile in plan["tiles"]
            ],
            "generator_state": plan["generator"]["state"],
        }, ensure_ascii=False, indent=2))
        return 0

    if args.command == "geometry-tile-audit":
        from .generation.geometry_tiles import audit_tile_observations
        import json as _json

        report = audit_tile_observations(args.plan, args.observations)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(_json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(_json.dumps({
            "audit": str(args.out.resolve()),
            "status": report["status"],
            "tile_statuses": [item["status"] for item in report["tile_reports"]],
            "overlap": report["overlap_report"]["status"],
        }, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS_WITHIN_DECLARED_TOLERANCES" else 2

    if args.command == "geometry-tile-stitch":
        from .generation.geometry_tiles import stitch_two_tile_cores
        import json as _json

        report = stitch_two_tile_cores(
            args.plan, args.left_generated, args.right_generated, args.out
        )
        print(_json.dumps({
            "output": report["output_path"],
            "sha256": report["output_sha256"],
            "status": report["status"],
            "ownership": report["ownership"],
            "geometry_audit": report["geometry_audit"],
        }, ensure_ascii=False, indent=2))
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
