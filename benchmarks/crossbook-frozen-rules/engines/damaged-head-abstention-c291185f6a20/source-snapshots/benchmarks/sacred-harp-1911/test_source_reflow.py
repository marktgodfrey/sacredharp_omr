from copy import deepcopy
from fractions import Fraction

from copisteria.front import Layout, Staff, Sym, System
from copisteria.read import Reading
from copisteria.write import Event

from source_reflow import reflow_transform


def _layout(bar_count=1, staff_count=1, columns=None):
    syms = []
    staves = []
    for k in range(staff_count):
        y = k * 140
        bars = []
        for j in range(bar_count):
            i = len(syms)
            bars.append(i)
            syms.append(Sym(i, "measure", {}, 1, 1, [100 + j * 300, y, 380 + j * 300, y + 80],
                            staff=k, bar=j))
        for j in range(bar_count):
            i = len(syms)
            syms.append(Sym(i, "note_quarter", {}, 1, 1,
                            [170 + j * 300, y + 20, 190 + j * 300, y + 40],
                            staff=k, bar=j))
        staves.append(Staff(bars=bars, sp=20, y0=y, y1=y + 80, x0=100, x1=700,
                            system=0, pos=k))
    cols = columns or [list(range(bar_count)) for _ in range(staff_count)]
    system = System(staves=list(range(staff_count)), columns=cols)
    return Layout(syms, staves, [system], 20, 1000, 140 * staff_count)


def _event(si, step="C", octave=4, dur=1, voice=1):
    return Event(x=170, kind="note", typ="quarter", step=step, octave=octave,
                 dur=Fraction(dur), si=si, voice=voice)


def _built(rows):
    return [[{"staves": rows}]]


def _row(staff, bar, events, clef="G2"):
    return {"staff": staff, "bar": bar, "voices": {1: events}, "state": {"clef": clef, "key": 0}}


def test_ordinary_reflow_preserves_pitched_ids_values_and_durations(monkeypatch):
    layout = _layout(bar_count=1, staff_count=2)
    rd = Reading(layout, {})
    e0, e1 = _event(1, "C", 4, Fraction(3, 2)), _event(3, "E", 4, 2)
    rows = [_row(0, 0, [e0]), _row(1, 0, [e1])]
    prior = {"built": _built(rows), "cuts": [Fraction(4)]}
    transform = reflow_transform(rd, prior, deepcopy(layout), [])
    selected, cuts = transform(deepcopy(prior["built"]), "4/4")
    result = [r["voices"][1][0] for r in selected[0][0]["staves"]]
    assert [(e.si, e.step, e.octave, e.dur) for e in result] == [
        (1, "C", 4, Fraction(3, 2)), (3, "E", 4, Fraction(2))]
    assert cuts == [Fraction(4)]


def test_merged_old_bars_use_each_events_physical_bar_without_duplicates(monkeypatch):
    layout = _layout(bar_count=2, staff_count=1, columns=[[0, 0]])
    rd = Reading(layout, {})
    e0, e1 = _event(2, "C", 4, 1), _event(3, "D", 4, 1)
    row = _row(0, 0, [e0, e1])
    prior = {"built": _built([row]), "cuts": [Fraction(4)]}
    transform = reflow_transform(rd, prior, deepcopy(layout), [])
    selected, _ = transform(deepcopy(prior["built"]), "4/4")
    events = selected[0][0]["staves"][0]["voices"][1]
    assert [e.si for e in events] == [2, 3]
    assert len({e.si for e in events}) == len(events)


def test_reflow_maps_old_single_staff_systems_into_repaired_four_staff_system():
    layout = _layout(bar_count=1, staff_count=4)
    # The old reading represented four source rows as separate systems; the
    # repaired layout presents those same rows in one four-staff system.
    layout.systems[:] = [System([k], [[0]]) for k in range(4)]
    for k, staff in enumerate(layout.staves):
        staff.system, staff.pos = k, 0
    original_measures = [{"staves": [_row(k, 0, [_event(2 * k + 1, "CDEFGAB"[k], 4, 1)])]}
                         for k in range(4)]
    prior = {"built": [original_measures], "cuts": [Fraction(4)] * 4}
    layout.systems[:] = [System([0, 1, 2, 3], [[0], [0], [0], [0]])]
    for k, staff in enumerate(layout.staves):
        staff.system, staff.pos = 0, k
    rd = Reading(layout, {})
    new_rows = [_row(k, 0, []) for k in range(4)]
    transform = reflow_transform(rd, prior, deepcopy(layout), [])
    selected, _ = transform(_built(new_rows), "4/4")
    got = [(r["staff"], e.si, e.step) for r in selected[0][0]["staves"]
           for e in r["voices"][1]]
    assert got == [(0, 1, "C"), (1, 3, "D"), (2, 5, "E"), (3, 7, "F")]


def test_pitch_refresh_uses_current_source_staff_clef(monkeypatch):
    from copisteria import write

    layout = _layout(bar_count=1, staff_count=1)
    rd = Reading(layout, {})
    existing = _event(1, "C", 4, 1)
    prior = {"built": _built([_row(0, 0, [existing], clef="F4")]), "cuts": [Fraction(4)]}
    seen = []

    def events(_rd, _staff, _bar, clef, key, _texts):
        seen.append((clef, key))
        return [_event(1, "G" if clef == "F4" else "C", 3 if clef == "F4" else 4)], [], {}

    monkeypatch.setattr(write, "_events", events)
    decisions = []
    transform = reflow_transform(rd, prior, deepcopy(layout), decisions)
    selected, _ = transform(deepcopy(prior["built"]), "4/4")
    refreshed = selected[0][0]["staves"][0]["voices"][1][0]
    assert seen == [("F4", 0)]
    assert (refreshed.step, refreshed.octave) == ("G", 3)
    assert decisions == [{"action": "source_staff_pitch", "sym_id": 1,
        "from": ["C", 4, 0], "to": ["G", 3, 0], "clef": "F4", "key": 0}]
