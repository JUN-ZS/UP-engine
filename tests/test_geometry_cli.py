from __future__ import annotations

import unittest

from ige.comfy.geometry_cli import build_parser


class GeometryCliTests(unittest.TestCase):
    def test_prepare_preflight_and_run_commands_are_registered(self):
        parser = build_parser()
        prepare = parser.parse_args([
            "prepare", "--workflow", "workflow.json", "--source", "source.png",
            "--canvas", "canvas.png", "--geometry-contract", "s2.json",
            "--approved-mask", "approved.png", "--protected-mask", "protected.png",
            "--tile-plan", "tiles.json", "--output-dir", "runs/run-1",
            "--out", "runs/run-1/manifest.json",
        ])
        self.assertEqual(prepare.command, "prepare")
        preflight = parser.parse_args(["preflight", "runs/run-1/manifest.json"])
        self.assertEqual(preflight.command, "preflight")
        run = parser.parse_args(["run", "runs/run-1/manifest.json", "--permission", "permission.json", "--diagnostic-submit", "--timeout", "900"])
        self.assertEqual(run.command, "run")
        self.assertTrue(run.diagnostic_submit)
        self.assertEqual(run.timeout, 900)


if __name__ == "__main__":
    unittest.main()
