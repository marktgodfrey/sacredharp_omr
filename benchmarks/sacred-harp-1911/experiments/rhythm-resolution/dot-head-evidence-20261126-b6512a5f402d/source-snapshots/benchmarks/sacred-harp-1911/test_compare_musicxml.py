"""Small synthetic regressions for the stdlib MusicXML comparator."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compare_musicxml import compare, parse_score  # noqa: E402


PARTS = ("treble", "alto", "tenor", "bass")


def score(notes: tuple[str, ...], *, fifths: int = 0, time: str = "4/4") -> str:
    declarations = "".join(
        f'<score-part id="P{i}"><part-name>{name}</part-name></score-part>'
        for i, name in enumerate(PARTS[:len(notes)], 1)
    )
    beat_count, beat_type = time.split("/")
    body = "".join(
        f'<part id="P{i}"><measure number="1">'
        f'<attributes><divisions>2</divisions><key><fifths>{fifths}</fifths></key>'
        f'<time><beats>{beat_count}</beats><beat-type>{beat_type}</beat-type></time></attributes>'
        f'{part_notes}</measure></part>'
        for i, part_notes in enumerate(notes, 1)
    )
    return f'<score-partwise><part-list>{declarations}</part-list>{body}</score-partwise>'


class CompareMusicXMLTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def parse(self, name: str, xml: str, *, line_names=None):
        path = self.root / name
        path.write_text(xml)
        return parse_score(path, line_names=line_names)

    def test_identical_score_has_zero_edits_and_perfect_exact_f1(self):
        xml = score(tuple(
            '<note><pitch><step>C</step><octave>5</octave></pitch><duration>2</duration></note>'
            for _ in PARTS
        ))
        result = compare(self.parse("ref.xml", xml), self.parse("pred.xml", xml))
        self.assertEqual(result["totals"]["pitch_edit_distance"], 0)
        self.assertEqual(result["totals"]["pitch_duration_edit_distance"], 0)
        self.assertEqual(result["time_aware_exact_event_multiset"]["f1"], 1.0)

    def test_duration_only_error_preserves_pitch_score(self):
        ref = score(tuple(
            '<note><pitch><step>C</step><octave>5</octave></pitch><duration>2</duration></note>'
            for _ in PARTS
        ))
        pred = ref.replace("<duration>2</duration>", "<duration>1</duration>", 1)
        result = compare(self.parse("ref.xml", ref), self.parse("pred.xml", pred))
        self.assertEqual(result["totals"]["pitch_edit_distance"], 0)
        self.assertEqual(result["totals"]["pitch_duration_edit_distance"], 1)
        self.assertLess(result["time_aware_exact_event_multiset"]["f1"], 1.0)

    def test_missing_line_is_penalized(self):
        three_parts = tuple(
            '<note><pitch><step>C</step><octave>5</octave></pitch><duration>2</duration></note>'
            for _ in PARTS[:3]
        )
        full = three_parts + (
            '<note><pitch><step>G</step><octave>2</octave></pitch><duration>2</duration></note>',
        )
        result = compare(self.parse("ref.xml", score(full)),
                         self.parse("pred.xml", score(three_parts)))
        self.assertTrue(result["per_line"]["bass"]["missing_line"])
        self.assertEqual(result["per_line"]["bass"]["pitch_edit_distance"], 1)

    def test_missing_alter_is_natural_even_in_flat_key(self):
        notes = tuple(
            '<note><pitch><step>B</step><octave>4</octave></pitch><duration>2</duration></note>'
            for _ in PARTS
        )
        parsed = self.parse("flat-key.xml", score(notes, fifths=-4))
        self.assertEqual(parsed.lines["treble"][0].pitch, 71)  # B natural, MIDI-style pitch.

    def test_generic_parts_align_to_named_three_part_reference(self):
        pitches = (
            '<note><pitch><step>A</step><octave>4</octave></pitch><duration>2</duration></note>',
            '<note><pitch><step>F</step><octave>4</octave></pitch><duration>2</duration></note>',
            '<note><pitch><step>D</step><octave>3</octave></pitch><duration>2</duration></note>',
        )
        ref_xml = (
            '<score-partwise><part-list>'
            '<score-part id="P1"><part-name>treble</part-name></score-part>'
            '<score-part id="P2"><part-name>tenor</part-name></score-part>'
            '<score-part id="P3"><part-name>bass</part-name></score-part>'
            '</part-list>'
            + ''.join(f'<part id="P{i}"><measure number="1">{note}</measure></part>'
                      for i, note in enumerate(pitches, 1))
            + '</score-partwise>'
        )
        pred_xml = (
            '<score-partwise><part-list>'
            + ''.join(f'<score-part id="P{i}"><part-name>Part {i}</part-name></score-part>'
                      for i in range(1, 4))
            + '</part-list>'
            + ''.join(f'<part id="P{i}"><measure number="1">{note}</measure></part>'
                      for i, note in enumerate(pitches, 1))
            + '</score-partwise>'
        )
        ref = self.parse("three-ref.xml", ref_xml)
        pred = self.parse("three-pred.xml", pred_xml,
                          line_names=[part["line"] for part in ref.summaries])
        result = compare(ref, pred)
        self.assertEqual(result["totals"]["pitch_edit_distance"], 0)
        self.assertEqual(result["totals"]["pitch_duration_edit_distance"], 0)

    def test_extra_generic_part_gets_unique_penalized_line(self):
        notes = tuple(
            '<note><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration></note>'
            for _ in range(4)
        )
        ref_xml = (
            '<score-partwise><part-list>'
            '<score-part id="P1"><part-name>treble</part-name></score-part>'
            '<score-part id="P2"><part-name>tenor</part-name></score-part>'
            '<score-part id="P3"><part-name>bass</part-name></score-part>'
            '</part-list>'
            + ''.join(f'<part id="P{i}"><measure number="1">{note}</measure></part>'
                      for i, note in enumerate(notes[:3], 1))
            + '</score-partwise>'
        )
        pred_xml = (
            '<score-partwise><part-list>'
            + ''.join(f'<score-part id="P{i}"><part-name>Part {i}</part-name></score-part>'
                      for i in range(1, 5))
            + '</part-list>'
            + ''.join(f'<part id="P{i}"><measure number="1">{note}</measure></part>'
                      for i, note in enumerate(notes, 1))
            + '</score-partwise>'
        )
        ref = self.parse("three-ref.xml", ref_xml)
        pred = self.parse("four-pred.xml", pred_xml,
                          line_names=[part["line"] for part in ref.summaries])
        result = compare(ref, pred)
        self.assertTrue(result["per_line"]["part_4"]["extra_line"])
        self.assertEqual(result["per_line"]["part_4"]["pitch_edit_distance"], 1)

    def test_chord_backup_forward_and_persistent_meter(self):
        first = (
            '<note><pitch><step>C</step><octave>5</octave></pitch><duration>2</duration></note>'
            '<note><chord/><pitch><step>E</step><alter>-1</alter><octave>5</octave></pitch><duration>6</duration></note>'
            '<backup><duration>2</duration></backup><forward><duration>2</duration></forward>'
        )
        rest = '<note><pitch><step>D</step><octave>4</octave></pitch><duration>2</duration></note>'
        parts = "".join(
            f'<part id="P{i}"><measure number="1"><attributes><divisions>2</divisions>'
            '<time><beats>3</beats><beat-type>2</beat-type></time></attributes>'
            f'{first if i == 1 else rest}</measure>'
            f'<measure number="2">{rest}</measure></part>'
            for i in range(1, 5)
        )
        declarations = "".join(
            f'<score-part id="P{i}"><part-name>{name}</part-name></score-part>'
            for i, name in enumerate(PARTS, 1)
        )
        parsed = self.parse("timed.xml", f'<score-partwise><part-list>{declarations}</part-list>{parts}</score-partwise>')
        treble = parsed.lines["treble"]
        self.assertEqual(treble[0].onset, treble[1].onset)  # chord tones align
        self.assertEqual(treble[1].duration, 3)  # longer chord member
        self.assertEqual(treble[-1].onset, 6)  # retained 3/2 meter across measures


if __name__ == "__main__":
    unittest.main()
