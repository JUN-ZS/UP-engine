import unittest
from ige.router import ModelProfile, RuntimeState, route


class RouterTests(unittest.TestCase):
    def test_untested_model_is_not_selected(self):
        profile = ModelProfile(
            model_id="candidate", supported_tasks=frozenset({"retexture"}),
            supports_masks=True, supports_multi_reference=True, max_resolution_mp=None,
            estimated_vram_gb=None, estimated_latency_seconds=None, local=True,
            license_status="approved", validation_status="untested"
        )
        decision = route("retexture", RuntimeState(), [profile])
        self.assertIsNone(decision.selected_model_id)
        self.assertEqual(decision.rejected["candidate"], "not_benchmarked")
