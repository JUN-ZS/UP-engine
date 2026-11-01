import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ige.upscale.distributed import (
    DistributedSiaxError,
    claim_next_task,
    complete_claim,
    prepare_siax_job,
    stitch_siax_job,
)
from ige.upscale.siax import MODEL_SHA256


class DistributedSiaxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.png"
        image = Image.new("RGB", (65, 35))
        pixels = image.load()
        for y in range(35):
            for x in range(65):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
        image.save(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def _plan(self):
        return prepare_siax_job(
            self.source,
            self.root / "job",
            tile_size=32,
            tile_pad=8,
        )

    def test_plan_builds_halo_tiles_and_expected_grid(self):
        manifest = self._plan()
        self.assertEqual(manifest["tiling"]["grid_width"], 3)
        self.assertEqual(manifest["tiling"]["grid_height"], 2)
        self.assertEqual(manifest["tiling"]["task_count"], 6)
        first = manifest["tasks"][0]
        self.assertEqual(first["core_box"], [0, 0, 32, 32])
        self.assertEqual(first["input_box"], [0, 0, 40, 35])
        self.assertEqual(manifest["checkpoint_sha256"], MODEL_SHA256)

    def test_two_workers_claim_disjoint_tasks_and_stitch_complete_canvas(self):
        manifest = self._plan()
        job = self.root / "job"
        claimed = []
        for index in range(manifest["tiling"]["task_count"]):
            worker = "local-a" if index % 2 == 0 else "github-b"
            task = claim_next_task(job, worker)
            self.assertIsNotNone(task)
            claimed.append((worker, task))

        task_ids = [task["task_id"] for _, task in claimed]
        self.assertEqual(len(task_ids), len(set(task_ids)))
        self.assertIsNone(claim_next_task(job, "late-worker"))

        for worker, task in claimed:
            x0, y0, x1, y1 = task["core_box"]
            colour = (x0 % 255, y0 % 255, 77)
            output = Image.new("RGB", ((x1 - x0) * 4, (y1 - y0) * 4), colour)
            complete_claim(
                job,
                worker,
                task,
                output,
                device="cpu-test-double",
                runtime_seconds=0.01,
            )

        output_path = self.root / "stitched.png"
        report = stitch_siax_job(job, output_path)
        self.assertEqual(report["execution"]["completed_tiles"], 6)
        self.assertEqual(report["execution"]["worker_count"], 2)
        self.assertEqual(report["output_dimensions"], {"width": 260, "height": 140})
        self.assertEqual(report["acceptance"], "candidate_only")
        self.assertFalse(report["final_acceptance"])
        with Image.open(output_path) as stitched:
            self.assertEqual(stitched.size, (260, 140))
            self.assertEqual(stitched.mode, "RGB")

    def test_stitch_refuses_incomplete_jobs(self):
        self._plan()
        with self.assertRaises(DistributedSiaxError):
            stitch_siax_job(self.root / "job", self.root / "incomplete.png")

    def test_stitch_detects_modified_tile_output(self):
        manifest = self._plan()
        job = self.root / "job"
        for index, task in enumerate(manifest["tasks"]):
            worker = f"worker-{index}"
            claimed = claim_next_task(job, worker)
            x0, y0, x1, y1 = claimed["core_box"]
            complete_claim(
                job,
                worker,
                claimed,
                Image.new("RGB", ((x1 - x0) * 4, (y1 - y0) * 4), (1, 2, 3)),
                device="cpu-test-double",
                runtime_seconds=0.0,
            )
        first = manifest["tasks"][0]
        tile_path = job / first["output_path"]
        tile_path.write_bytes(tile_path.read_bytes() + b"tamper")
        with self.assertRaises(DistributedSiaxError):
            stitch_siax_job(job, self.root / "tampered.png")

    def test_planner_refuses_nonempty_job_directory(self):
        job = self.root / "job"
        job.mkdir()
        (job / "keep.txt").write_text("do not overwrite", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            prepare_siax_job(self.source, job, tile_size=32, tile_pad=8)


if __name__ == "__main__":
    unittest.main()
