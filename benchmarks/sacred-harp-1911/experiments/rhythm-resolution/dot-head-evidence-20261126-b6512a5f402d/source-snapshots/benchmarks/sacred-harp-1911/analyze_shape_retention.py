#!/usr/bin/env python3
"""Diagnostic reference-note retention by inferred four-shape syllable.

This is a cross-edition, end-to-end sequence comparison, not detector recall.
Shape is inferred from reference pitch class and its constant key signature;
chromatic notes are excluded from the shape table. No inference is performed.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from compare_musicxml import levenshtein, parse_score

ROOT = Path(__file__).resolve().parent
SHAPES = {0: "fa", 2: "sol", 4: "la", 5: "fa", 7: "sol", 9: "la", 11: "mi"}


def align(reference, prediction, *, duration=False):
    """One minimum-edit alignment; prefer matches, substitutions, then deletions.

    Reference notes are assigned a match/substitution/missing outcome. Inserted
    prediction notes are not attributed to a reference shape. Equivalent optimal
    alignments can assign different individual notes to these outcomes.
    """
    a = [(e.pitch, e.duration) if duration else e.pitch for e in reference]
    b = [(e.pitch, e.duration) if duration else e.pitch for e in prediction]
    matrix = [list(range(len(b) + 1))] + [[i] + [0] * len(b) for i in range(1, len(a) + 1)]
    for i, left in enumerate(a, 1):
        for j, right in enumerate(b, 1):
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1,
                               matrix[i - 1][j - 1] + (left != right))
    assert matrix[-1][-1] == levenshtein(a, b)
    outcomes = {}
    i, j = len(a), len(b)
    while i or j:
        if i and j and a[i - 1] == b[j - 1] and matrix[i][j] == matrix[i - 1][j - 1]:
            outcomes[i - 1] = "match"
            i, j = i - 1, j - 1
        elif i and j and matrix[i][j] == matrix[i - 1][j - 1] + 1:
            outcomes[i - 1] = "substitution"
            i, j = i - 1, j - 1
        elif i and matrix[i][j] == matrix[i - 1][j] + 1:
            outcomes[i - 1] = "missing"
            i -= 1
        else:
            j -= 1
    return outcomes


def summary(counts):
    out = {}
    for shape, counts_for_shape in sorted(counts.items()):
        n = sum(counts_for_shape.values())
        out[shape] = {**dict(counts_for_shape), "reference_notes": n,
                      "match_rate": counts_for_shape["match"] / n if n else 0}
    return out


def main():
    results = json.loads((ROOT / "reader-gallery/results.json").read_text())
    groups = {mode: defaultdict(lambda: defaultdict(Counter)) for mode in ("pitch", "pitch_duration")}
    songs = []
    for sample in results["samples"]:
        ref_path = ROOT / sample["reference"]
        xml = ET.parse(ref_path)
        # This method uses one relative-major tonic per score. Refuse modulation.
        signatures = {int(k.findtext("fifths")) for k in xml.findall(".//key")}
        if len(signatures) != 1:
            raise ValueError(f"nonconstant/missing key for {sample['id']}: {signatures}")
        tonic = 7 * next(iter(signatures)) % 12
        ref = parse_score(ref_path)
        pred = parse_score(ROOT / "reader-gallery" / sample["prediction"],
                           line_names=[p["line"] for p in ref.summaries])
        report = sample["report"]
        unflagged = (report["parts"] == len(ref.summaries)
                     and report["staves"] == sample["expected_staves"]
                     and report["systems"] == sample["expected_systems"])
        song_counts = {mode: defaultdict(Counter) for mode in groups}
        for line, events in ref.lines.items():
            for mode in groups:
                outcomes = align(events, pred.lines.get(line, []), duration=mode == "pitch_duration")
                for i, event in enumerate(events):
                    shape = SHAPES.get((event.pitch - tonic) % 12, "chromatic_excluded")
                    outcome = outcomes[i]
                    song_counts[mode][shape][outcome] += 1
                    groups[mode]["all_100"][shape][outcome] += 1
                    if unflagged:
                        groups[mode]["unflagged_93"][shape][outcome] += 1
        songs.append({"id": sample["id"], "title": sample["title"], "unflagged": unflagged,
                      **{mode: summary(c) for mode, c in song_counts.items()}})
    output = {
        "method": "Minimum-edit reference-to-prediction alignment, separately by vocal part",
        "shape_inference": "Reference pitch class relative to major tonic implied by key fifths; chromatic notes excluded",
        "limitations": ["End-to-end pitch/sequence retention, not bounding-box detector recall",
                        "1911 scans versus 2025 references; shapes are inferred, not manually labeled on scans",
                        "Equivalent minimum-edit alignments can change individual assignments",
                        "Notes are correlated within songs; figures are descriptive",
                        "Unflagged staff/part counts do not prove correct geometry"],
        "groups": {mode: {group: summary(c) for group, c in values.items()} for mode, values in groups.items()},
        "songs": songs,
    }
    assert len(songs) == 100 and sum(s["unflagged"] for s in songs) == 93
    assert sum(v["reference_notes"] for v in output["groups"]["pitch"]["all_100"].values()) == 19667
    dest = ROOT / "reader-gallery/shape-retention.json"
    dest.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output["groups"], indent=2))
    print(f"Saved {dest}")


if __name__ == "__main__":
    main()
