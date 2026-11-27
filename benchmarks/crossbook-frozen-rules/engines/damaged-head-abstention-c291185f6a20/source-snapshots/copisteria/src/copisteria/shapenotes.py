"""Set four-shape Sacred Harp noteheads in a MusicXML partwise score.

This is a notation-only transform: pitches, rhythms, voices, lyrics and all
other MusicXML content are kept intact.  The diatonic letter determines the
shape; chromatic alterations do not.
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


STEPS = "CDEFGAB"
SHAPES = ("fa", "so", "la", "fa", "so", "la", "mi")
MAJOR_TONIC = {0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F", 7: "C",
               -1: "F", -2: "B", -3: "E", -4: "A", -5: "D", -6: "G", -7: "C"}
MINOR_TONIC = {0: "A", 1: "E", 2: "B", 3: "F", 4: "C", 5: "G", 6: "D", 7: "A",
               -1: "D", -2: "G", -3: "C", -4: "F", -5: "B", -6: "E", -7: "A"}
NOTE_CHILD_ORDER = ("notehead-text", "staff", "beam", "notations", "lyric", "play", "listen")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(parent: ET.Element, name: str) -> ET.Element | None:
    return next((e for e in parent if _local(e.tag) == name), None)


def _tonic_from_key(key: ET.Element) -> tuple[str, str]:
    """Read only ordinary circle-of-fifths major/minor signatures."""
    fifths_el = _child(key, "fifths")
    mode_el = _child(key, "mode")
    if fifths_el is None or fifths_el.text is None:
        raise ValueError("unsupported nontraditional key signature (missing fifths)")
    try:
        fifths = int(fifths_el.text.strip())
    except ValueError as exc:
        raise ValueError(f"unsupported key fifths: {fifths_el.text!r}") from exc
    mode = (mode_el.text.strip().lower() if mode_el is not None and mode_el.text else "major")
    if mode not in ("major", "minor"):
        raise ValueError(f"unsupported key mode: {mode!r}")
    table = MAJOR_TONIC if mode == "major" else MINOR_TONIC
    if fifths not in table:
        raise ValueError(f"unsupported nontraditional key signature: {fifths} fifths")
    return table[fifths], mode


def _relative_major(tonic: str, mode: str) -> str:
    return STEPS[(STEPS.index(tonic) + (2 if mode == "minor" else 0)) % 7]


def _shape(step: str, relative_major: str) -> str:
    degree = (STEPS.index(step) - STEPS.index(relative_major)) % 7
    return SHAPES[degree]


def _set_notehead(note: ET.Element, shape: str) -> None:
    heads = [e for e in note if _local(e.tag) == "notehead"]
    if heads:
        head = heads[0]
        head.text = shape
        # A previous explicit glyph would override the newly selected shape.
        head.attrib.pop("smufl", None)
        for extra in heads[1:]:
            note.remove(extra)
        return
    namespace = note.tag[:-len(_local(note.tag))]
    head = ET.Element(f"{namespace}notehead")
    # notehead belongs after stem and before staff/beam/notations/lyrics.
    index = next((i for i, e in enumerate(note) if _local(e.tag) in NOTE_CHILD_ORDER), len(note))
    head.text = shape
    note.insert(index, head)


def transform(source: str | Path | bytes, *, tonic: str | None = None,
              mode: str | None = None) -> tuple[ET.ElementTree, bool]:
    """Transform a partwise MusicXML tree; return ``(tree, assumed_default_key)``.

    ``tonic`` and ``mode`` override the tonal center globally. If no override
    is supplied, each part/staff follows its key signatures, defaulting to C
    major when the score contains no key at all.
    """
    if tonic is not None:
        tonic = tonic.upper()
        if tonic not in tuple(STEPS):
            raise ValueError("tonic must be a diatonic step C, D, E, F, G, A, or B")
    if mode is not None:
        mode = mode.lower()
        if mode not in ("major", "minor"):
            raise ValueError("mode must be major or minor")
    if (tonic is None) != (mode is None):
        raise ValueError("--tonic and --mode must be supplied together")
    tree = ET.parse(source) if not isinstance(source, bytes) else ET.ElementTree(ET.fromstring(source))
    root = tree.getroot()
    if _local(root.tag) != "score-partwise":
        raise ValueError("expected a MusicXML score-partwise document")

    used_default = False
    # Keep the source namespace URI (and the common default namespace spelling)
    # when ElementTree serializes the result.
    if root.tag.startswith("{"):
        ET.register_namespace("", root.tag[1:].split("}", 1)[0])
    for part in (e for e in root if _local(e.tag) == "part"):
        default_key = ("C", "major")
        has_default_key = False
        staff_keys: dict[str, tuple[str, str]] = {}
        for measure in (e for e in part if _local(e.tag) == "measure"):
            for item in list(measure):
                if _local(item.tag) == "attributes":
                    for key_el in (e for e in item if _local(e.tag) == "key"):
                        key = _tonic_from_key(key_el)  # validate unsupported keys even with an override
                        staff_no = key_el.get("number")
                        if staff_no is None:
                            default_key = key
                            has_default_key = True
                            staff_keys.clear()
                        else:
                            staff_keys[staff_no] = key
                elif _local(item.tag) == "note":
                    pitch = _child(item, "pitch")
                    step_el = _child(pitch, "step") if pitch is not None else None
                    if step_el is None or not step_el.text:
                        continue  # rests and unpitched notes have no scale degree
                    step = step_el.text.strip().upper()
                    if step not in tuple(STEPS):
                        raise ValueError(f"unsupported pitch step: {step!r}")
                    staff_el = _child(item, "staff")
                    staff_no = staff_el.text.strip() if staff_el is not None and staff_el.text else "1"
                    if tonic is None and staff_no not in staff_keys and not has_default_key:
                        used_default = True
                    key_tonic, key_mode = staff_keys.get(staff_no, default_key)
                    selected_tonic, selected_mode = ((tonic, mode) if tonic is not None else (key_tonic, key_mode))
                    _set_notehead(item, _shape(step, _relative_major(selected_tonic, selected_mode)))
    return tree, used_default and tonic is None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--tonic", choices=tuple(STEPS), help="override tonic step (requires --mode)")
    parser.add_argument("--mode", choices=("major", "minor"), help="override major/minor mode (requires --tonic)")
    args = parser.parse_args(argv)
    try:
        tree, assumed = transform(args.input, tonic=args.tonic, mode=args.mode)
    except (ET.ParseError, OSError, ValueError) as exc:
        parser.error(str(exc))
    tree.write(args.out, encoding="utf-8", xml_declaration=True)
    print(json.dumps({"input": str(args.input), "output": str(args.out),
                      "assumption": "C major (no key signature found)" if assumed else None}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
