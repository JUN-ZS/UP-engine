import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ige.skill_router import plan_skills


class SkillRouterTests(unittest.TestCase):
    def _inputs(self, root: Path, observations):
        image = root / "base.png"
        Image.new("RGB", (32, 24), "gray").save(image)
        diagnosis = root / "diagnosis.json"
        diagnosis.write_text(json.dumps({"diagnosis_version": "1.0", "image": {}, "observations": observations}), encoding="utf-8")
        return image, diagnosis

    def test_raster_only_does_not_guess_semantic_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            image, diagnosis = self._inputs(Path(directory), {})
            plan = plan_skills(image, diagnosis)
            self.assertEqual(plan["overall_status"], "REVIEW_REQUIRED")
            self.assertEqual(plan["steps"][0]["status"], "insufficient_semantic_evidence")
            portfolio = plan["strategy_portfolio"]
            self.assertEqual(portfolio["selection_mode"], "state_dependent_portfolio_not_single_fixed_method")
            self.assertGreaterEqual(len(portfolio["strategies"]), 12)
            self.assertTrue(all(item["execution_performed"] is False for item in portfolio["strategies"]))

    def test_topology_error_blocks_detail_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            observations = {
                "topology_error": {"state":"present", "evidence":"handle/head connectivity visibly broken", "source":"human", "verification":"human_verified"},
                "metal_detail_low": {"state":"present", "evidence":"mesh detail unresolved", "source":"human", "verification":"human_verified"}
            }
            image, diagnosis = self._inputs(Path(directory), observations)
            plan = plan_skills(image, diagnosis)
            self.assertEqual(plan["overall_status"], "BLOCKED")
            strategies = {item["strategy_id"]: item for item in plan["strategy_portfolio"]["strategies"]}
            self.assertEqual(strategies["CNN_GAN_SR"]["eligibility"], "blocked_until_topology_repaired")
            detail = [step for step in plan["steps"] if step["skill"] == "DETAIL6"][0]
            self.assertEqual(detail["status"], "blocked_by_upstream_topology")

    def test_model_candidate_does_not_authorize_skill_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            observations = {"metal_detail_low": {"state":"present", "evidence":"Grok suggests mesh detail may be soft", "source":"grok_vision", "verification":"candidate"}}
            image, diagnosis = self._inputs(Path(directory), observations)
            plan = plan_skills(image, diagnosis)
            self.assertEqual(plan["overall_status"], "REVIEW_REQUIRED")
            self.assertTrue(all(step["status"] == "review_required" for step in plan["steps"]))

    def test_detail6_partial_path_keeps_unmigrated_grid_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, diagnosis = self._inputs(root, {
                "metal_detail_low": {
                    "state": "present",
                    "evidence": "metal weave requires detail restoration",
                    "source": "human",
                    "verification": "human_verified"
                }
            })
            upscaled = root / "upscaled.png"
            masks = root / "masks.json"
            upscaled.write_bytes(b"fixture")
            masks.write_text("{}", encoding="utf-8")
            plan = plan_skills(image, diagnosis, upscaled_path=upscaled, masks_path=masks)
            detail = [step for step in plan["steps"] if step["skill"] == "DETAIL6"][0]
            self.assertEqual(detail["execution"], "partial")
            self.assertEqual(detail["status"], "partial_execution_review_required")
            siax = [step for step in plan["steps"] if step["skill"] == "SIAX4X"][0]
            grid = [step for step in plan["steps"] if step["skill"] == "GRID_SIAX"][0]
            self.assertEqual(siax["status"], "upscaled_master_available")
            self.assertEqual(grid["status"], "blocked_not_imported")
            self.assertEqual(plan["overall_status"], "BLOCKED")
    def test_verified_metal_defect_requires_real_4x_and_masks(self):
        with tempfile.TemporaryDirectory() as directory:
            observations = {"metal_detail_low": {"state":"present", "evidence":"metal weave is visibly unresolved", "source":"human", "verification":"human_verified"}}
            image, diagnosis = self._inputs(Path(directory), observations)
            plan = plan_skills(image, diagnosis)
            detail = [step for step in plan["steps"] if step["skill"] == "DETAIL6"][0]
            self.assertEqual(detail["status"], "blocked_missing_4x_master_or_masks")


if __name__ == "__main__":
    unittest.main()
