import unittest

from ige.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_all_pipeline_commands_are_registered(self):
        parser = build_parser()
        self.assertEqual(parser.prog, "ige")
        read = parser.parse_args([
            "read-image", "source.png", "--out", "runs/read-1",
            "--reasoner", "qwen"
        ])
        self.assertEqual(read.command, "read-image")
        self.assertEqual(read.reasoner, "qwen")
        self.assertIsNone(read.reasoning_model)

        compile_args = parser.parse_args([
            "compile-generation", "runs/read-1/analysis.json",
            "--out", "runs/task-1",
            "--objective", "retexture armor",
            "--target-region", "armor"
        ])
        self.assertEqual(compile_args.command, "compile-generation")
        self.assertEqual(compile_args.target_region, ["armor"])

        composite_args = parser.parse_args([
            "composite-generation", "runs/task-1/generation_packet.json",
            "source.png", "candidate.png", "--out", "runs/task-1/result.png"
        ])
        self.assertEqual(composite_args.command, "composite-generation")
        self.assertEqual(composite_args.out.suffix, ".png")

    def test_qwen_model_id_can_be_overridden(self):
        args = build_parser().parse_args([
            "read-image", "source.png", "--out", "runs/read-1",
            "--reasoner", "qwen",
            "--reasoning-model", "Qwen/Qwen3.6-27B"
        ])
        self.assertEqual(args.reasoning_model, "Qwen/Qwen3.6-27B")
