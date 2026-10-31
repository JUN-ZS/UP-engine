import unittest

from ige.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_all_pipeline_commands_are_registered(self):
        parser = build_parser()
        self.assertEqual(parser.prog, "ige")
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
        self.assertEqual(generate_args.resolution, "2k")

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
