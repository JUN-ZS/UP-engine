import unittest

from ige.upscale.siax import allocate_output_canvas


class SiaxCanvasTests(unittest.TestCase):
    def test_4x_output_canvas_is_uint8_rgb(self):
        width, height = 1792, 1008
        canvas = allocate_output_canvas(width, height, scale=4)
        self.assertEqual(canvas.shape, (4032, 7168, 3))
        self.assertEqual(str(canvas.dtype), "uint8")
        self.assertEqual(canvas.nbytes, 7168 * 4032 * 3)
        self.assertLess(canvas.nbytes, width * height * 16 * 3 * 4)

    def test_invalid_output_canvas_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            allocate_output_canvas(0, 100, scale=4)


if __name__ == "__main__":
    unittest.main()
