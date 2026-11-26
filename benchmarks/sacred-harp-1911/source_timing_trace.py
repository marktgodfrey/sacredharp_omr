"""Opt-in provenance for the writer's final bar timing and clipping decisions."""
from __future__ import annotations

import copy
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent.parent / "copisteria" / "src"))
from bar_recovery import capture_built
from audit_bar_meter import xml_inventory
from reader_trace import capture_writer_trace


def _event_ids(events):
    return [int(e.si) for e in events if getattr(e, "si", -1) >= 0]


def _source_identity(rd, event):
    si = int(getattr(event, "si", -1))
    if si < 0 or si >= len(rd.layout.syms):
        return {"symbol_id": si}
    s = rd.layout.syms[si]
    return {"symbol_id": si, "class": getattr(s, "cls", None),
            "staff": int(getattr(s, "staff", -1)), "source_bar": int(getattr(s, "bar", -1)),
            "box": list(getattr(s, "box", ()))}


@contextmanager
def _opening_meter(meter):
    """Temporarily force the supplied opening meter and always restore the hook."""
    if meter is None:
        yield
        return
    from copisteria import write
    original = write._page_meter
    write._page_meter = lambda *args, **kwargs: meter
    try:
        yield
    finally:
        write._page_meter = original


def write_timed(rd, image=None, opening=None, bar_transform=None):
    """Write once and return ``(xml, emitted_trace, timing, selected_pass)``.

    ``timing`` describes the selected, transformed built bars immediately before
    final clipping, then records actual XML spans and the writer's final chop.
    All temporary writer hooks are restored even when writing raises.
    """
    from copisteria import write

    selected_passes = []
    with _opening_meter(opening), capture_built() as passes, capture_writer_trace() as emitted:
        xml = write.write(rd, image=image, bar_transform=bar_transform)
        selected_passes.extend(passes)

    # capture_built provides the exact selected snapshot and its matching cuts.
    selected = next((p for p in reversed(selected_passes) if p["xml"] == xml), None)
    if selected is None:
        raise RuntimeError("writer did not expose its selected built pass")

    rows = []
    # Replay the writer's _chop on deep copies of each selected voice to make
    # source IDs and any shortened event explicit without mutating the snapshot.
    for part_no, measures in enumerate(selected["built"], 1):
        for measure_no, measure in enumerate(measures, 1):
            cut = selected["cuts"][measure_no - 1] if measure_no - 1 < len(selected["cuts"]) else None
            for row in measure["staves"]:
                if row is None:
                    continue
                local_meter = row["state"].get("time")
                staff_no = int(row["staff"])
                for voice_no, events in row["voices"].items():
                    _, end = write._voice_starts(events, write._time_len(local_meter))
                    clipped, dropped, shortened = [], [], []
                    if cut is not None:
                        original = copy.deepcopy(events)
                        chopped = write._chop(copy.deepcopy(events), cut)
                        # Match copied events by (si, kind, x, voice) while capturing
                        # mutations to duration/type on retained events.
                        kept_by_key = {(e.si, e.kind, e.x, e.voice): e for e in chopped}
                        for before in original:
                            key = (before.si, before.kind, before.x, before.voice)
                            after = kept_by_key.get(key)
                            if after is None:
                                dropped.append({**_source_identity(rd, before), 'event_kind': before.kind})
                            elif before.dur != after.dur or before.typ != after.typ or before.dots != after.dots:
                                shortened.append({**_source_identity(rd, before), "from": str(before.dur), "to": str(after.dur)})
                        clipped = [x["symbol_id"] for x in shortened]
                    rows.append({"part": part_no, "staff": staff_no, "bar": measure_no,
                                 "local_meter": local_meter, "source_bar": int(row["bar"]),
                                 "voice": int(voice_no), "source_event_ids": _event_ids(events),
                                 "voice_end_before_clip": str(end), "selected_cut": str(cut) if cut is not None else None,
                                 "clipped_event_ids": clipped,
                                 "dropped_head_ids": [x["symbol_id"] for x in dropped if x.get('event_kind') == 'note'],
                                 "dropped_events": dropped, "shortened_events": shortened})

    inventory = xml_inventory(xml)
    timing = {"opening_meter": selected["opening"], "bars": rows,
              'selected_cuts': [str(c) if c is not None else None for c in selected['cuts']],
              "xml_inventory": inventory, "emitted": emitted["emitted"]}
    return xml, emitted, timing, selected
