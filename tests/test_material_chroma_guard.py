import unittest
import numpy as np

from ige.upscale.material_chroma_guard import (
    apply_material_chroma_guard,
    detail6_y_only_residual,
    luma_only_compose,
    to_y_rgb,
)


class MaterialChromaGuardTests(unittest.TestCase):
    def test_luma_only_preserves_lp_chrom_on_metal(self):
        lp = np.zeros((8, 8, 3), dtype=np.float32)
        lp[:] = (180, 180, 180)  # neutral silver
        sr = lp.copy()
        sr[:] = (40, 40, 200)  # navy injection in SR
        mask = np.ones((8, 8), dtype=np.float32)
        out, meta = apply_material_chroma_guard(lp, sr, mask, feather=0.0)
        # Y should track SR brightness roughly; chrom should be near neutral not blue
        y = to_y_rgb(out)
        self.assertTrue(np.all(out[..., 2] <= out[..., 0] + 5))  # B not >> R
        self.assertGreater(meta["metal_pixels"], 0)

    def test_non_metal_keeps_sr(self):
        lp = np.full((4, 4, 3), 100, dtype=np.float32)
        sr = np.full((4, 4, 3), 50, dtype=np.float32)
        sr[..., 2] = 200
        mask = np.zeros((4, 4), dtype=np.float32)
        out, _ = apply_material_chroma_guard(lp, sr, mask, feather=0.0)
        np.testing.assert_allclose(out, sr, atol=1e-3)

    def test_detail6_metal_y_only_does_not_add_blue_chroma(self):
        # source slightly darker blue blotch-ish
        source = np.full((16, 16, 3), 160, dtype=np.float32)
        source[4:12, 4:12] = (80, 80, 140)
        low = np.full_like(source, 150)
        metal = np.zeros((16, 16), dtype=np.float32)
        metal[4:12, 4:12] = 1.0
        other = np.zeros((16, 16), dtype=np.float32)
        out = detail6_y_only_residual(source, low, metal, other, gain=0.5)
        # chrom ratio B/R on metal should stay near source chrom, not explode
        src_b_r = source[8, 8, 2] / (source[8, 8, 0] + 1e-3)
        out_b_r = out[8, 8, 2] / (out[8, 8, 0] + 1e-3)
        self.assertAlmostEqual(src_b_r, out_b_r, places=2)

    def test_detail6_other_mask_still_uses_rgb_residual(self):
        source = np.full((8, 8, 3), 100, dtype=np.float32)
        low = np.full((8, 8, 3), 80, dtype=np.float32)
        metal = np.zeros((8, 8), dtype=np.float32)
        other = np.ones((8, 8), dtype=np.float32)
        out = detail6_y_only_residual(source, low, metal, other, gain=0.5)
        # source + 0.5*(source-low) = 100+10=110
        np.testing.assert_allclose(out.mean(), 110.0, atol=0.5)


if __name__ == "__main__":
    unittest.main()
