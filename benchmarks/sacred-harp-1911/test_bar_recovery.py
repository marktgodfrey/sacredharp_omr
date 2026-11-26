from copy import deepcopy
from fractions import Fraction
from types import SimpleNamespace as NS

import pytest

from bar_recovery import capture_built, select_candidate


def _event(si, x, pitch, *, chord=False):
    from copisteria.write import Event
    return Event(x=x, kind="note", typ="quarter", dur=Fraction(1), si=si,
                 step=pitch, octave=4, chord=chord)


def _reading_for(events):
    syms = [NS(i=i, staff=0, bar=0, box=(e.x - 4, 20, e.x + 4, 28)) for i, e in enumerate(events)]
    return NS(layout=NS(syms=syms, staves=[NS(sp=10.)]))


def test_candidate_that_loses_baseline_physical_pitch_is_rejected_even_with_gain():
    rd = _reading_for([_event(0, 10, "C"), _event(1, 30, "D"), _event(2, 50, "E")])
    baseline = {1: [_event(0, 10, "C"), _event(1, 30, "D")]}
    unsafe = {1: [_event(0, 10, "C"), _event(2, 50, "E")]}
    chosen, detail = select_candidate(rd, baseline, [("unsafe", unsafe)], Fraction(4),
                                      {2: {"stem_found": True}})
    assert detail["selected"] == "frozen"
    assert detail["trials"][0]["lost_physical_notes"] == [1]
    assert {e.si for e in chosen[1]} == {0, 1}


def test_different_symbol_id_same_physical_pitch_counts_as_retained():
    rd = _reading_for([_event(0, 10, "C"), _event(1, 10.2, "C"), _event(2, 35, "D")])
    baseline = {1: [_event(0, 10, "C")]}
    candidate = {1: [_event(1, 10.2, "C"), _event(2, 35, "D")]}
    chosen, detail = select_candidate(rd, baseline, [("recovered", candidate)], Fraction(4),
                                      {2: {"stem_found": True}})
    assert detail["selected"] == "recovered"
    assert detail["trials"][0]["lost_physical_notes"] == []
    assert detail["added_verified_heads"] == [2]
    assert {e.si for e in chosen[1]} == {1, 2}


def test_without_new_verified_head_recovery_keeps_frozen_candidate():
    rd = _reading_for([_event(0, 10, "C"), _event(1, 30, "D")])
    baseline = {1: [_event(0, 10, "C")]}
    alternate = {1: [_event(0, 10, "C"), _event(1, 30, "D")]}
    chosen, detail = select_candidate(rd, baseline, [("unverified_gain", alternate)], Fraction(4), {})
    assert detail["selected"] == "frozen"
    assert detail["added_verified_heads"] == []
    assert {e.si for e in chosen[1]} == {0}


def test_selection_does_not_mutate_any_candidate_input():
    rd = _reading_for([_event(0, 10, "C"), _event(1, 30, "D")])
    baseline = {1: [_event(0, 10, "C")]}
    alternate = {1: [_event(0, 10, "C"), _event(1, 30, "D")]}
    before = deepcopy((baseline, alternate))
    chosen, _ = select_candidate(rd, baseline, [("candidate", alternate)], Fraction(4),
                                 {1: {"stem_found": True}})
    assert (baseline, alternate) == before
    chosen[1][0].step = "G"
    assert baseline[1][0].step == "C"
    assert alternate[1][0].step == "C"


def _one_bar_reading():
    from copisteria import front
    from copisteria.read import Reading

    def det(cls, box, **attrs):
        return {"cls": cls, "conf": .9, "xyxy": list(box),
                **({"attrs": {k: str(v) for k, v in attrs.items()},
                    "attr_p": {k: .9 for k in attrs}} if attrs else {})}

    dets = [det("measure", (0, 100, 200, 140)),
        det("note_quarter", (50, 115, 60, 125), staff_position=0),
        det("note_quarter", (100, 115, 110, 125), staff_position=2),
        det("meterSig_2_4", (20, 100, 30, 140)),
    ]
    layout = front.build(dets, 300, 300)
    tok = {}
    for s in layout.syms:
        if s.fam == "measure":
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": "measure"},
                        "key": {"v": 0}, "time": {"v": "2/4"}, "clef": {"v": "G2"}}
        elif s.fam == "meterSig":
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": "meterSig_2_4"}}
        else:
            pos = 0 if s.cx < 80 else 2
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": "note_quarter"},
                        "dots": {"v": 0}, "pos": {"v": pos}, "voice": {"v": 1}, "tup": {"v": "none"},
                        "alter": {"v": 0}, "grace": {"v": "none"}, "chord": 0., "tie": 0.}
    return Reading(layout=layout, tok=tok)


def _cross_bar_tie_reading():
    from copisteria import front
    from copisteria.read import Reading

    def det(cls, box, **attrs):
        return {"cls": cls, "conf": .99, "xyxy": list(box),
                **({"attrs": {k: str(v) for k, v in attrs.items()},
                    "attr_p": {k: .99 for k in attrs}} if attrs else {})}

    dets = [det("measure", (0, 100, 100, 140)), det("measure", (100, 100, 200, 140)),
            det("note_quarter", (85, 115, 95, 125), staff_position=0),
            det("note_quarter", (105, 115, 115, 125), staff_position=0),
            det("meterSig_4_4", (10, 100, 20, 140)), det("curve", (94, 125, 106, 131))]
    layout = front.build(dets, 200, 300)
    tok = {}
    for s in layout.syms:
        if s.fam == "measure":
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": "measure"},
                        "key": {"v": 0}, "time": {"v": "4/4"}, "clef": {"v": "G2"}}
        elif s.fam == "meterSig":
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": "meterSig_4_4"}}
        elif s.fam == "curve":
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": "curve"}}
        else:
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": "note_quarter"},
                        "dots": {"v": 0}, "pos": {"v": 0}, "voice": {"v": 1}, "tup": {"v": "none"},
                        "alter": {"v": 0}, "grace": {"v": "none"}, "chord": 0.,
                        "tie": 1. if s.cx < 100 else 0.}
    return Reading(layout=layout, tok=tok)


def _pickup_final_reading():
    from copisteria import front
    from copisteria.read import Reading

    def det(cls, box, **attrs):
        return {"cls": cls, "conf": .99, "xyxy": list(box),
                **({"attrs": {k: str(v) for k, v in attrs.items()},
                    "attr_p": {k: .99 for k in attrs}} if attrs else {})}

    dets = []
    for y in (100, 200):
        dets.extend(det("measure", (x, y, x + 100, y + 40)) for x in (0, 100, 200))
    for y in (115, 215):
        for x in (70, 120, 220):
            dets.append(det("note_quarter", (x, y, x + 10, y + 10), staff_position=0))
        dets.append(det("meterSig_2_4", (10, y - 15, 20, y + 25)))
        dets.append(det("barLine_final", (270, y - 5, 275, y + 45)))
    layout = front.build(dets, 300, 300)
    tok = {}
    for s in layout.syms:
        if s.fam == "measure":
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": "measure"},
                        "key": {"v": 0}, "time": {"v": "2/4"}, "clef": {"v": "G2"}}
        elif s.fam in ("meterSig", "barLine"):
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": s.cls}}
        else:
            tok[s.i] = {"real": {"p": 1., "det": 1., "ev": 0}, "cls": {"v": "note_quarter"},
                        "dots": {"v": 0}, "pos": {"v": 0}, "voice": {"v": 1}, "tup": {"v": "none"},
                        "alter": {"v": 0}, "grace": {"v": "none"}, "chord": 0., "tie": 0.}
    return Reading(layout=layout, tok=tok)


def test_writer_transform_runs_before_ties_and_attachment_and_keeps_fixed_cut(monkeypatch):
    from copisteria import write
    rd = _one_bar_reading()
    observed = {}
    attach = write._attach
    drawn_ties = write._drawn_ties
    order = []

    def transform(built, opening):
        order.append("transform")
        observed["opening"] = opening
        observed["cut"] = write._column_lengths(built)
        observed["tie_before"] = any(e.tie_stop for m in built[0] for st in m["staves"] if st
                                      for vs in st["voices"].values() for e in vs)
        return built, [Fraction(1)]

    def check_attach(*args, **kwargs):
        order.append("attach")
        observed["tie_at_attach"] = any(e.tie_stop for measures in args[1] for m in measures
                                        for st in m["staves"] if st for vs in st["voices"].values() for e in vs)
        return attach(*args, **kwargs)

    def check_ties(*args, **kwargs):
        order.append("ties")
        return drawn_ties(*args, **kwargs)

    monkeypatch.setattr(write, "_attach", check_attach)
    monkeypatch.setattr(write, "_drawn_ties", check_ties)
    xml = write.write(rd, bar_transform=transform)
    # The chosen opening meter may be absent; the transform receives it as-is.
    assert observed["opening"] is None
    assert observed["cut"] == [Fraction(2)]
    assert observed["tie_before"] is False
    assert observed["tie_at_attach"] is False
    assert order.index("transform") < order.index("ties") < order.index("attach")
    assert xml.count("<note>") == 1
    assert "<duration>1</duration>" in xml


def test_capture_built_hook_is_restored_when_writer_raises(monkeypatch):
    from copisteria import write
    original = write.write
    rd = _one_bar_reading()

    def fail(*args, **kwargs):
        raise RuntimeError("attachment failure")

    monkeypatch.setattr(write, "_attach", fail)
    with capture_built() as passes:
        with pytest.raises(RuntimeError, match="attachment failure"):
            write.write(rd)
    assert write.write is original
    assert passes == []


def test_selected_replacement_gets_cross_bar_tie_stop(monkeypatch):
    from copisteria import write
    rd = _cross_bar_tie_reading()
    selected_partner = {}
    attach = write._attach

    def transform(built, opening):
        partner = next(e for e in built[0][1]["staves"][0]["voices"][1] if e.kind == "note")
        selected = deepcopy(partner)
        built[0][1]["staves"][0]["voices"][1] = [selected]
        selected_partner["event"] = selected
        return built, None

    def check_attach(*args, **kwargs):
        assert selected_partner["event"].tie_stop is True
        assert any(e is selected_partner["event"] for measures in args[1] for m in measures
                   for st in m["staves"] if st for vs in st["voices"].values() for e in vs)
        return attach(*args, **kwargs)

    monkeypatch.setattr(write, "_attach", check_attach)
    write.write(rd, bar_transform=transform)


def test_recovery_keeps_shared_pickup_and_final_complement_cuts():
    from copisteria import write
    from reader_policy import verify_reading
    from reader_trace import capture_writer_trace
    from bar_recovery import recovery_transform
    rd = _pickup_final_reading()
    verified = verify_reading(rd, None)
    for s in rd.layout.syms:
        if s.fam == "note":
            verified[s.i] = {"stem_found": True}

    with capture_built() as passes:
        write.write(rd)
    frozen_pass = passes[-1]
    expected = frozen_pass["cuts"]
    assert expected[0] < Fraction(2) and expected[-1] < Fraction(2)
    # Model the frozen bars as having lost their short pickup/complement notes;
    # recovery can select their verified source events, but cannot lengthen the
    # shared columns to nominal meter.
    for part in frozen_pass["built"]:
        for m_i in (0, len(part) - 1):
            for staff in part[m_i]["staves"]:
                if staff is not None:
                    staff["voices"] = {}
    decisions = []
    with capture_writer_trace() as emitted:
        xml = write.write(rd, bar_transform=recovery_transform(rd, frozen_pass, verified, decisions))
    assert [d["cut"] for d in decisions if d["measure"] in (1, len(expected))] == [
        str(expected[0]), str(expected[0]), str(expected[-1]), str(expected[-1])]
    selected = [d for d in decisions if d["measure"] in (1, len(expected))]
    assert len(selected) == 4 and all(d["selected"] != "frozen" for d in selected)
    assert len([e for e in emitted["emitted"] if e["kind"] == "note"]) == 6
    assert "<duration>1</duration>" in xml


def test_capture_composes_with_requested_bar_selection_and_keeps_its_cut():
    from copisteria import write
    def select(built, opening):
        return built, [Fraction(1)]
    with capture_built() as passes:
        xml = write.write(_one_bar_reading(), bar_transform=select)
    assert len(passes) == 1
    assert passes[0]['cuts'] == [Fraction(1)]
    assert passes[0]['xml'] == xml
    assert xml.count('<note>') == 1

