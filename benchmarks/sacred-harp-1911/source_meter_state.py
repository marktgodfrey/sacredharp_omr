"""Opt-in source-positioned meter propagation for a saved ``Reading``.

The detector's raw meter marks and the reader's measure-head meter attributes
are retained as evidence. A meter change is admitted only when parallel staves
agree at one source column; equal-duration signatures remain distinct values.
"""
from __future__ import annotations

from collections import defaultdict

RAW_GLYPH_MIN = 0.40
HEAD_TIME_MIN = 0.80


def _meter(value):
    if not isinstance(value, str) or value in ("", "other", "None"):
        return None
    if value.startswith("meterSig_"):
        value = value[len("meterSig_"):].replace("_", "/")
    if value.count("/") != 1:
        return None
    a, b = value.split("/")
    return value if a.isdigit() and b.isdigit() else None


def _pos_key(L, staff, bar):
    st = L.staves[staff]
    return st.system, L.column(staff, bar)


def source_meter_state(rd, *, raw_glyph_min=RAW_GLYPH_MIN, head_time_min=HEAD_TIME_MIN):
    """Return source-positioned consensus events and full evidence, without mutation.

    Candidate evidence comes from raw meter glyphs (their detector confidence,
    plus final Reading fields) and decoded time attributes on measure heads.
    Consensus is across at least two distinct staves in the same system column.
    Events are mapped to every staff's physical bar at that column and carried
    forward in page order; signatures are never collapsed by equal capacity.
    """
    L = rd.layout
    candidates = defaultdict(lambda: defaultdict(list))
    evidence = []
    for sym in L.syms:
        tok = rd.tok.get(sym.i, {})
        if sym.staff < 0 or sym.bar < 0 or sym.staff >= len(L.staves):
            continue
        if sym.bar >= len(L.staves[sym.staff].bars):
            continue
        key = _pos_key(L, sym.staff, sym.bar)
        cls = sym.cls
        if cls.startswith("meterSig_"):
            meter = _meter(cls)
            record = {"source": "raw_meter_glyph", "symbol": sym.i,
                      "raw_class": sym.cls, "raw_confidence": sym.p,
                      "reading_class": tok.get("cls", {}).copy(),
                      "reading_real": tok.get("real", {}).copy(),
                      "staff": sym.staff, "bar": sym.bar, "system": key[0],
                      "column": key[1], "x": sym.cx, "meter": meter,
                      "accepted_candidate": bool(meter and sym.p >= raw_glyph_min)}
            evidence.append(record)
            if meter and sym.p >= raw_glyph_min:
                candidates[key][meter].append((sym.staff, record))
        # Measure-head time values are independent evidence, useful when the
        # detector missed the printed signature glyph entirely.
        if (sym.fam == "measure" and L.staves[sym.staff].bars[sym.bar] == sym.i
                and key == (0, 0)):
            time = tok.get("time", {})
            meter = _meter(time.get("v"))
            if meter:
                record = {"source": "measure_head_time", "symbol": sym.i,
                          "value": time.get("v"), "confidence": time.get("p", 0),
                          "staff": sym.staff, "bar": sym.bar, "system": key[0],
                          "column": key[1], "x": sym.cx, "meter": meter,
                          "accepted_candidate": time.get("p", 0) >= head_time_min}
                evidence.append(record)
                if time.get("p", 0) >= head_time_min:
                    candidates[key][meter].append((sym.staff, record))

    events = []
    for (system, column), meters in sorted(candidates.items()):
        # A printed glyph is direct evidence of a local change. Copied or
        # conflicting measure-head attributes must not veto that mark.
        raw = {meter: [(sid, r) for sid, r in rows if r['source'] == 'raw_meter_glyph']
               for meter, rows in meters.items()}
        raw_accepted = [(meter, rows) for meter, rows in raw.items()
                        if len({staff for staff, _ in rows}) >= 2]
        accepted = raw_accepted or [(meter, rows) for meter, rows in meters.items()
                    if len({staff for staff, _ in rows}) >= 2]
        # Conflicting multi-staff values at one column are ambiguous.
        if len(accepted) != 1:
            continue
        meter, rows = accepted[0]
        staves = [sid for sid in L.systems[system].staves
                  if any(_pos_key(L, sid, bar) == (system, column)
                         for bar in range(len(L.staves[sid].bars)))]
        events.append({"system": system, "column": column, "meter": meter,
                       "supporting_staves": sorted({sid for sid, _ in rows}),
                       "bar_by_staff": {sid: next(bar for bar in range(len(L.staves[sid].bars))
                                                    if _pos_key(L, sid, bar) == (system, column))
                                        for sid in staves},
                       "evidence": [r for _, r in rows]})

    # Preserve local transitions, then carry the latest meter to every later
    # physical bar, including bars after a system break.
    by_staff_bar = {}
    current = None
    ordered = sorted(events, key=lambda e: (e["system"], e["column"]))
    transitions = []
    for event in ordered:
        if event["meter"] != current:
            transitions.append(dict(event))
            current = event["meter"]
    if transitions:
        all_bars = sorted((L.staves[sid].system, L.column(sid, bar), sid, bar)
                          for sid, st in enumerate(L.staves)
                          for bar in range(len(st.bars)))
        ti = 0
        active = None
        for system, column, sid, bar in all_bars:
            while ti < len(transitions) and (transitions[ti]["system"], transitions[ti]["column"]) <= (system, column):
                active = transitions[ti]["meter"]
                ti += 1
            if active is not None:
                by_staff_bar[sid, bar] = active
    return {"events": events, "transitions": transitions, "evidence": evidence,
            "meter_by_staff_bar": by_staff_bar}


def apply_source_meter_state(rd, state=None, **kwargs):
    """Install explicit time values in measure-head readings for downstream writing."""
    state = state or source_meter_state(rd, **kwargs)
    for (staff, bar), meter in state["meter_by_staff_bar"].items():
        si = rd.layout.staves[staff].bars[bar]
        rd.tok.setdefault(si, {})["time"] = {"v": meter, "p": 1.0,
            "source_meter_state": True}
    return state
