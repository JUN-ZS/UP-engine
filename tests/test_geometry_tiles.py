import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ige.generation.geometry_tiles import (
    GeometryTileError,
    audit_tile_observations,
    plan_two_tile_generation,
    stitch_two_tile_cores,
)
from ige.cli import build_parser


class GeometryLockedTileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image_path = self.root / "source.png"
        image = Image.new("RGB", (100, 80), (80, 90, 100))
        image.save(self.image_path)
        self.sha = hashlib.sha256(self.image_path.read_bytes()).hexdigest()
        self.contract_path = self.root / "object_geometry.json"
        contract = {
            "schema_version": "ige-object-geometry/1.0",
            "geometry_status": "human_verified",
            "source": {"sha256": self.sha, "width": 100, "height": 80},
            "object": {
                "id": "hammer-head",
                "bbox_xyxy": [35, 20, 65, 55],
                "polygon_xy": [[35, 25], [42, 20], [58, 20], [65, 25],
                               [65, 50], [58, 55], [42, 55], [35, 50]],
                "landmarks": {
                    "left_end": [35, 37],
                    "center": [50, 37],
                    "right_end": [65, 37],
                },
            },
            "tolerances": {
                "bbox_iou_min": 0.95,
                "silhouette_iou_min": 0.95,
                "landmark_max_px": 1.0,
                "overlap_silhouette_iou_min": 0.95,
                "overlap_landmark_max_px": 1.0,
            },
            "provenance": {"source": "human_annotation"},
        }
        self.contract_path.write_text(json.dumps(contract), encoding="utf-8")
        self.out = self.root / "plan"
        self.plan = plan_two_tile_generation(
            self.image_path, self.contract_path, self.out, split_x=50, overlap_px=12
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_planner_creates_two_crops_with_disjoint_cores_and_shared_context(self):
        left, right = self.plan["tiles"]
        self.assertEqual(left["crop_xyxy"], [0, 0, 62, 80])
        self.assertEqual(right["crop_xyxy"], [38, 0, 100, 80])
        self.assertEqual(left["core_xyxy_global"], [0, 0, 50, 80])
        self.assertEqual(right["core_xyxy_global"], [50, 0, 100, 80])
        self.assertEqual(left["core_xyxy_local"], [0, 0, 50, 80])
        self.assertEqual(right["core_xyxy_local"], [12, 0, 62, 80])
        self.assertEqual(left["object_geometry_local"]["bbox_xyxy"], [35, 20, 62, 55])
        self.assertEqual(right["object_geometry_local"]["bbox_xyxy"], [0, 20, 27, 55])
        self.assertTrue((self.out / "tile_left.png").is_file())
        self.assertTrue((self.out / "tile_right.png").is_file())
        self.assertTrue((self.out / "tile_left.task.json").is_file())
        self.assertTrue((self.out / "tile_right.task.json").is_file())
        self.assertEqual(self.plan["status"], "planned_not_generated")
        self.assertFalse(self.plan["tiles"][0]["object_geometry_local"]["coordinate_frame"] == "global")

    def _perfect_observations(self):
        result = []
        for tile in self.plan["tiles"]:
            geometry = tile["object_geometry_local"]
            result.append({
                "tile_id": tile["tile_id"],
                "bbox_xyxy": geometry["bbox_xyxy"],
                "polygon_xy": geometry["polygon_xy"],
                "landmarks": geometry["landmarks"],
            })
        return {"observations": result}

    def test_exact_geometry_measurements_pass_all_declared_gates(self):
        observations_path = self.root / "observations.json"
        observations_path.write_text(json.dumps(self._perfect_observations()), encoding="utf-8")
        report = audit_tile_observations(self.out / "plan.json", observations_path)
        self.assertEqual(report["status"], "PASS_WITHIN_DECLARED_TOLERANCES")
        self.assertEqual(report["overlap_report"]["silhouette_iou"], 1.0)
        self.assertEqual(report["overlap_report"]["shared_landmark_max_error_px"], 0.0)

    def test_local_tile_shift_fails_even_when_input_plan_is_unchanged(self):
        observations = self._perfect_observations()
        right = observations["observations"][1]
        right["bbox_xyxy"] = [x + 5 if i % 2 == 0 else x for i, x in enumerate(right["bbox_xyxy"])]
        right["polygon_xy"] = [[x + 5, y] for x, y in right["polygon_xy"]]
        right["landmarks"] = {name: [point[0] + 5, point[1]] for name, point in right["landmarks"].items()}
        observations_path = self.root / "shifted.json"
        observations_path.write_text(json.dumps(observations), encoding="utf-8")
        report = audit_tile_observations(self.out / "plan.json", observations_path)
        self.assertEqual(report["status"], "FAIL_OR_INCOMPLETE")
        self.assertEqual(report["tile_reports"][1]["status"], "outside_declared_tolerance")
        self.assertEqual(report["overlap_report"]["status"], "not_evaluated")

    def test_model_candidate_cannot_be_promoted_to_geometry_lock(self):
        raw = json.loads(self.contract_path.read_text(encoding="utf-8"))
        raw["geometry_status"] = "candidate"
        self.contract_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(GeometryTileError, "human_verified"):
            plan_two_tile_generation(
                self.image_path, self.contract_path, self.root / "candidate", split_x=50, overlap_px=12
            )

    def test_source_hash_mismatch_is_rejected(self):
        raw = json.loads(self.contract_path.read_text(encoding="utf-8"))
        raw["source"]["sha256"] = "0" * 64
        self.contract_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(GeometryTileError, "SHA-256"):
            plan_two_tile_generation(
                self.image_path, self.contract_path, self.root / "bad-hash", split_x=50, overlap_px=12
            )

    def test_split_must_cross_global_object_bbox(self):
        with self.assertRaisesRegex(GeometryTileError, "split line to cross"):
            plan_two_tile_generation(
                self.image_path, self.contract_path, self.root / "bad-split", split_x=30, overlap_px=12
            )

    def test_missing_tile_observation_is_incomplete_not_pass(self):
        observations_path = self.root / "one-tile.json"
        observations_path.write_text(
            json.dumps({"observations": self._perfect_observations()["observations"][:1]}),
            encoding="utf-8",
        )
        report = audit_tile_observations(self.out / "plan.json", observations_path)
        self.assertEqual(report["status"], "FAIL_OR_INCOMPLETE")
        self.assertEqual(report["tile_reports"][1]["status"], "incomplete")

    def test_disjoint_core_stitch_reconstructs_canvas_without_blending(self):
        left = self.root / "left_generated.png"
        right = self.root / "right_generated.png"
        Image.new("RGB", (62, 80), (255, 0, 0)).save(left)
        Image.new("RGB", (62, 80), (0, 0, 255)).save(right)
        output = self.root / "stitched.png"
        report = stitch_two_tile_cores(self.out / "plan.json", left, right, output)
        with Image.open(output) as image:
            self.assertEqual(image.size, (100, 80))
            self.assertEqual(image.getpixel((10, 40)), (255, 0, 0))
            self.assertEqual(image.getpixel((49, 40)), (255, 0, 0))
            self.assertEqual(image.getpixel((50, 40)), (0, 0, 255))
            self.assertEqual(image.getpixel((99, 40)), (0, 0, 255))
        self.assertEqual(report["status"], "COMPOSITE_CANDIDATE_NOT_GEOMETRY_ACCEPTED")
        self.assertFalse(report["final_acceptance"])
        self.assertTrue(Path(str(output) + ".audit.json").is_file())

    def test_stitch_rejects_generated_dimensions_that_do_not_match_plan(self):
        left = self.root / "wrong_left.png"
        right = self.root / "right.png"
        Image.new("RGB", (61, 80), (255, 0, 0)).save(left)
        Image.new("RGB", (62, 80), (0, 0, 255)).save(right)
        with self.assertRaisesRegex(GeometryTileError, "no implicit resize"):
            stitch_two_tile_cores(self.out / "plan.json", left, right, self.root / "bad.png")

    def test_cli_parses_plan_and_audit_commands(self):
        parser = build_parser()
        plan_args = parser.parse_args([
            "geometry-tile-plan", "source.png", "contract.json",
            "--out", "tiles", "--split-x", "50", "--overlap-px", "12",
        ])
        self.assertEqual(plan_args.command, "geometry-tile-plan")
        self.assertEqual(plan_args.split_x, 50)
        audit_args = parser.parse_args([
            "geometry-tile-audit", "tiles/plan.json", "observations.json",
            "--out", "audit.json",
        ])
        self.assertEqual(audit_args.command, "geometry-tile-audit")
        stitch_args = parser.parse_args([
            "geometry-tile-stitch", "tiles/plan.json", "left.png", "right.png",
            "--out", "master.png",
        ])
        self.assertEqual(stitch_args.command, "geometry-tile-stitch")

    def test_existing_nonempty_output_is_not_overwritten(self):
        with self.assertRaises(FileExistsError):
            plan_two_tile_generation(
                self.image_path, self.contract_path, self.out, split_x=50, overlap_px=12
            )


if __name__ == "__main__":
    unittest.main()
