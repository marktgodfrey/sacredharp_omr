#!/usr/bin/env python3
"""Inventory unconfirmed reader-gallery reference-note misses for scan review."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from compare_musicxml import STEP, _line_name, parse_score, q
from analyze_shape_retention import SHAPES, align

ROOT = Path(__file__).resolve().parent
EXCLUDED_ID = "1911-Origin-JPK-0069"  # Holy Manna
SHAPE_NAMES = ("fa", "sol", "la", "mi", "chromatic_excluded")


def xml_event_locations(path: Path):
    """Return parsed-line event metadata in compare_musicxml ordering."""
    root = ET.parse(path).getroot()
    part_names = {p.get("id", ""): p.findtext("part-name", default=p.get("id", "part"))
                  for p in root.findall("./part-list/score-part")}
    raw = defaultdict(list)
    for pi, part in enumerate(root.findall("part")):
        line = _line_name(part_names.get(part.get("id", ""), part.get("id", "part")), pi)
        by_staff = defaultdict(list)
        cursor = part_time = Fraction(0)
        divisions, nominal = 1, None
        for mi, measure in enumerate(part.findall("measure"), 1):
            cursor = Fraction(0)
            last_onset = max_cursor = Fraction(0)
            measure_nominal = nominal
            within = defaultdict(int)
            for child in measure:
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "attributes":
                    d = child.findtext("divisions")
                    if d: divisions = int(d)
                    beats, beat_type = child.findtext("./time/beats"), child.findtext("./time/beat-type")
                    if beats and beat_type:
                        try:
                            nominal = measure_nominal = Fraction(sum(map(int, beats.split("+"))) * 4, int(beat_type))
                        except ValueError:
                            nominal = measure_nominal = None
                elif tag in ("backup", "forward"):
                    amount = Fraction(int(child.findtext("duration", default="0")), divisions)
                    cursor += amount if tag == "forward" else -amount
                    max_cursor = max(max_cursor, cursor)
                elif tag == "note":
                    if child.find("grace") is not None: continue
                    dur = Fraction(int(child.findtext("duration", default="0")), divisions)
                    chord = child.find("chord") is not None
                    onset = last_onset if chord else cursor
                    if not chord: last_onset = cursor
                    max_cursor = max(max_cursor, onset + dur)
                    pitch_node = child.find("pitch")
                    if pitch_node is not None:
                        pitch = ((int(pitch_node.findtext("octave", default="4")) + 1) * 12
                                 + STEP[pitch_node.findtext("step", default="C")]
                                 + int(Fraction(pitch_node.findtext("alter", default="0"))))
                        staff = child.findtext("staff", default="1")
                        key = f"{line}:staff{staff}"
                        within[key] += 1
                        by_staff[staff].append((part_time + onset, pitch, dur, mi, within[key]))
                    if not chord:
                        cursor += dur
                        max_cursor = max(max_cursor, cursor)
            advance = max_cursor if measure.get("implicit") == "yes" else max(max_cursor, measure_nominal or Fraction(0))
            part_time += advance
        for staff, events in by_staff.items():
            key = line if len(by_staff) == 1 else f"{line}:staff{staff}"
            raw[key].extend(events)
    return {key: sorted(vals, key=lambda e: (e[0], e[1], e[2])) for key, vals in raw.items()}


def main():
    results = json.loads((ROOT / "reader-gallery/results.json").read_text())
    records, excluded, ambiguous = [], [], []
    grouped = defaultdict(list)
    for sample in results["samples"]:
        ref_path = ROOT / sample["reference"]
        ref = parse_score(ref_path)
        report = sample["report"]
        flags = {"parts": report["parts"] != len(ref.summaries),
                 "staves": report["staves"] != sample["expected_staves"],
                 "systems": report["systems"] != sample["expected_systems"]}
        if sample["id"] == EXCLUDED_ID or any(flags.values()):
            excluded.append({"song_id": sample["id"], "title": sample["title"],
                             "reason": "Holy Manna" if sample["id"] == EXCLUDED_ID else "reader-gallery structure flag",
                             "flags": flags})
            continue
        xml = ET.parse(ref_path)
        signatures = {int(k.findtext("fifths")) for k in xml.findall(".//key")}
        if len(signatures) != 1: raise ValueError(f"nonconstant key signature in {sample['id']}: {signatures}")
        tonic = 7 * next(iter(signatures)) % 12
        locations = xml_event_locations(ref_path)
        pred = parse_score(ROOT / "reader-gallery" / sample["prediction"],
                           line_names=[p["line"] for p in ref.summaries])
        for line, events in ref.lines.items():
            locs = locations.get(line, [])
            if len(events) != len(locs):
                ambiguous.append({"song_id": sample["id"], "part": line, "reason": "event count mismatch"})
                continue
            # Identical events at different XML measure locations cannot be mapped by
            # compare_musicxml's sorted event identity, so omit that line explicitly.
            identities = defaultdict(set)
            for onset, pitch, dur, measure, _ in locs: identities[(onset, pitch, dur)].add(measure)
            if any(len(ms) > 1 for ms in identities.values()):
                ambiguous.append({"song_id": sample["id"], "part": line,
                                  "reason": "duplicate event identity spans measures"})
                continue
            outcomes = align(events, pred.lines.get(line, []), duration=False)
            for i, event in enumerate(events):
                onset, pitch, dur, measure, note_index = locs[i]
                shape = SHAPES.get((event.pitch - tonic) % 12, "chromatic_excluded")
                outcome = outcomes[i]
                rec = {"song_id": sample["id"], "title": sample["title"], "part": line,
                       "measure_number": measure, "note_index": note_index,
                       "pitch": event.pitch, "duration": q(event.duration), "shape": shape,
                       "outcome": outcome, "alignment": "pitch_only_minimum_edit",
                       "candidate_status": "UNCONFIRMED"}
                records.append(rec)
                if shape == "la" and outcome == "missing":
                    grouped[(sample["id"], sample["title"], line, measure)].append(rec)
    groups = [{"song_id": k[0], "title": k[1], "part": k[2], "measure_number": k[3],
               "la_missing_count": len(v), "candidates": v}
              for k, v in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), *kv[0]))]
    output = {"status": "UNCONFIRMED", "method": "Pitch-only minimal sequence alignment per parsed part",
              "shape_inference": "Pitch class relative to constant key-signature major tonic; chromatic notes excluded",
              "reference_mapping": "MusicXML part-local measure and note indices; sorted as compare_musicxml.parse_score",
              "limitations": ["2025 reference editions compared with 1911 scans",
                              "Minimum-edit ties may alter individual miss assignments",
                              "Candidate inventory does not establish a visual cause or confirm a scan miss"],
              "excluded_samples": excluded, "ambiguous_mappings": ambiguous,
              "records": records, "la_missing_groups": groups}
    dest = ROOT / "diagnostics/miss-trace/candidates.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Saved {dest}: {len(records)} mapped events; {len(groups)} la-miss bars; "
          f"{len(excluded)} excluded samples; {len(ambiguous)} ambiguous lines")


if __name__ == "__main__": main()
