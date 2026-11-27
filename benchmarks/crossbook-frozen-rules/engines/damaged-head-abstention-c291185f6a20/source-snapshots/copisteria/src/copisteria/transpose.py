"""MusicXML pitch transposition with conventional circle-of-fifths keys.

``key_info(fifths, mode)`` returns a mapping with tonic ``step``, ``alter``
and conventional ``name``.
"""
from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET

STEPS = "CDEFGAB"
NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MAJOR_NAMES = ("Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#")
MINOR_NAMES = ("Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#", "G#", "D#", "A#")


def key_info(fifths: int, mode: str) -> dict[str, str | int]:
    """Return ``step``, ``alter``, and conventional tonic ``name`` for a key."""
    if isinstance(fifths, bool) or not isinstance(fifths, int) or not -7 <= fifths <= 7:
        raise ValueError("key fifths must be an integer from -7 through 7")
    mode = mode.lower()
    if mode not in ("major", "minor"):
        raise ValueError("key mode must be major or minor")
    name = (MAJOR_NAMES if mode == "major" else MINOR_NAMES)[fifths + 7]
    return {"step": name[0], "alter": (1 if name.endswith("#") else -1 if name.endswith("b") else 0),
            "name": name + ("m" if mode == "minor" else "")}


def parse_key(name: str) -> tuple[int, str]:
    """Parse a conventional major/minor tonic such as ``F#m`` or ``Cb major``."""
    text = name.strip().replace("♯", "#").replace("♭", "b")
    match = re.fullmatch(r"([A-Ga-g])([#b]?)(?:\s*(major|minor|maj|min|m))?", text, re.I)
    if not match:
        raise ValueError(f"invalid key name: {name!r}")
    letter, accidental, suffix = match.groups()
    mode = "minor" if suffix and suffix.lower() in ("minor", "min", "m") else "major"
    tonic = letter.upper() + accidental
    names = MINOR_NAMES if mode == "minor" else MAJOR_NAMES
    try:
        return names.index(tonic) - 7, mode
    except ValueError as exc:
        raise ValueError(f"unsupported conventional key: {name!r}") from exc


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(parent: ET.Element, name: str) -> ET.Element | None:
    return next((el for el in parent if _local(el.tag) == name), None)


def _accidental_name(alter: int) -> str:
    try:
        return {-2: "flat-flat", -1: "flat", 0: "natural", 1: "sharp", 2: "double-sharp"}[alter]
    except KeyError as exc:
        raise ValueError(f"unsupported transposed alteration: {alter}") from exc


def transpose(tree: ET.ElementTree, semitones: int, diatonic_steps: int,
              fifths_delta: int = 0, mode_override: str | None = None) -> ET.ElementTree:
    """Return a deep-copied score transposed by the supplied chromatic and diatonic interval."""
    if not isinstance(tree, ET.ElementTree):
        raise TypeError("tree must be an ElementTree")
    if mode_override is not None and mode_override not in ("major", "minor"):
        raise ValueError("mode_override must be 'major' or 'minor'")
    out = copy.deepcopy(tree)
    root = out.getroot()
    if _local(root.tag) != "score-partwise":
        raise ValueError("expected a MusicXML score-partwise document")
    for el in root.iter():
        if _local(el.tag) == "key":
            fifths_el = _child(el, "fifths")
            if fifths_el is None or not fifths_el.text:
                raise ValueError("unsupported nontraditional key signature")
            try:
                fifths = int(fifths_el.text.strip())
            except ValueError as exc:
                raise ValueError("invalid key fifths") from exc
            key_info(fifths, (_child(el, "mode").text.strip().lower()
                              if _child(el, "mode") is not None and _child(el, "mode").text else "major"))
            shifted = fifths + fifths_delta
            if not -7 <= shifted <= 7:
                raise ValueError(f"transposed key exceeds conventional range: {shifted} fifths")
            fifths_el.text = str(shifted)
            mode_el = _child(el, "mode")
            if mode_override is not None:
                if mode_el is None:
                    mode_el = ET.SubElement(el, f"{el.tag[:-len(_local(el.tag))]}mode")
                mode_el.text = mode_override

    for note in (el for el in root.iter() if _local(el.tag) == "note"):
        pitch = _child(note, "pitch")
        if pitch is None:
            continue
        step_el, octave_el = _child(pitch, "step"), _child(pitch, "octave")
        if step_el is None or octave_el is None or not step_el.text or not octave_el.text:
            continue
        step = step_el.text.strip().upper()
        if step not in STEPS:
            raise ValueError(f"unsupported pitch step: {step!r}")
        old_alter_el = _child(pitch, "alter")
        old_alter = float(old_alter_el.text) if old_alter_el is not None and old_alter_el.text else 0.0
        if not old_alter.is_integer():
            raise ValueError("microtonal pitch alterations are unsupported")
        old_alter = int(old_alter)
        old_octave = int(octave_el.text)
        diatonic = old_octave * 7 + STEPS.index(step) + diatonic_steps
        new_octave, new_idx = divmod(diatonic, 7)
        new_step = STEPS[new_idx]
        chromatic = (old_octave + 1) * 12 + NATURAL[step] + old_alter + semitones
        new_alter = chromatic - ((new_octave + 1) * 12 + NATURAL[new_step])
        accidental = _child(note, "accidental")
        glyph_name = _accidental_name(new_alter)
        accidental_name = glyph_name if accidental is not None else None
        step_el.text = new_step
        octave_el.text = str(new_octave)
        if new_alter == 0:
            if old_alter_el is not None:
                pitch.remove(old_alter_el)
        elif old_alter_el is None:
            old_alter_el = ET.Element(f"{pitch.tag[:-len(_local(pitch.tag))]}alter")
            pitch.insert(list(pitch).index(octave_el), old_alter_el)
            old_alter_el.text = str(new_alter)
        else:
            old_alter_el.text = str(new_alter)
        if accidental is not None:
            accidental.text = accidental_name
        for head in [e for e in note if _local(e.tag) == "notehead"]:
            note.remove(head)
    return out
