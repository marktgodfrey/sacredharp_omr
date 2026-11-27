"""Choose a shared key and written registers for four-staff shape-note singing.

Tenor carries the melody: prioritize E4–F5 with no notes below E4. Alto is
kept in C4–B4, the low part of a treble staff. Treble and bass minimize ledger
lines. These are written-register choices, not promises about vocal ranges.
"""
from __future__ import annotations

import copy
import xml.etree.ElementTree as ET

from .transpose import key_info, parse_key, transpose

STEPS = "CDEFGAB"
NATURAL = (0, 2, 4, 5, 7, 9, 11)
BOUNDS = {"Tenor": (30, 38), "Alto": (28, 34), "Treble": (30, 38), "Bass": (18, 26)}


def _parts(root):
    labels = {sp.get("id"): sp.findtext("{*}part-name") for sp in root.findall("{*}part-list/{*}score-part")}
    result = {labels.get(p.get("id")): p for p in root.findall("{*}part")}
    if not all(name in result for name in BOUNDS):
        raise ValueError("register fitting requires Treble, Alto, Tenor and Bass parts")
    return result


def _notes(part):
    return [n for n in part.findall("{*}measure/{*}note") if n.find("{*}pitch") is not None]


def _ordinal(note):
    return int(note.findtext("{*}pitch/{*}octave")) * 7 + STEPS.index(note.findtext("{*}pitch/{*}step"))


def _identity(note):
    return note.findtext("{*}pitch/{*}step"), int(note.findtext("{*}pitch/{*}alter", "0"))


def _range(part):
    notes = _notes(part)
    if not notes:
        return None
    def label(note):
        step, alter = _identity(note)
        return step + ({-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}.get(alter, f"({alter})")) + note.findtext("{*}pitch/{*}octave")
    return [label(min(notes, key=_ordinal)), label(max(notes, key=_ordinal))]


def _cost(values, name):
    if not values:
        return (0, 0, 0)
    low, high = BOUNDS[name]
    below = sum(max(low - value, 0) ** 2 for value in values)
    above = sum(max(value - high, 0) ** 2 for value in values)
    if name == "Tenor":
        return (below, above, (min(values) - low) ** 2 + (max(values) - high) ** 2)
    center = 30 if name == "Alto" else (low + high) / 2
    return (below + above, sum(abs(value - center) for value in values), 0)


def _choose_octave(part, name):
    values = [_ordinal(n) for n in _notes(part)]
    return min(range(-3, 4), key=lambda shift: (*_cost([v + shift * 7 for v in values], name), abs(shift)))


def _set_octave(part, shift):
    for note in _notes(part):
        octave = note.find("{*}pitch/{*}octave")
        octave.text = str(int(octave.text) + shift)


def _source_mode(parts, fifths, explicit, override):
    if override:
        return override, "explicit source-mode correction"
    if explicit in ("major", "minor"):
        return explicit, "explicit MusicXML mode"
    ends = [_identity(_notes(parts[name])[-1]) for name in ("Tenor", "Bass") if _notes(parts[name])]
    if len(ends) == 2 and ends[0] == ends[1]:
        for mode in ("major", "minor"):
            info = key_info(fifths, mode)
            if ends[0] == (info["step"], info["alter"]):
                return mode, "tenor and bass cadence agree with tonic"
    return "major", "mode uncertain; signature interpreted as major (review needed)"


def fit_registers(tree, *, target_key=None, source_mode=None, fixed_octaves=None):
    """Return a transposed copy plus an auditable key/register selection report.

    fixed_octaves are relative to the supplied four-part arrangement, after
    shared key transposition. Explicit choices override automatic fitting.
    """
    root = tree.getroot()
    parts = _parts(root)
    first_key = parts["Tenor"].find("{*}measure/{*}attributes/{*}key")
    if first_key is None:
        raise ValueError("register fitting needs an initial traditional key signature")
    fifths = int(first_key.findtext("{*}fifths"))
    mode, reason = _source_mode(parts, fifths, first_key.findtext("{*}mode"), source_mode)
    origin = key_info(fifths, mode)
    prepared = copy.deepcopy(tree)
    for key in prepared.getroot().findall(".//{*}attributes/{*}key"):
        mode_element = key.find("{*}mode")
        if mode_element is None:
            mode_element = ET.SubElement(key, key.tag[:-3] + "mode")
            mode_element.text = mode
        elif source_mode is not None:
            mode_element.text = mode
    candidates = [parse_key(target_key)] if target_key else [(f, mode) for f in range(-7, 8)]
    best = None
    for target_fifths, target_mode in candidates:
        if target_mode != mode:
            raise ValueError("key transposition must preserve the source mode")
        target = key_info(target_fifths, target_mode)
        # Pick the nearest chromatic spelling; voice octaves are fitted below.
        intervals = [(NATURAL[STEPS.index(target["step"])] + target["alter"] + 12 * octv
                      - NATURAL[STEPS.index(origin["step"])] - origin["alter"],
                      STEPS.index(target["step"]) + 7 * octv - STEPS.index(origin["step"]))
                     for octv in (-1, 0, 1)]
        chromatic, diatonic = min(intervals, key=lambda pair: (abs(pair[0]), abs(pair[1])))
        try:
            moved = transpose(prepared, chromatic, diatonic, target_fifths - fifths)
        except ValueError:
            if target_key:
                raise
            continue
        moved_parts = _parts(moved.getroot())
        shifts = {}
        costs = {}
        for name, part in moved_parts.items():
            shifts[name] = (fixed_octaves or {}).get(name, _choose_octave(part, name))
            _set_octave(part, shifts[name])
            costs[name] = _cost([_ordinal(n) for n in _notes(part)], name)
        # Tenor layout takes priority, then low alto, the other staffs, key simplicity.
        score = (*costs["Tenor"], costs["Alto"][0], costs["Treble"][0] + costs["Bass"][0],
                 abs(target_fifths), abs(chromatic))
        if best is None or score < best[0]:
            best = (score, moved, {"source_key": origin["name"], "source_mode_reason": reason,
                                  "target_key": target["name"], "semitones": chromatic,
                                  "diatonic_steps": diatonic, "octave_adjustments": shifts,
                                  "ranges": {n: _range(p) for n, p in moved_parts.items()},
                                  "tenor_below_E4": sum(_ordinal(n) < 30 for n in _notes(moved_parts["Tenor"])),
                                  "tenor_above_F5": sum(_ordinal(n) > 38 for n in _notes(moved_parts["Tenor"])),
                                  "explicit_target": target_key is not None,
                                  "mode_needs_review": "uncertain" in reason})
    if best is None:
        raise ValueError("no supported key spelling can fit this score")
    return best[1], best[2]


def arrange_for_singing(source, *, target_key=None, source_mode=None, octave_adjustments=None,
                        preserve_ambiguous_chords=False, initial_octave_shifts="auto"):
    """Shared processing entry point: split voices, then choose key and registers."""
    from .satb import arrange
    tree, report = arrange(source, octave_shifts=initial_octave_shifts,
                           preserve_ambiguous_chords=preserve_ambiguous_chords)
    tree, fitted = fit_registers(tree, target_key=target_key, source_mode=source_mode,
                                 fixed_octaves=octave_adjustments)
    report["initial_octave_shifts"] = report["octave_shifts"].copy()
    report["octave_shifts"] = {name: report["octave_shifts"][name] + fitted["octave_adjustments"][name]
                               for name in BOUNDS}
    report["register_fit"] = fitted
    return tree, report
