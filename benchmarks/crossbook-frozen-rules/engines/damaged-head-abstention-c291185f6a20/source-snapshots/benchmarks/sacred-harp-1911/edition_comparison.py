"""Compare OMR output against an edition with explicit physical voice order."""
from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from compare_musicxml import Parsed, compare, parse_score

_FOUR = ["treble", "alto", "tenor", "bass"]
_THREE = ["treble", "tenor", "bass"]


def _forced_score(path: Path, names: list[str], *, strict: bool) -> Parsed:
    tree = ET.parse(path)
    root = tree.getroot()
    parts = root.findall("part")
    if strict and len(parts) != len(names):
        raise ValueError(f"expected {len(names)} parts, found {len(parts)} in {path}")
    plist = root.find("part-list")
    if plist is None:
        plist = ET.Element("part-list")
        root.insert(0, plist)
    decls = {p.get("id"): p for p in plist.findall("score-part")}
    # Override names in a temporary copy so instrument labels cannot defeat visual order.
    for i, part in enumerate(parts):
        name = names[i] if i < len(names) else f"Part {i + 1}"
        part_id = part.get("id") or f"P{i + 1}"
        part.set("id", part_id)
        decl = decls.get(part_id)
        if decl is None:
            decl = ET.SubElement(plist, "score-part", id=part_id)
            decls[part_id] = decl
        node = decl.find("part-name")
        if node is None:
            node = ET.SubElement(decl, "part-name")
        node.text = name
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "score.musicxml"
        tree.write(tmp, encoding="utf-8", xml_declaration=True)
        return parse_score(tmp, line_names=names)


def _revoice(parsed: Parsed, line_ids: dict[str, int]) -> Parsed:
    lines = {}
    for line, events in parsed.lines.items():
        index = line_ids[line]
        lines[line] = [replace(event, part_order=index) for event in events]
    return Parsed(lines, parsed.summaries, parsed.rests, parsed.graces, parsed.measures)


def compare_edition(reference_path, prediction_path, source_voice_order: list[str],
                    reference_voice_order: list[str] | None = None) -> dict:
    """Compare scores using visually established physical voice identities."""
    reference_path, prediction_path = Path(reference_path), Path(prediction_path)
    # Parse reference once to choose conventional edition order by actual count.
    raw_ref = parse_score(reference_path)
    if reference_voice_order is None:
        count = len(raw_ref.summaries)
        if count == 4:
            reference_voice_order = _FOUR
        elif count == 3:
            reference_voice_order = _THREE
        else:
            raise ValueError(f"no conventional voice order for {count} reference parts")
    else:
        reference_voice_order = list(reference_voice_order)
    source_voice_order = list(source_voice_order)
    if (not source_voice_order or any(not isinstance(v, str) or not v.strip() for v in source_voice_order)
            or len(source_voice_order) != len(set(source_voice_order))):
        raise ValueError("source_voice_order must contain unique nonempty voice names")
    if reference_voice_order is not None:
        reference_voice_order = list(reference_voice_order)
        if (not reference_voice_order or any(not isinstance(v, str) or not v.strip() for v in reference_voice_order)
                or len(reference_voice_order) != len(set(reference_voice_order))):
            raise ValueError("reference_voice_order must contain unique nonempty voice names")
    if len(reference_voice_order) != len(raw_ref.summaries):
        raise ValueError("reference_voice_order length must match reference part count")
    ref = _forced_score(reference_path, reference_voice_order, strict=True)
    pred = _forced_score(prediction_path, source_voice_order, strict=False)
    # Edition-absent voices are omitted from both edit denominators and exact-event recall.
    excluded = [v for v in reference_voice_order if v not in source_voice_order]
    excluded_counts = {v: sum(len(es) for key, es in ref.lines.items()
                              if key.split(":staff", 1)[0] == v) for v in excluded}
    ref.lines = {v: es for v, es in ref.lines.items()
                 if v.split(":staff", 1)[0] not in excluded}
    shared_lines = list(dict.fromkeys([*ref.lines, *pred.lines]))
    line_ids = {line: index + 1 for index, line in enumerate(shared_lines)}
    ref = _revoice(ref, line_ids)
    pred = _revoice(pred, line_ids)
    return {
        "comparison": compare(ref, pred),
        "excluded_reference_lines": excluded,
        "excluded_reference_note_counts": excluded_counts,
        "source_voice_order": source_voice_order,
        "reference_voice_order": reference_voice_order,
        "reference_structure": ref.summaries,
        "prediction_structure": pred.summaries,
    }
