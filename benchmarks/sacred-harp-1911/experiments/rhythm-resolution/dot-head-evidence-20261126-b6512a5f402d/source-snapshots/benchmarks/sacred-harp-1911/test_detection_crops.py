import unittest
from types import SimpleNamespace

from detection_crops import merge_tile_detections, plan_staff_tiles


class DetectionCropTests(unittest.TestCase):
    def test_tiles_fit_scaled_limit_and_overlap(self):
        staff = SimpleNamespace(x0=5, y0=100, x1=9000, y1=164, sp=16)
        tiles = plan_staff_tiles([staff], (10000, 400), max_tile_side=512)
        self.assertGreater(len(tiles), 1)
        for t in tiles:
            x0, y0, x1, y1 = t["crop"]
            self.assertGreaterEqual(x0, 0); self.assertGreaterEqual(y0, 0)
            self.assertLessEqual(x1, 10000); self.assertLessEqual(y1, 400)
            self.assertLessEqual(max(x1-x0, y1-y0) * t["scale"], 512.01)
        for a, b in zip(tiles, tiles[1:]):
            self.assertGreaterEqual(a["crop"][2] - b["crop"][0], 4 * staff.sp - 1)

    def test_scale_and_tiny_bounds(self):
        staff = SimpleNamespace(x0=0, y0=0, x1=20, y1=20, sp=4)
        tile = plan_staff_tiles([staff], (24, 22), target_spacing=16, max_tile_side=100)[0]
        self.assertEqual(tile["crop"], [0, 0, 24, 22])
        self.assertEqual(tile["scale"], 1.)
        up = plan_staff_tiles([staff], (24, 22), target_spacing=16, max_tile_side=100, max_upscale=2)[0]
        self.assertEqual(up["scale"], 2.)

    def test_global_coordinates_nms_alternatives_and_structure(self):
        base = [{"cls": "clef_g", "conf": .9, "xyxy": [0, 0, 8, 20]},
                {"cls": "note_quarter", "conf": .6, "xyxy": [110, 60, 120, 70]}]
        run = {"crop": [100, 50, 200, 150], "scale": 1., "detections": [
            {"cls": "note_half", "conf": .8, "xyxy": [10, 10, 20, 20], "bbox": [10, 10, 10, 10],
             "attrs": {"stem": "up"}, "attr_p": {"stem": .8}, "attr_dist": {"stem": {"up": .8}}},
            {"cls": "rest_quarter", "conf": .7, "xyxy": [10, 10, 20, 20]},
            {"cls": "barLine", "conf": .99, "xyxy": [1, 1, 3, 30]}]}
        result, diag = merge_tile_detections(base, [run])
        self.assertEqual(len(result), 3)  # note duplicate suppressed; rest alternative retained
        note = next(d for d in result if d["cls"] == "note_half")
        self.assertEqual(note["xyxy"], [110, 60, 120, 70])
        self.assertEqual(note["bbox"], [110, 60, 10, 10])
        self.assertEqual(note["attrs"], {"stem": "up"})
        self.assertEqual(sum(d["cls"] == "barLine" for d in result), 0)
        self.assertEqual(diag["same_family_suppressed"], 1)
        self.assertEqual(diag["structural_ignored"], 1)


if __name__ == "__main__":
    unittest.main()
