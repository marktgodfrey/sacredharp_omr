from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from edition_comparison import compare_edition  # noqa: E402


def xml(names, pitches):
    declarations = "".join(
        f'<score-part id="P{i}"><part-name>{name}</part-name></score-part>'
        for i, name in enumerate(names, 1))
    parts = "".join(
        f'<part id="P{i}"><measure number="1"><attributes><divisions>1</divisions>'
        '<time><beats>4</beats><beat-type>4</beat-type></time></attributes>'
        + (f'<note><pitch><step>{step}</step><octave>{octave}</octave></pitch>'
           '<duration>1</duration></note>' if pitch else '')
        + '</measure></part>'
        for i, pitch in enumerate(pitches, 1)
        for step, octave in [pitch or (None, None)])
    return f'<score-partwise><part-list>{declarations}</part-list>{parts}</score-partwise>'


class EditionComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def paths(self, ref, pred):
        a, b = self.root / "ref.xml", self.root / "pred.xml"
        a.write_text(ref); b.write_text(pred)
        return a, b

    def test_three_voice_source_excludes_arbitrary_alto(self):
        ref = xml(["treble", "alto", "tenor", "bass"],
                  [("C", 5), ("F", 4), ("G", 4), ("C", 3)])
        pred = xml(["Bassoon", "Treble", "Alto"],
                   [("C", 5), ("G", 4), ("C", 3)])
        a, b = self.paths(ref, pred)
        result = compare_edition(a, b, ["treble", "tenor", "bass"])
        comp = result["comparison"]
        self.assertEqual(comp["totals"]["pitch_edit_distance"], 0)
        self.assertEqual(comp["time_aware_exact_event_multiset"]["f1"], 1.0)
        self.assertEqual(result["excluded_reference_note_counts"], {"alto": 1})
        self.assertEqual(result["prediction_structure"][1]["line"], "tenor")

    def test_missing_expected_tenor_is_penalized(self):
        ref = xml(["x", "y", "z", "w"], [("C", 5), ("F", 4), ("G", 4), ("C", 3)])
        pred = xml(["x", "z", "w"], [("C", 5), None, ("C", 3)])
        a, b = self.paths(ref, pred)
        result = compare_edition(a, b, ["treble", "tenor", "bass"])
        self.assertTrue(result["comparison"]["per_line"]["tenor"]["missing_line"])
        self.assertGreater(result["comparison"]["totals"]["pitch_edit_distance"], 0)

    def test_extra_prediction_part_is_penalized(self):
        ref = xml(["treble", "alto", "tenor", "bass"],
                  [("C", 5), ("F", 4), ("G", 4), ("C", 3)])
        pred = xml(["a", "b", "c", "d"], [("C", 5), ("G", 4), ("C", 3), ("D", 5)])
        a, b = self.paths(ref, pred)
        result = compare_edition(a, b, ["treble", "tenor", "bass"])
        self.assertTrue(result["comparison"]["per_line"]["part_4"]["extra_line"])

    def test_four_part_comparison_is_unchanged(self):
        names = ["treble", "alto", "tenor", "bass"]
        score = xml(names, [("C", 5), ("F", 4), ("G", 4), ("C", 3)])
        a, b = self.paths(score, score)
        result = compare_edition(a, b, names)
        self.assertEqual(result["comparison"]["totals"]["pitch_edit_distance"], 0)
        self.assertEqual(result["comparison"]["time_aware_exact_event_multiset"]["f1"], 1.0)

    def test_missing_part_list_and_declarations_are_rebuilt(self):
        score = xml(["misleading"], [("C", 5)])
        score = score.replace('<part-list><score-part id="P1"><part-name>misleading</part-name>'
                              '</score-part></part-list>', '')
        a, b = self.paths(score, score)
        result = compare_edition(a, b, ["treble"], reference_voice_order=["treble"])
        self.assertEqual(result["comparison"]["totals"]["pitch_edit_distance"], 0)

    def test_multistaff_edition_absent_line_is_fully_excluded(self):
        ref = xml(["treble", "alto", "tenor", "bass"],
                  [("C", 5), ("F", 4), ("G", 4), ("C", 3)])
        ref = ref.replace('<step>F</step><octave>4</octave></pitch><duration>1</duration></note>',
                          '<step>F</step><octave>4</octave></pitch><duration>1</duration></note>'
                          '<note><pitch><step>A</step><octave>4</octave></pitch>'
                          '<duration>1</duration><staff>2</staff></note>', 1)
        pred = xml(["a", "b", "c"], [("C", 5), ("G", 4), ("C", 3)])
        a, b = self.paths(ref, pred)
        result = compare_edition(a, b, ["treble", "tenor", "bass"])
        self.assertEqual(result["excluded_reference_note_counts"]["alto"], 2)
        self.assertNotIn("alto:staff1", result["comparison"]["per_line"])
        self.assertNotIn("alto:staff2", result["comparison"]["per_line"])


if __name__ == "__main__":
    unittest.main()
