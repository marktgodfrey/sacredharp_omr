"""Arrange a two-staff SATB MusicXML score as four shape-note vocal parts."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from pathlib import Path


PARTS = ("Treble", "Alto", "Tenor", "Bass")
TARGETS = (("Treble", 1, "G", 2, "E4", "F5"),
           ("Alto", 0, "G", 2, "E4", "F5"),
           ("Tenor", 0, "G", 2, "E4", "F5"),
           ("Bass", 1, "F", 4, "G2", "A3"))
STEPS = "CDEFGAB"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _child(node, name):
    return next((e for e in node if _local(e.tag) == name), None)


def _children(node, name):
    return [e for e in node if _local(e.tag) == name]


def _tag(parent, name):
    return f"{parent.tag[:parent.tag.index('}') + 1]}{name}" if "}" in parent.tag else name


def _retag(element, parent):
    """Put a default-namespace MusicXML subtree in its destination namespace."""
    namespace = parent.tag[:parent.tag.index("}") + 1] if "}" in parent.tag else ""
    for node in element.iter():
        node.tag = namespace + _local(node.tag)
    return element


@dataclass
class Event:
    note: ET.Element
    onset: Fraction
    duration: Fraction
    voice: str
    staff: int
    pitch: int | None
    stem: str | None
    chord: bool
    rest: bool


def _pitch(note):
    p = _child(note, "pitch")
    if p is None:
        return None
    step, octave = _child(p, "step"), _child(p, "octave")
    if step is None or octave is None or step.text not in STEPS:
        raise ValueError("unsupported or incomplete MusicXML pitch")
    return int(octave.text) * 7 + STEPS.index(step.text)


def _parse_measure(part, measure, divisions: int) -> tuple[list[Event], Fraction, int]:
    cursor = Fraction(0)
    furthest = Fraction(0)
    events = []
    last_start: dict[tuple[int, str], Fraction] = {}
    for item in measure:
        name = _local(item.tag)
        if name == "attributes":
            de = _child(item, "divisions")
            if de is not None:
                divisions = int(de.text)
                if divisions <= 0:
                    raise ValueError("MusicXML divisions must be positive")
        elif name in ("backup", "forward"):
            de = _child(item, "duration")
            if de is None:
                raise ValueError(f"MusicXML {name} is missing duration")
            delta = Fraction(int(de.text), divisions)
            cursor += delta if name == "forward" else -delta
            if cursor < 0:
                raise ValueError("MusicXML backup moves before the measure start")
            furthest = max(furthest, cursor)
        elif name == "note":
            staff_el, voice_el = _child(item, "staff"), _child(item, "voice")
            staff = int(staff_el.text) if staff_el is not None and staff_el.text else 1
            voice = voice_el.text.strip() if voice_el is not None and voice_el.text else "?"
            chord = _child(item, "chord") is not None
            duration_el = _child(item, "duration")
            duration = Fraction(int(duration_el.text), divisions) if duration_el is not None else Fraction(0)
            key = (staff, voice)
            onset = last_start.get(key, cursor) if chord else cursor
            if not chord:
                last_start[key] = onset
            pitch = _pitch(item)
            rest = _child(item, "rest") is not None
            stem_el = _child(item, "stem")
            event = Event(item, onset, duration, voice, staff, pitch,
                          stem_el.text if stem_el is not None else None, chord, rest)
            events.append(event)
            if not chord:
                cursor += duration
                furthest = max(furthest, cursor)
            else:
                furthest = max(furthest, onset + duration)
    return events, furthest, divisions


def _median(values):
    s = sorted(values)
    return s[len(s) // 2] if s else 0


def _mark_fallback(report, events):
    report["_fallback_events"].update(id(event) for event in events)


def _has_fused_pair(events: list[Event]) -> bool:
    """Whether one measure contains a fused two-note chord on this staff."""
    groups = {}
    for event in events:
        if event.pitch is not None:
            groups.setdefault((event.staff, event.voice, event.onset), []).append(event)
    return any(len(group) == 2 and any(event.chord for event in group)
               for group in groups.values())


def _can_duplicate_unison(event: Event, events: list[Event]) -> bool:
    """Conservatively recognize an isolated, visible singleton in a fused staff."""
    if (event.pitch is None or event.chord or event.duration <= 0 or event.stem is not None or
            event.voice == "?" or event.note.get("print-object") == "no" or
            _child(event.note, "grace") is not None):
        return False
    end = event.onset + event.duration
    for other in events:
        if other is event or other.duration <= 0:
            continue
        overlaps = event.onset < other.onset + other.duration and other.onset < end
        if not overlaps:
            continue
        if other.pitch is not None:
            return False
        rest = _child(other.note, "rest")
        if other.rest and other.note.get("print-object") != "no" and \
                (rest is None or rest.get("print-object") != "no"):
            return False
    return True


def _route_staff(events: list[Event], staff: int, report: dict, source_label: str) -> dict:
    """Resolve source voice labels to upper/lower staff lines."""
    pitched = [e for e in events if e.staff == staff and e.pitch is not None and not e.chord]
    ids = sorted({e.voice for e in pitched if e.voice != "?"}, key=lambda v: (not v.isdigit(), int(v) if v.isdigit() else v))
    by_voice = {v: [e for e in pitched if e.voice == v] for v in ids}
    if len(ids) > 2:
        raise ValueError(f"staff {staff} contains more than two independent source voices")
    route = {}
    if len(ids) == 2:
        med = {v: _median([e.pitch for e in by_voice[v]]) for v in ids}
        dominant = {}
        for v in ids:
            votes = [e.stem for e in by_voice[v] if e.stem in ("up", "down")]
            dominant[v] = max(("up", "down"), key=votes.count) if votes else None
        distinct = dominant[ids[0]] == "up" and dominant[ids[1]] == "down" or \
                   dominant[ids[1]] == "up" and dominant[ids[0]] == "down"
        if distinct:
            route = {v: ("upper" if dominant[v] == "up" else "lower") for v in ids}
        elif med[ids[0]] != med[ids[1]]:
            top = max(ids, key=lambda v: med[v])
            route = {v: ("upper" if v == top else "lower") for v in ids}
            _mark_fallback(report, (e for v in ids for e in by_voice[v]))
        elif all(v.isdigit() for v in ids):
            route = {ids[0]: "upper", ids[1]: "lower"}
            _mark_fallback(report, (e for v in ids for e in by_voice[v]))
            report["ambiguities"].append(f"{source_label}: equal-pitch source voices routed by voice order")
        else:
            raise ValueError(f"staff {staff} voices cannot be separated by pitch or stem")
    elif len(ids) == 1:
        v = ids[0]
        ups = [e for e in by_voice[v] if e.stem == "up"]
        downs = [e for e in by_voice[v] if e.stem == "down"]
        if ups and downs:
            # Stem direction is the only evidence of two lines in one voice ID.
            for e in by_voice[v]:
                route[id(e)] = "upper" if e.stem == "up" else "lower" if e.stem == "down" else "upper"
            _mark_fallback(report, by_voice[v])
            report["ambiguities"].append(f"{source_label}: one voice split by stem direction")
        else:
            route[v] = "upper"
            _mark_fallback(report, by_voice[v])
            report["ambiguities"].append(f"{source_label}: only one explicit voice; assigned to upper line")
    else:
        # Voice-less notes can still be separated by stem. Otherwise pitch
        # relative to the staff median is the deterministic, reported fallback.
        unlabelled = [e for e in pitched if e.voice == "?"]
        if not unlabelled:
            return route
        ups = [e for e in unlabelled if e.stem == "up"]
        downs = [e for e in unlabelled if e.stem == "down"]
        if ups and downs:
            for e in unlabelled:
                route[id(e)] = "upper" if e.stem == "up" else "lower"
        elif len({e.pitch for e in unlabelled}) > 1:
            pivot = _median([e.pitch for e in unlabelled])
            for e in unlabelled:
                route[id(e)] = "upper" if e.pitch >= pivot else "lower"
        else:
            for e in unlabelled:
                route[id(e)] = "upper"
            report["ambiguities"].append(f"{source_label}: voice-less unison routed to upper line")
        _mark_fallback(report, unlabelled)
    return route


def _event_line(event: Event, route: dict, staff: int, report: dict, events: list[Event], source_label: str,
                preserve_ambiguous_chords: bool = False) -> str:
    if event.pitch is not None:
        if event.chord or any(e.chord for e in events if e.staff == staff and e.onset == event.onset):
            simultaneous = [e for e in events if e.staff == staff and e.voice == event.voice and
                            e.onset == event.onset and e.pitch is not None]
            if len(simultaneous) > 2:
                if not preserve_ambiguous_chords:
                    raise ValueError(f"{source_label} measure has a chord larger than two notes")
                group_key = frozenset(id(e) for e in simultaneous)
                if group_key not in report.setdefault("_ambiguous_chords", set()):
                    report["_ambiguous_chords"].add(group_key)
                    _mark_fallback(report, simultaneous)
                    stems = {e.stem for e in simultaneous if e.stem in ("up", "down")}
                    if stems == {"up", "down"}:
                        for e in simultaneous:
                                if e.stem in ("up", "down"):
                                    report.setdefault("_ambiguous_chord_routes", {})[id(e)] = (
                                        "upper" if e.stem == "up" else "lower")
                        # Notes without explicit stems are assigned by the same stable pitch split.
                        _split_ambiguous_chord(simultaneous, report)
                    else:
                        _split_ambiguous_chord(simultaneous, report)
                    report["ambiguities"].append(
                        f"{source_label}: preserved ambiguous chord with {len(simultaneous)} notes")
                return report["_ambiguous_chord_routes"][id(event)]
            if len(simultaneous) == 2 and any(e.chord for e in simultaneous):
                pair_key = frozenset(id(e) for e in simultaneous)
                if pair_key not in report["_fused_chords"]:
                    report["_fused_chords"].add(pair_key)
                    _mark_fallback(report, simultaneous)
                    report["ambiguities"].append(f"{source_label}: fused chord split by pitch")
                if simultaneous[0].pitch == simultaneous[1].pitch:
                    return "upper" if event is simultaneous[0] else "lower"
                return "upper" if event.pitch == max(e.pitch for e in simultaneous) else "lower"
        if id(event) in route:
            return route[id(event)]
        if event.voice in route and isinstance(route[event.voice], str):
            return route[event.voice]
        if id(event) in route:
            return route[id(event)]
        if event.voice == "?":
            matches = [e for e in events if e.staff == staff and e.pitch is not None and e.voice != "?" and
                       abs(e.onset - event.onset) <= event.duration]
            if matches:
                nearest = min(matches, key=lambda e: abs(e.onset - event.onset))
                return route.get(nearest.voice, "upper")
            report["ambiguities"].append(f"{source_label}: unvoiced note routed to upper line")
            _mark_fallback(report, [event])
            return "upper"
        return "upper"
    if event.voice in route and isinstance(route[event.voice], str):
        return route[event.voice]
    # A rest without a readable voice belongs to the nearest preceding/following
    # voiced event. Keeping it on one line avoids inventing notes or duplicated rests.
    candidates = [e for e in events if e.staff == staff and e.pitch is not None and e.voice in route]
    if candidates:
        nearest = min(candidates, key=lambda e: abs(e.onset - event.onset))
        _mark_fallback(report, [event])
        report["ambiguities"].append(f"{source_label}: unvoiced rest assigned to nearest voice")
        return route[nearest.voice]
    report["ambiguities"].append(f"{source_label}: unvoiced rest assigned to upper line")
    return "upper"


def _split_ambiguous_chord(events: list[Event], report: dict) -> None:
    """Assign ambiguous chord notes to two lanes by a deterministic pitch split."""
    ordered = sorted(enumerate(events), key=lambda pair: (pair[1].pitch, pair[0]))
    if len(ordered) == 1:
        report.setdefault("_ambiguous_chord_routes", {})[id(ordered[0][1])] = "upper"
        return
    midpoint = (ordered[0][1].pitch + ordered[-1][1].pitch) / 2
    ties = [pair for pair in ordered if pair[1].pitch == midpoint]
    tie_upper = {id(pair[1]) for pair in ties[(len(ties) + 1) // 2:]}
    for _, event in ordered:
        routes = report.setdefault("_ambiguous_chord_routes", {})
        if id(event) not in routes:
            if event.pitch > midpoint or (event.pitch == midpoint and id(event) in tie_upper):
                routes[id(event)] = "upper"
            else:
                routes[id(event)] = "lower"


def _ordinal(step: str, octave: int) -> int:
    return octave * 7 + STEPS.index(step)


def _pitch_bounds(name):
    step, octave = name[0], int(name[1:])
    return _ordinal(step, octave)


def choose_octave_shift(events: list[Event], target: str) -> int:
    """Choose one diatonic octave shift for a whole voice, minimizing ledger lines."""
    low, high = (("E4", "F5") if target != "Bass" else ("G2", "A3"))
    lo, hi = _pitch_bounds(low), _pitch_bounds(high)
    pitches = [e.pitch for e in events if e.pitch is not None and not e.rest]
    if not pitches:
        return 0
    center = (lo + hi) / 2
    return min(range(-2, 3), key=lambda shift: (
        sum(max(lo - (p + 7 * shift), 0, (p + 7 * shift) - hi) ** 2 for p in pitches),
        sum(abs(p + 7 * shift - center) for p in pitches), abs(shift)))


def _lcm(a: int, b: int) -> int:
    return abs(a * b) // gcd(a, b) if a and b else 0


def _fraction_divisions(values):
    out = 1
    for value in values:
        out = _lcm(out, value.denominator)
    return max(1, out)


def _make_attributes(parent, divisions, key, time, clef_sign, clef_line,
                     *, include_key=True, include_time=True, include_clef=True):
    attrs = ET.SubElement(parent, _tag(parent, "attributes"))
    ET.SubElement(attrs, _tag(attrs, "divisions")).text = str(divisions)
    if include_key:
        key_out = _retag(copy.deepcopy(key), attrs)
        key_out.attrib.pop("number", None)
        attrs.append(key_out)
    if include_time:
        time_out = _retag(copy.deepcopy(time), attrs)
        time_out.attrib.pop("number", None)
        attrs.append(time_out)
    if include_clef:
        clef = ET.SubElement(attrs, _tag(attrs, "clef"))
        ET.SubElement(clef, _tag(clef, "sign")).text = clef_sign
        ET.SubElement(clef, _tag(clef, "line")).text = str(clef_line)


def _state_fingerprint(element):
    clone = copy.deepcopy(element)
    clone.attrib.pop("number", None)
    return ET.tostring(clone, encoding="unicode")


def _music_state(parts, measure_idx, source_staff):
    """Get the active key/time state for a staff through this measure."""
    part = parts[source_staff[0]]
    default_key = ET.Element("key")
    ET.SubElement(default_key, "fifths").text = "0"
    ET.SubElement(default_key, "mode").text = "major"
    default_time = ET.Element("time")
    ET.SubElement(default_time, "beats").text = "4"
    ET.SubElement(default_time, "beat-type").text = "4"
    key = default_key
    time = default_time
    key_specific = {}
    time_specific = {}
    for measure in list(e for e in part if _local(e.tag) == "measure")[:measure_idx + 1]:
        for attrs in (e for e in measure if _local(e.tag) == "attributes"):
            for k in _children(attrs, "key"):
                n = k.get("number")
                if n is None:
                    key = k; key_specific.clear()
                else:
                    key_specific[n] = k
            for t in _children(attrs, "time"):
                n = t.get("number")
                if n is None:
                    time = t; time_specific.clear()
                else:
                    time_specific[n] = t
    selected = str(source_staff[1])
    return key_specific.get(selected, key), time_specific.get(selected, time)


def arrange(source: str | Path | bytes, *, octave_shifts="auto",
            preserve_ambiguous_chords: bool = False) -> tuple[ET.ElementTree, dict]:
    """Convert a two-staff SATB score into Treble, Alto, Tenor, Bass parts."""
    if isinstance(source, bytes):
        root = ET.fromstring(source)
        tree = ET.ElementTree(root)
    elif isinstance(source, ET.ElementTree):
        tree, root = source, source.getroot()
    else:
        tree = ET.parse(source); root = tree.getroot()
    if _local(root.tag) != "score-partwise":
        raise ValueError("expected a MusicXML score-partwise document")
    source_parts = [e for e in root if _local(e.tag) == "part"]
    if len(source_parts) == 1:
        source_parts = source_parts
        layout = "two-staves-one-part"
    elif len(source_parts) == 2:
        layout = "two-parts-one-staff"
    else:
        raise ValueError("input must have one two-staff part or two one-staff parts")
    measures_by_part = [[e for e in p if _local(e.tag) == "measure"] for p in source_parts]
    if not measures_by_part or len({len(ms) for ms in measures_by_part}) != 1:
        raise ValueError("source parts must have the same measure count")
    if layout == "two-staves-one-part":
        found = {int(s.text) for m in measures_by_part[0] for s in m.iter() if _local(s.tag) == "staff" and s.text}
        for measure in measures_by_part[0]:
            for declaration in measure.iter():
                if _local(declaration.tag) == "staves" and declaration.text:
                    found.update(range(1, int(declaration.text) + 1))
        if found - {1, 2} or not {1, 2}.issubset(found):
            raise ValueError("the one-part source must declare or use both staff 1 and staff 2")
    else:
        for part in source_parts:
            found = {int(s.text) for m in part.iter() for s in m.iter() if _local(s.tag) == "staff" and s.text}
            found.update(int(s.text) for m in part.iter() for s in m.iter()
                         if _local(s.tag) == "staves" and s.text)
            if found - {1}:
                raise ValueError("each source part must contain one staff")

    report = {"layout": layout, "octave_shifts": {}, "fallback_notes": 0, "ambiguities": [],
              "beams_removed": 0, "_fused_chords": set(), "_fallback_events": set(),
              "_ambiguous_chords": set(), "_ambiguous_chord_routes": {}}
    measure_lengths: list[Fraction] = []
    divisions_by_part = [1] * len(source_parts)
    line_events = {name: [] for name in PARTS}
    line_map = {name: [] for name in PARTS}
    # Resolve source voice labels across the full score so a voice that rests
    # for an entire measure keeps its upper/lower identity in that measure.
    parsed_measures = []
    max_measure_len = []
    whole_staff = {}
    for mi in range(len(measures_by_part[0])):
        all_events = []
        max_len = Fraction(0)
        for pi, part in enumerate(source_parts):
            ev, length, divisions_by_part[pi] = _parse_measure(part, measures_by_part[pi][mi], divisions_by_part[pi])
            all_events.extend((pi, e) for e in ev)
            max_len = max(max_len, length)
            for event in ev:
                key = (pi, event.staff) if layout == "two-parts-one-staff" else (0, event.staff)
                whole_staff.setdefault(key, []).append(event)
        parsed_measures.append(all_events)
        max_measure_len.append(max_len)
    routes = {key: _route_staff(events, key[1], report, f"source part {key[0] + 1}/staff {key[1]}")
              for key, events in whole_staff.items()}
    fused_evidence = set()
    for measure_events in parsed_measures:
        by_staff = {}
        for pi, event in measure_events:
            key = (pi, event.staff) if layout == "two-parts-one-staff" else (0, event.staff)
            by_staff.setdefault(key, []).append(event)
        fused_evidence.update(key for key, events in by_staff.items() if _has_fused_pair(events))
    for mi, all_events in enumerate(parsed_measures):
        measure_lengths.append(max_measure_len[mi])
        per_line = {name: [] for name in PARTS}
        for staff in (1, 2):
            if layout == "two-parts-one-staff":
                source_part_idx, source_staff = staff - 1, 1
                part_events = [e for pi, e in all_events if pi == source_part_idx and e.staff == source_staff]
            else:
                source_part_idx, source_staff = 0, staff
                part_events = [e for pi, e in all_events if pi == 0 and e.staff == source_staff]
            route = routes.get((source_part_idx, source_staff), {})
            if staff == 1:
                upper, lower = "Tenor", "Alto"
            else:
                upper, lower = "Treble", "Bass"
            for event in part_events:
                line = _event_line(event, route, source_staff, report, part_events,
                                   f"source part {source_part_idx + 1}/staff {source_staff}",
                                   preserve_ambiguous_chords)
                per_line[upper if line == "upper" else lower].append(event)
            measure_voice_ids = {event.voice for event in part_events if event.voice != "?"}
            if (source_part_idx, source_staff) in fused_evidence and len(measure_voice_ids) <= 1:
                inferred = [event for event in part_events if _can_duplicate_unison(event, part_events)]
                for event in inferred:
                    destination = lower if any(e is event for e in per_line[upper]) else upper
                    per_line[destination].append(event)
                    _mark_fallback(report, [event])
                    report["ambiguities"].append(
                        f"source part {source_part_idx + 1}/staff {source_staff}: "
                        "isolated singleton copied to both lines as an inferred unison")
        for name in PARTS:
            line_events[name].extend(per_line[name])
            line_map[name].append(per_line[name])
    shifts = {}
    for name in PARTS:
        if octave_shifts == "auto":
            shifts[name] = choose_octave_shift(line_events[name], name)
        else:
            shifts[name] = int(octave_shifts.get(name, 0))
            if shifts[name] not in range(-2, 3):
                raise ValueError(f"octave shift for {name} must be between -2 and 2")
    report["octave_shifts"] = shifts

    # Build a clean partwise document while retaining score-level metadata.
    out_root = ET.Element(root.tag, dict(root.attrib))
    for child in root:
        if _local(child.tag) == "part-list":
            part_list = ET.SubElement(out_root, _tag(out_root, "part-list"), dict(child.attrib))
            for idx, name in enumerate(PARTS, 1):
                sp = ET.SubElement(part_list, _tag(part_list, "score-part"), {"id": f"P{idx}"})
                ET.SubElement(sp, _tag(sp, "part-name")).text = name
        elif _local(child.tag) != "part":
            out_root.append(copy.deepcopy(child))
    new_parts = []
    for idx, name in enumerate(PARTS, 1):
        part = ET.SubElement(out_root, _tag(out_root, "part"), {"id": f"P{idx}"})
        new_parts.append(part)
        target = next(t for t in TARGETS if t[0] == name)
        _, source_slot, clef_sign, clef_line, _, _ = target
        source_part_idx, source_staff = ((source_slot, 1) if layout == "two-parts-one-staff"
                                         else (0, source_slot + 1))
        prior_key = prior_time = None
        for mi in range(len(measures_by_part[0])):
            source_measure = measures_by_part[source_part_idx][mi]
            src_measure = line_map[name][mi]
            m_attrs = dict(source_measure.attrib)
            measure = ET.SubElement(part, _tag(part, "measure"), m_attrs)
            key, time = _music_state(source_parts, mi, (source_part_idx, source_staff))
            # Use one exact integer divisions scale for every note and gap.
            all_fracs = [measure_lengths[mi]] + [e.onset for e in src_measure] + [e.duration for e in src_measure]
            divisions = _fraction_divisions(all_fracs)
            key_fp, time_fp = _state_fingerprint(key), _state_fingerprint(time)
            _make_attributes(measure, divisions, key, time, clef_sign, clef_line,
                             include_key=prior_key != key_fp,
                             include_time=prior_time != time_fp,
                             include_clef=mi == 0)
            prior_key, prior_time = key_fp, time_fp
            ordered = sorted(src_measure, key=lambda e: (e.onset, 0 if e.duration == 0 else 1,
                                                         0 if e.pitch is None else e.pitch))
            lanes = []
            prior_onset = None
            for event in ordered:
                lane = next((entries for entries, end, last in lanes
                             if event.onset >= end or event.onset == last), None)
                if lane is None:
                    if lanes:
                        report["ambiguities"].append(f"{name} measure {mi + 1}: overlapping events retained in voice 2")
                    lane = []
                    lanes.append((lane, Fraction(0), None))
                lane.append(event)
                lane_index = next(i for i, row in enumerate(lanes) if row[0] is lane)
                entries, end, last = lanes[lane_index]
                lanes[lane_index] = (entries, max(end, event.onset + event.duration), event.onset)
            if not lanes:
                lanes = [([], Fraction(0), None)]
            for lane_index, (events, _, _) in enumerate(lanes, 1):
                cursor = Fraction(0)
                lane_onset = None
                for event in events:
                    chord_member = event.pitch is not None and event.onset == lane_onset and event.duration > 0
                    if event.onset > cursor:
                        forward = ET.SubElement(measure, _tag(measure, "forward"))
                        ET.SubElement(forward, _tag(forward, "duration")).text = str(int((event.onset - cursor) * divisions))
                        ET.SubElement(forward, _tag(forward, "voice")).text = str(lane_index)
                        cursor = event.onset
                    note = copy.deepcopy(event.note)
                    for child in list(note):
                        if _local(child.tag) == "beam":
                            report["beams_removed"] += 1
                        if _local(child.tag) in ("chord", "staff", "stem", "beam"):
                            note.remove(child)
                    voice = _child(note, "voice")
                    if voice is None:
                        voice = ET.Element(_tag(note, "voice"))
                        after_voice = {"type", "dot", "accidental", "time-modification", "stem", "notehead",
                                       "notehead-text", "staff", "beam", "notations", "lyric", "play", "listen"}
                        insert_at = next((i for i, child in enumerate(note) if _local(child.tag) in after_voice), len(note))
                        note.insert(insert_at, voice)
                    voice.text = str(lane_index)
                    if chord_member:
                        chord = ET.Element(_tag(note, "chord"))
                        note.insert(1 if _child(note, "grace") is not None else 0, chord)
                        _mark_fallback(report, [event])
                        message = f"{name} measure {mi + 1}: same-onset events rendered as chords"
                        if message not in report["ambiguities"]:
                            report["ambiguities"].append(message)
                    dur = _child(note, "duration")
                    if dur is not None:
                        dur.text = str(int(event.duration * divisions))
                    pitch = _child(note, "pitch")
                    if pitch is not None:
                        octave = _child(pitch, "octave")
                        octave.text = str(int(octave.text) + shifts[name])
                    measure.append(note)
                    if event.duration and not chord_member:
                        cursor = max(cursor, event.onset + event.duration)
                    if event.pitch is not None and event.duration > 0:
                        lane_onset = event.onset
                if cursor < measure_lengths[mi]:
                    forward = ET.SubElement(measure, _tag(measure, "forward"))
                    ET.SubElement(forward, _tag(forward, "duration")).text = str(int((measure_lengths[mi] - cursor) * divisions))
                    ET.SubElement(forward, _tag(forward, "voice")).text = str(lane_index)
                if lane_index < len(lanes) and measure_lengths[mi]:
                    backup = ET.SubElement(measure, _tag(measure, "backup"))
                    ET.SubElement(backup, _tag(backup, "duration")).text = str(int(measure_lengths[mi] * divisions))
            for barline in _children(source_measure, "barline"):
                measure.append(copy.deepcopy(barline))
    report.pop("_fused_chords")
    report.pop("_ambiguous_chords")
    report.pop("_ambiguous_chord_routes")
    report["fallback_notes"] = len(report.pop("_fallback_events"))
    report["ambiguities"] = list(dict.fromkeys(report["ambiguities"]))
    report["review_needed_count"] = report["fallback_notes"]
    return ET.ElementTree(out_root), report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--octave-shift", action="append", default=[], metavar="PART=N",
                        help="override auto octave shift, e.g. --octave-shift Treble=1")
    parser.add_argument("--preserve-ambiguous-chords", action="store_true",
                        help="preserve chords larger than two notes as an uncorrected draft")
    parser.add_argument("--target-key", help="choose a specific output key, e.g. F#m")
    parser.add_argument("--source-mode", choices=("major", "minor"), help="correct an uncertain source mode")
    parser.add_argument("--keep-key-and-register", action="store_true", help="skip singing-register fitting")
    args = parser.parse_args(argv)
    shifts = "auto"
    if args.octave_shift:
        shifts = {}
        for row in args.octave_shift:
            name, sep, value = row.partition("=")
            if not sep or name not in PARTS:
                parser.error(f"invalid octave shift {row!r}")
            shifts[name] = int(value)
    try:
        if args.keep_key_and_register:
            tree, report = arrange(args.input, octave_shifts=shifts,
                                   preserve_ambiguous_chords=args.preserve_ambiguous_chords)
        else:
            from .registers import arrange_for_singing
            tree, report = arrange_for_singing(args.input, target_key=args.target_key,
                                               source_mode=args.source_mode,
                                               initial_octave_shifts=shifts,
                                               octave_adjustments={name: 0 for name in shifts} if isinstance(shifts, dict) else None,
                                               preserve_ambiguous_chords=args.preserve_ambiguous_chords)
        from .shapenotes import transform
        shaped, _ = transform(ET.tostring(tree.getroot(), encoding="utf-8"))
    except (ET.ParseError, OSError, ValueError) as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    shaped.write(args.out, encoding="utf-8", xml_declaration=True)
    print(json.dumps({"input": str(args.input), "output": str(args.out), **report}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
