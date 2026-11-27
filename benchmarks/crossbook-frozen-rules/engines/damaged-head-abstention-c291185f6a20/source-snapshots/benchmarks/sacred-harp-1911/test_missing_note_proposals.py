"""Regression tests for opt-in, source-supported note alternatives."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from copisteria.front import Layout, Staff, Sym, System
from copisteria.vocab import CLS_ID
from head_morphology import head_morphology
from missing_note_proposals import (append_alternative, proposal_sites,
                                    suppress_measure_rest_conflicts, visual_alternative)


def _trace_reading(song_id):
    path = ROOT / "experiments" / "local-recovery" / "final-0996d2a689dc" / "note_rest" / f"{song_id}.trace.json"
    data = json.loads(path.read_text())
    syms = [Sym(
        i=s["i"], cls=s["cls"], post={int(k): v for k, v in s["post"].items()}, p=s["p"], n=s["n"],
        box=tuple(s["box"]), attrs=s.get("attrs", {}), attr_p=s.get("attr_p", {}),
        attr_dist=s.get("attr_dist", {}), staff=s["staff"], bar=s["bar"],
        synthetic=s.get("synthetic", False), cand=s.get("cand", False),
    ) for s in data["syms"]]
    layout = Layout(syms, [Staff(**s) for s in data["staves"]],
                    [System(**s) for s in data["systems"]], float(data.get("sp", 0)), 0, 0)
    return SimpleNamespace(layout=layout, tok={int(k): v for k, v in data["tokens"].items()})


def _record(box, score, note_mass=1.0):
    class_probabilities = {
        "note_quarter": note_mass * (2 / 3),
        "note_half": note_mass * (1 / 3),
        "rest_half": 1 - note_mass,
    }
    return {
        "refined_source_xyxy": list(box),
        "objectness_probability": score,
        # Keep the legacy field consistent for readability; selection now
        # recomputes the allowed note mass from these class probabilities.
        "note_family_mass": note_mass,
        "class_probabilities": class_probabilities,
        "best_note": "note_quarter",
        "attributes": {},
    }


def test_visual_alternative_rejects_adjacent_and_oversized_rois():
    site = {"box": [100, 100, 120, 120], "staff_space": 10}
    valid = _record([101, 101, 119, 119], 0.3, 0.2)
    adjacent = _record([125, 100, 145, 120], 0.99, 1.0)
    oversized = _record([80, 80, 140, 140], 1.0, 1.0)

    selected = visual_alternative({"records": [valid, adjacent, oversized]}, site)
    assert selected is not None
    assert selected["record"] is valid
    assert selected["visual_note_probability"] == pytest.approx(0.06)
    assert visual_alternative({"records": [adjacent, oversized]}, site) is None


def test_visual_selection_uses_position_without_relabeling_raw_probability():
    site = {'box': [100, 100, 120, 120], 'staff_space': 10, 'geometry_position': 0}
    wrong_position = _record([101, 101, 119, 119], .9, 1.)
    right_position = _record([101, 101, 119, 119], .4, 1.)
    wrong_position['attributes'] = {'staff_position': {'8': 1.}}
    right_position['attributes'] = {'staff_position': {'0': .9, '8': .1}}
    selected = visual_alternative({'records': [wrong_position, right_position]}, site)
    assert selected['record'] is right_position
    assert selected['visual_note_probability'] == pytest.approx(.4)
    assert selected['position_weighted_selection_score'] == pytest.approx(.36)


def test_append_keeps_raw_visual_mass_and_fixed_layout_assignments():
    bar = Sym(0, "measure", {CLS_ID["measure"]: 1.0}, 1.0, 1, (0, 0, 100, 40), staff=0, bar=0)
    layout = Layout([bar], [Staff([0], 10, 0, 40, 0, 100, system=0, pos=0)],
                    [System([0], [[0]])], 10, 100, 60)
    rd = SimpleNamespace(layout=layout, tok={})
    site = {"box": [40, 15, 50, 25], "staff": 0, "bar": 0}
    before = (layout.syms[0], list(layout.staves[0].bars), [list(c) for c in layout.systems[0].columns])
    alt = {
        "visual_note_probability": 0.4 * 0.3,
        "record": {
            "best_note": "note_quarter",
            "class_probabilities": {"note_quarter": 0.2, "note_half": 0.1, "rest_half": 0.7},
            "attributes": {},
        },
    }

    idx = append_alternative(rd, site, alt)

    appended = layout.syms[idx]
    assert rd.layout is layout
    assert idx == 1
    assert appended.i == idx and appended.staff == 0 and appended.bar == 0
    assert appended.box == tuple(site["box"])
    assert appended.p == pytest.approx(0.12)  # objectness * total note mass, not conditionalized to 1
    assert sum(appended.post.values()) == pytest.approx(1.0)
    assert appended.post[CLS_ID["note_quarter"]] == pytest.approx(2 / 3)
    assert appended.post[CLS_ID["note_half"]] == pytest.approx(1 / 3)
    assert layout.syms[0] is before[0]
    assert layout.staves[0].bars == before[1]
    assert layout.systems[0].columns == before[2]


def test_filled_head_removes_open_duration_mass_without_inflating_probability():
    site = {"box": [100, 100, 120, 120], "staff_space": 10,
            "head_evidence": {"head_ink_fraction": 0.7}}
    record = {
        "refined_source_xyxy": [101, 101, 119, 119],
        "objectness_probability": 0.5,
        "class_probabilities": {"note_quarter": 0.1, "note_half": 0.2, "note_whole": 0.1, "rest_half": 0.6},
        "best_note": "note_half",
        "attributes": {},
    }
    alt = visual_alternative({"records": [record]}, site)
    assert alt is not None
    # The raw visual score retains only the filled-head-compatible quarter mass.
    assert alt["visual_note_probability"] == pytest.approx(0.5 * 0.1)

    rd = SimpleNamespace(layout=Layout([], [], [], 10, 100, 60), tok={})
    idx = append_alternative(rd, {**site, "staff": 0, "bar": 0}, alt)
    appended = rd.layout.syms[idx]
    assert appended.cls == "note_quarter"
    assert appended.p == pytest.approx(0.05)
    assert set(appended.post) == {CLS_ID["note_quarter"]}
    assert sum(appended.post.values()) == pytest.approx(1.0)


def test_hollow_source_morphology_limits_appended_durations_without_inflating_mass():
    source = ROOT / "sources" / "1911-Origin-JPK-0308.jpg"
    if not source.exists():
        pytest.skip("cached M095 source scan is unavailable")
    morphology = head_morphology(Image.open(source), (1604.1, 946.8, 1638.7, 985.8), 177)
    assert morphology["hollow_head"]

    site = {"box": [1604.1, 946.8, 1638.7, 985.8], "staff_space": 35,
            "staff": 0, "bar": 0, "head_morphology": morphology}
    record = {
        "refined_source_xyxy": [1605, 948, 1637, 985],
        "objectness_probability": 0.4,
        "note_family_mass": 0.75,
        "class_probabilities": {
            "note_quarter": 0.2, "note_eighth": 0.1, "note_half": 0.2,
            "note_whole": 0.1, "note_breve": 0.1, "note_long": 0.05,
            "rest_half": 0.25,
        },
        "best_note": "note_quarter",
        "attributes": {},
    }
    alt = visual_alternative({"records": [record]}, site)
    assert alt is not None
    assert alt["visual_note_probability"] == pytest.approx(0.4 * 0.75)

    rd = SimpleNamespace(layout=Layout([], [], [], 10, 100, 60), tok={})
    idx = append_alternative(rd, site, alt)
    appended = rd.layout.syms[idx]
    allowed = {CLS_ID["note_half"], CLS_ID["note_whole"], CLS_ID["note_breve"], CLS_ID["note_long"]}
    assert set(appended.post) == allowed
    assert appended.cls in {"note_half", "note_whole", "note_breve", "note_long"}
    assert appended.p == pytest.approx(0.30)
    assert sum(appended.post.values()) == pytest.approx(1.0)


def test_proposal_sites_excludes_four_confirmed_clamanda_rest_boxes():
    source = ROOT / "sources" / "1911-Origin-JPK-0052.jpg"
    trace = ROOT / "experiments" / "local-recovery" / "final-0996d2a689dc" / "note_rest" / "1911-Origin-JPK-0052.trace.json"
    if not source.exists() or not trace.exists():
        pytest.skip("cached Clamanda source scan or saved reading is unavailable")
    rd = _trace_reading("1911-Origin-JPK-0052")
    sites = proposal_sites(rd, Image.open(source).convert("L"))
    confirmed_rest_ids = {117, 19, 70, 139}
    assert not confirmed_rest_ids.intersection(site["anchor_id"] for site in sites)
    # Source review identifies these as hollow square notes (IDs 449/451/468)
    # and hollow square notes with downward stems (454/456), not measure rests.
    source_note_measure_ids = {449, 451, 454, 456, 468}
    assert source_note_measure_ids <= {site["anchor_id"] for site in sites}


def test_greenland_mrest_measure_at_m056_is_a_proposal_site():
    song_id = "1911-s0316-greenland"
    sample = next(s for s in json.loads((ROOT / "manifest.json").read_text())["samples"] if s["id"] == song_id)
    source = ROOT / sample["input"]
    trace = ROOT / "experiments" / "local-recovery" / "final-0996d2a689dc" / "note_rest" / f"{song_id}.trace.json"
    if not source.exists() or not trace.exists():
        pytest.skip("cached Greenland source scan or saved reading is unavailable")
    rd = _trace_reading(song_id)
    site = next((site for site in proposal_sites(rd, Image.open(source).convert("L"))
                 if site["anchor_id"] == 586), None)
    assert site is not None
    assert site["box"] == [3701.3, 1017.7, 3733.3, 1051.2]
    assert site["staff"] == 1 and site["bar"] == 16


def _symbol(i, cls, staff, bar):
    return Sym(i, cls, {CLS_ID[cls]: 1.0}, 0.9, 1, (i * 20, 0, i * 20 + 10, 10), staff=staff, bar=bar)


def _token(cls, real_p, voice=1):
    return {"cls": {"v": cls}, "real": {"p": real_p}, "voice": {"v": voice}}


def test_measure_rest_conflicts_are_local_and_voice_one_only():
    syms = [
        _symbol(0, "mRest_measure", 0, 0),       # high-p same-bar measure rest
        _symbol(1, "mRest_measure", 0, 0),       # low-p same-bar measure rest
        _symbol(2, "rest_half", 0, 0),           # ordinary rest remains
        _symbol(3, "mRest_measure", 0, 1),       # different bar remains
        _symbol(4, "note_quarter", 0, 0),         # supported new voice-one note
    ]
    tok = {
        0: _token("mRest_measure", .8),
        1: _token("mRest_measure", .4),
        2: _token("rest_half", .9),
        3: _token("mRest_measure", .9),
        4: _token("note_quarter", .7, voice=1),
    }
    rd = SimpleNamespace(layout=Layout(syms, [], [], 10, 100, 40), tok=tok)

    decisions = suppress_measure_rest_conflicts(rd, [4])

    assert [d["sym_id"] for d in decisions] == [0]
    assert tok[0]["real"]["p"] == 0
    assert tok[0]["real"]["proposal_original_p"] == pytest.approx(.8)
    assert tok[1]["real"]["p"] == pytest.approx(.4)
    assert tok[2]["real"]["p"] == pytest.approx(.9)
    assert tok[3]["real"]["p"] == pytest.approx(.9)

    tok[0]["real"]["p"] = .8
    tok[0]["real"].pop("proposal_original_p")
    tok[4]["voice"]["v"] = 2
    assert suppress_measure_rest_conflicts(rd, [4]) == []
    assert tok[0]["real"]["p"] == pytest.approx(.8)


def test_proposal_sites_covers_all_18_reviewed_rest_only_anchors():
    audit = ROOT / "diagnostics" / "miss-trace" / "confirmed-misses.json"
    manifest_path = ROOT / "manifest.json"
    if not audit.exists() or not manifest_path.exists():
        pytest.skip("saved confirmed-miss audit or manifest is unavailable")
    cases = json.loads(audit.read_text())["cases"]
    cases = [c for c in cases if c.get("stage") == "rest_only_no_recorded_note_proposal"]
    manifest = {s["id"]: s for s in json.loads(manifest_path.read_text())["samples"]}
    if any(not (ROOT / manifest[c["song_id"]]["input"]).exists() for c in cases if c["song_id"] in manifest):
        pytest.skip("one or more source scans for reviewed anchors are unavailable")

    found = set()
    for song_id in sorted({c["song_id"] for c in cases}):
        sample = manifest[song_id]
        rd = _trace_reading(song_id)
        image = Image.open(ROOT / sample["input"]).convert("L")
        found.update((song_id, site["anchor_id"]) for site in proposal_sites(rd, image))
    expected = {(c["song_id"], c["anchor_sym_id"]) for c in cases}
    assert len(expected) == 18
    assert expected <= found
