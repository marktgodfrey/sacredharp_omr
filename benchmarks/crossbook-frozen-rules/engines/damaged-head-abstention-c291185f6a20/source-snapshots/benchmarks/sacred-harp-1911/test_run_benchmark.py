"""Failure-path scoring tests for the batch benchmark runner."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from compare_musicxml import parse_score  # noqa: E402
from run_benchmark import collect_outputs, score_variant  # noqa: E402


class FailedPredictionTests(unittest.TestCase):
    def test_collect_outputs_maps_source_stem_to_stable_song_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            suffixes = (".musicxml", ".shapes.musicxml", ".report.json", ".html")
            for suffix in suffixes:
                (out / ("scan-0072" + suffix)).write_text("runtime" + suffix)
            collect_outputs({"id": "parting-hand", "input": "sources/scan-0072.jpg"}, out)
            for suffix in suffixes:
                self.assertEqual((out / ("parting-hand" + suffix)).read_text(), "runtime" + suffix)

    def test_failure_artifact_scores_empty_prediction_and_no_viewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref_path = root / "reference.musicxml"
            ref_path.write_text("""<score-partwise><part-list>
              <score-part id="P1"><part-name>treble</part-name></score-part>
              <score-part id="P2"><part-name>alto</part-name></score-part>
              <score-part id="P3"><part-name>tenor</part-name></score-part>
              <score-part id="P4"><part-name>bass</part-name></score-part>
              </part-list>
              <part id="P1"><measure number="1"><note><pitch><step>C</step><octave>5</octave></pitch><duration>1</duration></note></measure></part>
              <part id="P2"><measure number="1"><note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration></note></measure></part>
              <part id="P3"><measure number="1"><note><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration></note></measure></part>
              <part id="P4"><measure number="1"><note><pitch><step>C</step><octave>3</octave></pitch><duration>1</duration></note></measure></part>
              </score-partwise>""")
            out = root / "predictions"
            out.mkdir()
            (out / "song.failure.json").write_text(json.dumps({
                "variant": "clean_layout", "input": "scan.png",
                "traceback": "Traceback\nRuntimeError: model unavailable",
                "error": "RuntimeError: model unavailable", "elapsed_seconds": 1.25,
            }))
            sample = {"id": "song", "expected_staves": 8, "expected_systems": 2}
            result = score_variant(sample, parse_score(ref_path), "clean_layout", "predictions", root=root)

        self.assertTrue(result["failed"])
        self.assertIsNone(result["prediction_sha256"])
        self.assertIsNone(result["viewer"])
        self.assertEqual(result["runtime"]["staves"], 0)
        self.assertEqual(result["runtime"]["systems"], 0)
        self.assertEqual(result["runtime"]["elapsed_seconds"], 1.25)
        self.assertEqual(result["comparison"]["totals"]["prediction_notes"], 0)
        self.assertEqual(result["comparison"]["totals"]["reference_notes"], 4)
        self.assertEqual(result["comparison"]["totals"]["pitch_duration_edit_distance"], 4)

    def test_missing_prediction_without_failure_artifact_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ref_path = root / "reference.musicxml"
            ref_path.write_text("<score-partwise><part-list/><part id='P1'/></score-partwise>")
            with self.assertRaises(FileNotFoundError):
                score_variant({"id": "song"}, parse_score(ref_path), "default", "out", root=root)


if __name__ == "__main__":
    unittest.main()
