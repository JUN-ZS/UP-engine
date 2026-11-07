import unittest

from ige.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_all_pipeline_commands_are_registered(self):
        parser = build_parser()
        self.assertEqual(parser.prog, "ige")
        registry = parser.parse_args(["validate-method-registry"])
        self.assertEqual(registry.command, "validate-method-registry")
        audit = parser.parse_args(["audit-s0-s7", "evidence.json", "--method-registry", "registry.json", "--out", "audit.json"])
        self.assertEqual(audit.command, "audit-s0-s7")
        self.assertEqual(audit.evidence.name, "evidence.json")
        comfy = parser.parse_args([
            "audit-comfy-workflow",
            "--ui", "ui.json",
            "--api", "api.json",
            "--out", "comfy_audit.json",
        ])
        self.assertEqual(comfy.command, "audit-comfy-workflow")
        self.assertEqual(comfy.ui.name, "ui.json")
        self.assertEqual(comfy.api.name, "api.json")
        read = parser.parse_args([
            "read-image", "source.png", "--out", "runs/read-1",
            "--reasoner", "grok"
        ])
        self.assertEqual(read.command, "read-image")
        self.assertEqual(read.reasoner, "grok")
        self.assertIsNone(read.reasoning_model)

        compile_args = parser.parse_args([
            "compile-generation", "runs/read-1/analysis.json",
            "--out", "runs/task-1",
            "--objective", "retexture armor",
            "--target-region", "armor"
        ])
        self.assertEqual(compile_args.command, "compile-generation")
        self.assertEqual(compile_args.target_region, ["armor"])

        generate_args = parser.parse_args([
            "generate-candidate", "runs/task-1/generation_packet.json",
            "source.png", "--out", "runs/task-1/candidate"
        ])
        self.assertEqual(generate_args.command, "generate-candidate")
        self.assertEqual(generate_args.backend, "here")
        self.assertIsNone(generate_args.candidate)
        self.assertEqual(generate_args.resolution, "2k")

        generate_api = parser.parse_args([
            "generate-candidate", "packet.json", "base.png",
            "--out", "out", "--backend", "xai-api"
        ])
        self.assertEqual(generate_api.backend, "xai-api")

        accept = parser.parse_args([
            "accept-candidate", "packet.json", "base.png", "cand.png",
            "--out", "out"
        ])
        self.assertEqual(accept.command, "accept-candidate")

        register_args = parser.parse_args([
            "assess-registration", "source.png", "candidate.png"
        ])
        self.assertEqual(register_args.command, "assess-registration")

        composite_args = parser.parse_args([
            "composite-generation", "runs/task-1/generation_packet.json",
            "source.png", "candidate.png", "--out", "runs/task-1/result.png",
            "--require-registration-gate"
        ])
        self.assertEqual(composite_args.command, "composite-generation")
        self.assertEqual(composite_args.out.suffix, ".png")
        self.assertTrue(composite_args.require_registration_gate)


        diagnose = parser.parse_args([
            "diagnose-image", "source.png", "--out", "runs/diagnosis",
            "--identity-reference", "a8b.png",
            "--identity-reference-id", "a8b78fe5-2654-4f6f-84e3-c1dfbee61004",
        ])
        self.assertEqual(diagnose.command, "diagnose-image")
        self.assertEqual(diagnose.identity_reference_id, "a8b78fe5-2654-4f6f-84e3-c1dfbee61004")
        diagnose_without_identity = parser.parse_args([
            "diagnose-image", "source.png", "--out", "runs/diagnosis-no-ref"
        ])
        self.assertIsNone(diagnose_without_identity.identity_reference)

        refs = parser.parse_args(["ref-search", "--skill", "DETAIL6"])
        self.assertEqual(refs.command, "ref-search")
        plan = parser.parse_args(["skill-plan", "source.png", "--diagnosis", "diagnosis.json", "--method-registry", "registry.json", "--license-review-acknowledged"])
        self.assertEqual(plan.command, "skill-plan")
        self.assertEqual(plan.method_registry.name, "registry.json")
        self.assertTrue(plan.license_review_acknowledged)
        upscale = parser.parse_args(["upscale-siax", "source.png", "--checkpoint", "s iax.pth", "--out", "4x.png"])
        self.assertEqual(upscale.command, "upscale-siax")
        detail6 = parser.parse_args(["detail6", "source.png", "--upscaled", "4x.png", "--masks", "masks.json", "--out", "detail6"])
        self.assertEqual(detail6.command, "detail6")

    def test_grok_model_id_can_be_overridden(self):
        args = build_parser().parse_args([
            "read-image", "source.png", "--out", "runs/read-1",
            "--reasoner", "grok",
            "--reasoning-model", "grok-4"
        ])
        self.assertEqual(args.reasoning_model, "grok-4")

    def test_deprecated_qwen_still_parseable_for_comparison(self):
        args = build_parser().parse_args([
            "read-image", "source.png", "--out", "runs/read-1",
            "--reasoner", "qwen",
            "--reasoning-model", "Qwen/Qwen3.6-27B"
        ])
        self.assertEqual(args.reasoner, "qwen")
        self.assertEqual(args.reasoning_model, "Qwen/Qwen3.6-27B")
