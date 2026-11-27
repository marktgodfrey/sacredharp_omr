#!/usr/bin/env python3
"""Compare written Sacred Harp MusicXML note events, without performance edits."""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

LINES = ("treble", "alto", "tenor", "bass")
STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def q(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _line_name(name: str, ordinal: int, line_names: list[str] | None = None) -> str:
    lower = name.strip().lower()
    for key in LINES:
        if key in lower:
            return key
    if re.fullmatch(r"(?:part\s*\d*|p\d*)", lower) and line_names is not None:
        return line_names[ordinal] if ordinal < len(line_names) else f"part_{ordinal + 1}"
    return LINES[ordinal] if ordinal < len(LINES) else f"part_{ordinal + 1}"


@dataclass(frozen=True)
class Event:
    part_order: int
    onset: Fraction
    pitch: int
    duration: Fraction


@dataclass
class Parsed:
    lines: dict[str, list[Event]]
    summaries: list[dict]
    rests: int
    graces: int
    measures: int


def parse_score(path: Path, *, line_names: list[str] | None = None) -> Parsed:
    root = ET.parse(path).getroot()
    part_names = {
        p.get("id", ""): p.findtext("part-name", default=p.get("id", "part"))
        for p in root.findall("./part-list/score-part")
    }
    lines: dict[str, list[Event]] = {}
    summaries = []
    rests = graces = measures = 0
    for part_index, part in enumerate(root.findall("part")):
        part_id = part.get("id", "")
        name = part_names.get(part_id, part_id or f"part {part_index + 1}")
        line = _line_name(name, part_index, line_names)
        by_staff: dict[str, list[Event]] = {}
        cursor = Fraction(0)
        part_time = Fraction(0)
        divisions = 1
        fifths = 0
        key_summary = "unknown"
        time_summary = "unknown"
        nominal_measure = None
        part_measures = 0
        for measure in part.findall("measure"):
            measures += 1
            part_measures += 1
            cursor = Fraction(0)
            last_note_onset = Fraction(0)
            max_cursor = Fraction(0)
            measure_nominal = nominal_measure
            for child in measure:
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "attributes":
                    value = child.findtext("divisions")
                    if value:
                        divisions = int(value)
                    fifths_text = child.findtext("./key/fifths")
                    if fifths_text is not None:
                        fifths = int(fifths_text)
                        mode = child.findtext("./key/mode", default="major")
                        key_summary = f"{fifths:+d} fifths {mode}"
                    beats, beat_type = child.findtext("./time/beats"), child.findtext("./time/beat-type")
                    if beats and beat_type:
                        time_summary = f"{beats}/{beat_type}"
                        try:
                            beat_count = sum(int(part) for part in beats.split("+"))
                            nominal_measure = Fraction(beat_count * 4, int(beat_type))
                            measure_nominal = nominal_measure
                        except ValueError:
                            nominal_measure = measure_nominal = None
                elif tag in ("backup", "forward"):
                    amount = Fraction(int(child.findtext("duration", default="0")), divisions)
                    cursor += amount if tag == "forward" else -amount
                    max_cursor = max(max_cursor, cursor)
                elif tag == "note":
                    if child.find("grace") is not None:
                        graces += 1
                        continue
                    dur = Fraction(int(child.findtext("duration", default="0")), divisions)
                    is_chord = child.find("chord") is not None
                    onset = last_note_onset if is_chord else cursor
                    if not is_chord:
                        last_note_onset = cursor
                    max_cursor = max(max_cursor, onset + dur)
                    if child.find("rest") is not None:
                        rests += 1
                    else:
                        pitch_node = child.find("pitch")
                        if pitch_node is not None:
                            step = pitch_node.findtext("step", default="C")
                            octave = int(pitch_node.findtext("octave", default="4"))
                            alter_text = pitch_node.findtext("alter")
                            # In MusicXML, <pitch><alter> is the resolved pitch.
                            # An absent alter means natural regardless of key signature
                            # or earlier accidentals in the measure.
                            alter = int(Fraction(alter_text)) if alter_text else 0
                            pitch = (octave + 1) * 12 + STEP[step] + alter
                            staff = child.findtext("staff", default="1")
                            by_staff.setdefault(staff, []).append(Event(part_index + 1, part_time + onset, pitch, dur))
                    if not is_chord:
                        cursor += dur
                        max_cursor = max(max_cursor, cursor)
            # Regular measures retain the last declared meter even when the time
            # element is omitted. An implicit pickup advances only by its actual
            # encoded content, not by the full nominal meter.
            advance = max_cursor if measure.get("implicit") == "yes" else max(max_cursor, measure_nominal or Fraction(0))
            part_time += advance
        # A part with multiple staves produces independently scoreable lines.
        for staff, events in sorted(by_staff.items(), key=lambda item: int(item[0]) if item[0].isdigit() else item[0]):
            key = line if len(by_staff) == 1 else f"{line}:staff{staff}"
            lines.setdefault(key, []).extend(events)
        summaries.append({"part_order": part_index + 1, "part_id": part_id,
                          "part_name": name, "line": line, "key": key_summary,
                          "time": time_summary, "measures": part_measures,
                          "notes": sum(map(len, by_staff.values()))})
    for events in lines.values():
        events.sort(key=lambda e: (e.onset, e.pitch, e.duration))
    return Parsed(lines, summaries, rests, graces, measures)


def levenshtein(a, b) -> int:
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def compare(reference: Parsed, prediction: Parsed) -> dict:
    keys = list(LINES)
    for parsed in (reference, prediction):
        for key in parsed.lines:
            if key not in keys:
                keys.append(key)
    per_line = {}
    pitch_edits = duration_edits = pitch_den = duration_den = 0
    for key in keys:
        ref, pred = reference.lines.get(key, []), prediction.lines.get(key, [])
        pd = levenshtein([e.pitch for e in ref], [e.pitch for e in pred])
        dd = levenshtein([(e.pitch, e.duration) for e in ref], [(e.pitch, e.duration) for e in pred])
        denom = max(len(ref), len(pred))
        pitch_edits += pd; duration_edits += dd
        pitch_den += denom; duration_den += denom
        per_line[key] = {"reference_notes": len(ref), "prediction_notes": len(pred),
                         "pitch_edit_distance": pd,
                         "pitch_error_rate": pd / denom if denom else 0.0,
                         "pitch_duration_edit_distance": dd,
                         "pitch_duration_error_rate": dd / denom if denom else 0.0,
                         "missing_line": bool(ref) and not pred,
                         "extra_line": bool(pred) and not ref}
    ref_events = Counter((e.part_order, e.onset, e.pitch, e.duration)
                         for line, events in reference.lines.items() for e in events)
    pred_events = Counter((e.part_order, e.onset, e.pitch, e.duration)
                          for line, events in prediction.lines.items() for e in events)
    common = sum((ref_events & pred_events).values())
    ref_n, pred_n = sum(ref_events.values()), sum(pred_events.values())
    precision = common / pred_n if pred_n else (1.0 if not ref_n else 0.0)
    recall = common / ref_n if ref_n else (1.0 if not pred_n else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"line_order": keys, "per_line": per_line,
            "totals": {"reference_notes": ref_n, "prediction_notes": pred_n,
                       "pitch_edit_distance": pitch_edits,
                       "pitch_error_rate": pitch_edits / pitch_den if pitch_den else 0.0,
                       "pitch_duration_edit_distance": duration_edits,
                       "pitch_duration_error_rate": duration_edits / duration_den if duration_den else 0.0,
                       "pitch_rate_denominator": pitch_den,
                       "pitch_duration_rate_denominator": duration_den},
            "time_aware_exact_event_multiset": {"matches": common, "precision": precision,
                                                  "recall": recall, "f1": f1}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("prediction", type=Path)
    parser.add_argument("--out", type=Path, help="Write JSON here (stdout when omitted).")
    args = parser.parse_args()
    ref = parse_score(args.reference)
    pred = parse_score(args.prediction, line_names=[part["line"] for part in ref.summaries])
    result = {"schema_version": 1, "reference": str(args.reference), "prediction": str(args.prediction),
              "comparison": compare(ref, pred),
              "reference_structure": {"parts": ref.summaries, "measure_count": ref.measures,
                                      "rest_count": ref.rests, "grace_note_count": ref.graces},
              "prediction_structure": {"parts": pred.summaries, "measure_count": pred.measures,
                                        "rest_count": pred.rests, "grace_note_count": pred.graces},
              "limitations": ["Written pitches and notated durations only; no repeat unfolding, transposition, or octave correction.",
                              "Time-aware events use part-local absolute quarter-note onset derived from MusicXML durations and meter.",
                              "Part matching uses vocal names when present and otherwise the conventional four-part order."]}
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data)
    else:
        sys.stdout.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
