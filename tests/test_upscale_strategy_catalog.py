import unittest

from ige.upscale.strategy_catalog import build_strategy_portfolio


def obs(state="present", verification="human_verified", evidence="visible evidence"):
    return {"state": state, "verification": verification, "evidence": evidence}


class UpscaleStrategyPortfolioTests(unittest.TestCase):
    def test_portfolio_exposes_distinct_method_families_not_only_model_names(self):
        result = build_strategy_portfolio({
            "metal_detail_low": obs(),
            "face_detail_low": obs(),
        })
        ids = {item["strategy_id"] for item in result["strategies"]}
        self.assertGreaterEqual(len(ids), 12)
        for expected in (
            "RESAMPLE_CONTROL", "CLASSICAL_RESTORATION", "MULTISCALE_FREQUENCY_ENHANCEMENT", "CNN_GAN_SR",
            "TRANSFORMER_SR", "DIFFUSION_SR", "IDENTITY_GUIDED_FACE_RESTORATION",
            "REFERENCE_GUIDED_SR", "NATIVE_GENERATIVE_REDETAIL", "ROI_HYBRID",
            "TEMPORAL_MULTI_FRAME_SR", "GEOMETRY_GUIDED_SR",
        ):
            self.assertIn(expected, ids)

    def test_identity_reference_is_not_counted_as_generic_texture_donor(self):
        result = build_strategy_portfolio(
            {"metal_detail_low": obs()},
            references=[{"role": "identity_reference", "asset_id": "a8b", "availability": "local_verified"}],
        )
        self.assertEqual(result["context"]["identity_reference_count"], 1)
        self.assertEqual(result["context"]["verified_detail_donor_count"], 0)
        refsr = next(x for x in result["strategies"] if x["strategy_id"] == "REFERENCE_GUIDED_SR")
        face = next(x for x in result["strategies"] if x["strategy_id"] == "IDENTITY_GUIDED_FACE_RESTORATION")
        self.assertEqual(refsr["eligibility"], "blocked_no_verified_detail_donor")
        self.assertEqual(face["eligibility"], "conditional_not_selected")

    def test_a8b_can_select_identity_guided_face_path_when_face_defect_is_present(self):
        result = build_strategy_portfolio(
            {"face_detail_low": obs()},
            references=[{"role": "identity_reference", "asset_id": "a8b", "availability": "local_verified"}],
        )
        face = next(x for x in result["strategies"] if x["strategy_id"] == "IDENTITY_GUIDED_FACE_RESTORATION")
        self.assertEqual(face["eligibility"], "candidate_not_imported")

    def test_verified_material_donor_selects_reference_guided_family(self):
        result = build_strategy_portfolio(
            {"metal_detail_low": obs()},
            references=[{"role": "armor_detail_donor", "asset_id": "metal-donor-1", "availability": "local_verified"}],
        )
        self.assertEqual(result["context"]["verified_detail_donor_count"], 1)
        refsr = next(x for x in result["strategies"] if x["strategy_id"] == "REFERENCE_GUIDED_SR")
        self.assertEqual(refsr["eligibility"], "candidate_not_imported")

    def test_temporal_strategy_requires_compatible_registered_frames(self):
        unregistered = build_strategy_portfolio(
            {"metal_detail_low": obs()},
            context={"frame_count": 3, "frames_registered": False},
        )
        temporal = next(x for x in unregistered["strategies"] if x["strategy_id"] == "TEMPORAL_MULTI_FRAME_SR")
        self.assertEqual(temporal["eligibility"], "blocked_frames_not_registered")
        registered = build_strategy_portfolio(
            {"metal_detail_low": obs()},
            context={"frame_count": 3, "frames_registered": True},
        )
        temporal = next(x for x in registered["strategies"] if x["strategy_id"] == "TEMPORAL_MULTI_FRAME_SR")
        self.assertEqual(temporal["eligibility"], "candidate_not_imported")

    def test_topology_error_blocks_detail_methods_but_preserves_control(self):
        result = build_strategy_portfolio({"topology_error": obs()})
        by_id = {x["strategy_id"]: x for x in result["strategies"]}
        self.assertEqual(by_id["RESAMPLE_CONTROL"]["eligibility"], "control_only")
        self.assertEqual(by_id["CNN_GAN_SR"]["eligibility"], "blocked_until_topology_repaired")
        self.assertEqual(by_id["DIFFUSION_SR"]["eligibility"], "blocked_until_topology_repaired")

    def test_degradation_diagnosis_selects_classical_restoration_separately(self):
        result = build_strategy_portfolio({"motion_blur": obs()})
        classical = next(x for x in result["strategies"] if x["strategy_id"] == "CLASSICAL_RESTORATION")
        self.assertEqual(classical["eligibility"], "candidate_after_review")

    def test_existing_4x_master_is_reused_without_requiring_checkpoint(self):
        result = build_strategy_portfolio(
            {"metal_detail_low": obs()},
            has_siax_checkpoint=False,
            has_4x_master=True,
        )
        cnn = next(x for x in result["strategies"] if x["strategy_id"] == "CNN_GAN_SR")
        self.assertTrue(any("reuse it" in line for line in cnn["reasons"]))

    def test_reference_uuid_without_materialized_bytes_does_not_enable_identity_method(self):
        result = build_strategy_portfolio(
            {"face_detail_low": obs()},
            references=[{"role": "identity_reference", "asset_id": "a8b78fe5"}],
        )
        self.assertEqual(result["context"]["identity_reference_count"], 0)
        face = next(x for x in result["strategies"] if x["strategy_id"] == "IDENTITY_GUIDED_FACE_RESTORATION")
        self.assertEqual(face["eligibility"], "blocked_no_identity_reference")

    def test_microcontrast_context_selects_frequency_method_without_sr_claim(self):
        result = build_strategy_portfolio(
            {"metal_detail_low": obs()},
            context={"local_contrast_deficit": True},
        )
        method = next(x for x in result["strategies"] if x["strategy_id"] == "MULTISCALE_FREQUENCY_ENHANCEMENT")
        self.assertEqual(method["eligibility"], "candidate_after_review")
        self.assertEqual(method["detail_recovery"], "existing_signal_only")

    def test_portfolio_does_not_run_or_accept_any_candidate(self):
        result = build_strategy_portfolio({"metal_detail_low": obs()})
        self.assertTrue(all(x["execution_performed"] is False for x in result["strategies"]))
        self.assertTrue(all(x["final_acceptance"] is False for x in result["strategies"]))


if __name__ == "__main__":
    unittest.main()
