import unittest
from types import SimpleNamespace

from guided_detection import merge_recovery_detections, plan_recovery_tiles


def fixture():
    syms = [SimpleNamespace(i=1, box=(100, 45, 112, 57), staff=0, bar=2),
            SimpleNamespace(i=2, box=(200, 45, 212, 57), staff=0, bar=2),
            SimpleNamespace(i=3, box=(400, 45, 412, 57), staff=0, bar=2)]
    staff = SimpleNamespace(sp=12., y0=30., y1=78.)
    layout = SimpleNamespace(syms=syms, staves=[staff])
    tok = {1: {"cls": {"v": "rest_half"}, "real": {"p": .95}},
           2: {"cls": {"v": "note_quarter"}, "real": {"p": .2}},
           3: {"cls": {"v": "note_eighth"}, "real": {"p": .9}}}
    rd = SimpleNamespace(layout=layout, tok=tok)
    ver = {1: {"stem_found": True}, 2: {"stem_found": True}, 3: {"stem_found": True}}
    return rd, ver


class GuidedDetectionTests(unittest.TestCase):
    def test_plans_grouped_bounded_native_tiles_and_uses_original_conflict_score(self):
        rd, ver = fixture()
        rd.tok[2]["real"]["conflict_original_p"] = .2
        tiles = plan_recovery_tiles(rd, (500, 120), ver)
        self.assertEqual(len(tiles), 1)  # same staff/bar heads share the bounded crop
        self.assertEqual(tiles[0]["head_ids"], [1, 2])
        self.assertEqual(tiles[0]["scale"], 1.)
        self.assertEqual(tiles[0]["staff_index"], 0)
        self.assertEqual(tiles[0]["bar_index"], 2)
        self.assertEqual(tiles[0]["crop"], [4, 0, 308, 114])

    def test_merge_only_verified_note_heads_and_keep_duration_alternatives(self):
        rd, ver = fixture()
        base = [{"cls": "rest_half", "conf": .8, "xyxy": [99, 44, 113, 58]},
                {"cls": "clef_g", "conf": .99, "xyxy": [0, 0, 20, 20]}]
        run = {"crop": [90, 30, 230, 90], "scale": 1., "detections": [
            {"cls": "note_half", "conf": .7, "xyxy": [10, 15, 22, 27]},
            {"cls": "note_quarter", "conf": .9, "xyxy": [10, 15, 22, 27]},
            {"cls": "rest_quarter", "conf": .99, "xyxy": [10, 15, 22, 27]},
            {"cls": "note_eighth", "conf": .99, "xyxy": [60, 15, 72, 27]},
            {"cls": "note_eighth", "conf": .99, "xyxy": [50, 15, 62, 27]},
            {"cls": "note_half", "conf": .99, "xyxy": [-14, 9, 36, 33]}]}
        merged, diag = merge_recovery_detections(base, [run], rd, ver)
        self.assertEqual(len(merged), 3)  # original rest + structure + verified note proposal
        self.assertEqual(sum(d["cls"] == "clef_g" for d in merged), 1)
        self.assertEqual(merged[-1]["xyxy"], [100., 45., 112., 57.])
        self.assertEqual(len(diag["duration_alternatives"]), 2)
        self.assertEqual(len(diag["accepted_proposals"]), 2)
        self.assertEqual(diag["same_family_suppressed"], 1)
        self.assertEqual(diag["ignored_non_note"], 1)
        self.assertGreaterEqual(diag["rejected_unverified_or_geometry"], 2)

    def test_no_pitch_or_rest_proposals_are_created(self):
        rd, ver = fixture()
        merged, diag = merge_recovery_detections([], [{"crop": [90, 30, 130, 80], "detections": [
            {"cls": "rest_quarter", "conf": .99, "xyxy": [10, 15, 22, 27]}]}], rd, ver)
        self.assertEqual(merged, [])
        self.assertEqual(diag["accepted_proposals"], [])
        self.assertEqual(diag["ignored_non_note"], 1)

    def test_scaled_tile_boxes_return_to_source_coordinates(self):
        rd, ver = fixture()
        merged, _ = merge_recovery_detections([], [{"crop": [90, 30, 130, 80], "scale": .5,
            "detections": [{"cls": "note_half", "conf": .8, "xyxy": [10, 15, 22, 27],
                            "bbox": [10, 15, 12, 12]}]}], rd, ver)
        self.assertEqual(merged[0]["xyxy"], [100., 45., 112., 57.])
        self.assertEqual(merged[0]["bbox"], [100., 45., 12., 12.])


if __name__ == "__main__":
    unittest.main()
