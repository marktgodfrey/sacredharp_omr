#!/usr/bin/env python3
"""Replay saved reader-gallery writer traces without running either model."""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from fractions import Fraction

from PIL import Image

ROOT = Path(__file__).resolve().parent
TRANS = ROOT / "reader-gallery" / "transcriptions"
OUT = ROOT / "diagnostics" / "miss-trace" / "replays"

# Import the local package when invoked as a standalone benchmark script.
sys.path.insert(0, str(ROOT.parent.parent / "copisteria" / "src"))
from copisteria import front, write
from copisteria.read import Reading


def _records(title: str):
    manifest = json.loads((ROOT / "reader-gallery" / "manifest.json").read_text())
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())
    matches = [s for s in manifest["samples"] if norm(s["title"]) == norm(title)]
    if len(matches) != 1:
        raise ValueError(f"title {title!r}: expected one manifest match, got {len(matches)}")
    sample = matches[0]
    tid = sample["id"]
    trace_path = TRANS / f"{tid}.trace.json"
    report_path = TRANS / f"{tid}.report.json"
    trace = json.loads(trace_path.read_text())
    report = json.loads(report_path.read_text())
    image_path = ROOT / sample["input"]
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    return sample, trace, report, trace_path, report_path, image_path


def _reading(trace: dict, image: Image.Image):
    syms = []
    for d in trace["syms"]:
        syms.append(front.Sym(
            i=int(d["i"]), cls=d["cls"], post={int(k): float(v) for k, v in d["post"].items()},
            p=float(d["p"]), n=int(d["n"]), box=tuple(map(float, d["box"])), attrs=d.get("attrs", {}),
            attr_p=d.get("attr_p", {}), attr_dist=d.get("attr_dist", {}), staff=int(d.get("staff", -1)),
            bar=int(d.get("bar", -1)), synthetic=bool(d.get("synthetic", False)),
            det=int(d.get("det", -1)), cand=bool(d.get("cand", False))))
    staves = [front.Staff(bars=list(map(int, s["bars"])), sp=float(s["sp"]), y0=float(s["y0"]),
                          y1=float(s["y1"]), x0=float(s["x0"]), x1=float(s["x1"]),
                          system=int(s.get("system", -1)), pos=int(s.get("pos", -1)),
                          line_x0=s.get("line_x0")) for s in trace["staves"]]
    systems = [front.System(staves=list(map(int, s["staves"])),
                            columns=[list(map(int, c)) for c in s.get("columns", [])])
               for s in trace["systems"]]
    sp = sorted(s.sp for s in staves)
    layout = front.Layout(syms, staves, systems, sp[len(sp)//2] if sp else 10.0,
                          float(image.width), float(image.height), ink=True)
    tok = {int(k): v for k, v in trace["tokens"].items()}
    return Reading(layout, tok)


def _event(e):
    return {"si": int(e.si), "kind": e.kind, "x": float(e.x), "step": e.step,
            "octave": int(e.octave), "alter": int(e.alter), "typ": e.typ, "dots": int(e.dots),
            "tup": e.tup, "dur": str(e.dur), "voice": int(e.voice), "chord": bool(e.chord),
            "grace": e.grace}


def _pitched_xml(xml: str):
    root = ET.fromstring(xml)
    seq = []
    for note in root.findall(".//note"):
        if note.find("rest") is not None or note.find("pitch") is None:
            continue
        p = note.find("pitch")
        alter = int(p.findtext("alter", "0"))
        seq.append({"step": p.findtext("step"), "octave": int(p.findtext("octave")),
                    "alter": alter, "dur": int(note.findtext("duration", "0"))})
    return seq


def replay(title: str):
    sample, trace, report, trace_path, report_path, image_path = _records(title)
    with Image.open(image_path) as im:
        source_image = im.convert("L")
    if report.get("layout_choice") == "normalized":
        import numpy as np
        from copisteria.front import clean_page
        image = Image.fromarray(clean_page(np.asarray(source_image)))
    else:
        image = source_image
    rd = _reading(trace, image)
    stages = {"events": [], "voices": [], "chops": [], "serialized_notes": []}
    originals = {name: getattr(write, name) for name in ("_events", "_voices", "_chop", "_note")}

    def wrap_events(*args, **kwargs):
        result = originals["_events"](*args, **kwargs)
        evs, dirs, marks = result
        stages["events"].append({"staff": args[1], "bar": args[2], "events": [_event(e) for e in evs]})
        return result

    def wrap_voices(events, *args, **kwargs):
        result = originals["_voices"](events, *args, **kwargs)
        stages["voices"].append({"input": [_event(e) for e in events],
                                 "output": {str(k): [_event(e) for e in v] for k, v in result.items()}})
        return result

    def wrap_chop(evs, cut):
        before = [_event(e) for e in evs]
        result = originals["_chop"](evs, cut)
        kept_ids = {id(e) for e in result}
        stages["chops"].append({"cut": str(cut), "input": before,
                                "kept": [_event(e) for e in result],
                                "dropped": [x for e, x in zip(evs, before) if id(e) not in kept_ids]})
        return result

    def wrap_note(meas, e, dur, voice, staff_no, whole_rest=False):
        stages["serialized_notes"].append({**_event(e), "xml_duration": int(dur), "voice": int(voice),
                                           "staff_no": staff_no})
        return originals["_note"](meas, e, dur, voice, staff_no, whole_rest=whole_rest)

    try:
        write._events, write._voices, write._chop, write._note = wrap_events, wrap_voices, wrap_chop, wrap_note
        xml = write.write(rd, image=image)
    finally:
        for name, fn in originals.items():
            setattr(write, name, fn)

    emitted = trace.get("writer", {}).get("emitted", [])
    saved_notes = [{"step": e.get("step"), "octave": e.get("octave"), "alter": e.get("alter", 0),
                    "dur": e.get("dur"), "si": e.get("e.si")}
                   for e in emitted if e.get("kind") == "note"]
    # Captured _note calls preserve source si after clipping and immediately before XML serialization.
    xml_notes = _pitched_xml(xml)
    saved_xml_shape = [{k: e[k] for k in ("step", "octave", "alter", "dur")} for e in saved_notes]
    xml_match = len(saved_xml_shape) == len(xml_notes) and all(
        a["step"] == b["step"] and a["octave"] == b["octave"] and a["alter"] == b["alter"] and
        int(a["dur"]) == b["dur"] for a, b in zip(saved_xml_shape, xml_notes))
    replay_notes = [{"step": e["step"], "octave": e["octave"], "alter": e["alter"],
                     "dur": e["xml_duration"], "si": e["si"]}
                    for e in stages["serialized_notes"] if e["kind"] == "note"]
    replay_sequence_match = replay_notes == saved_notes
    captured_ids = Counter(e["si"] for e in replay_notes)
    saved_ids = Counter(e["si"] for e in saved_notes)
    ids_match = captured_ids == saved_ids
    status = "EXACT" if xml_match and replay_sequence_match and ids_match else "MISMATCH"
    result = {"title": sample["title"], "id": sample["id"], "layout_choice": report.get("layout_choice"),
              "image": str(image_path.relative_to(ROOT)), "image_variant": report.get("layout_choice"),
              "source_dimensions": [source_image.width, source_image.height],
              "verification": {"status": status, "xml_pitched_sequence_matches_saved": xml_match,
                               "serialized_pitch_duration_si_sequence_matches_saved": replay_sequence_match,
                               "serialized_source_si_multiset_matches_saved_notes": ids_match,
                               "saved_note_count": len(saved_notes), "xml_pitched_note_count": len(xml_notes),
                               "saved_si_only_in_saved_notes": sorted((saved_ids - captured_ids).elements()),
                               "replay_sequence_first_mismatch": next((i for i, (a, b) in enumerate(zip(saved_notes, replay_notes)) if a != b), None) if not replay_sequence_match else None,
                               "replay_sequence_lengths": [len(saved_notes), len(replay_notes)],
                               "captured_si_only_in_events": sorted((captured_ids - saved_ids).elements())},
              "sources": {"trace": str(trace_path.relative_to(ROOT)), "report": str(report_path.relative_to(ROOT))},
              "stages": stages, "saved_writer_emitted": emitted,
              "xml_pitched_notes": xml_notes, "replayed_musicxml": xml}
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"{sample['id']}.replay.json"
    out_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{sample['title']}: {status} xml={xml_match} si={ids_match} -> {out_path}")
    return status


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--titles", nargs="+", required=True, help="exact gallery titles to replay")
    args = ap.parse_args()
    failures = 0
    for title in args.titles:
        try:
            failures += replay(title) != "EXACT"
        except Exception as exc:
            failures += 1
            print(f"{title}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
