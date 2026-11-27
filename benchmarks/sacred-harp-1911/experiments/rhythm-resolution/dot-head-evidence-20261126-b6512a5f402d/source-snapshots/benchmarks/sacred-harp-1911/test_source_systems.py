import json
from pathlib import Path

from copisteria.front import Layout, Staff, Sym, System

from source_systems import group_source_systems


def _layout(clefs, systems):
    staves = []
    syms = []
    for i, clef in enumerate(clefs):
        y = i * 200.0
        staves.append(Staff(bars=[len(syms)], sp=20, y0=y, y1=y + 80,
                            x0=100, x1=500, system=0, pos=i))
        # Each bar owns a unique ID and a fixed geometry; grouping must retain it.
        syms.append(Sym(i=len(syms), cls="measure", post={}, p=1, n=1,
                        box=[100, y, 480, y + 80], attrs={}, attr_p={}, attr_dist={},
                        staff=i, bar=0, synthetic=False, cand=False))
        syms.append(Sym(i=len(syms), cls=clef, post={}, p=1, n=1,
                        box=[20, y + 10, 60, y + 70], attrs={}, attr_p={}, attr_dist={},
                        staff=i, bar=0, synthetic=False, cand=False))
    sy = [System(staves=list(g), columns=[[0] for _ in g]) for g in systems]
    return Layout(syms=syms, staves=staves, systems=sy, sp=20, width=600, height=200 * len(clefs))


def test_repairs_five_known_four_part_grouping_shapes():
    cases = [
        # Golden Harp: detector split 3+1; Farewell and Salem: four singletons.
        (["clef_G2"] * 3 + ["clef_F4"], [[0, 1, 2], [3]]),
        (["clef_G2"] * 3 + ["clef_F4"], [[0], [1], [2], [3]]),
        # Monroe: 3+5; Clamanda: one group of eight.
        (["clef_G2"] * 3 + ["clef_F4"] + ["clef_G2"] * 3 + ["clef_F4"],
         [[0, 1, 2], [3, 4, 5, 6, 7]]),
        (["clef_G2"] * 3 + ["clef_F4"] + ["clef_G2"] * 3 + ["clef_F4"],
         [list(range(8))]),
        # The remaining requested case has four source staves in four groups.
        (["clef_G2"] * 3 + ["clef_F4"], [[0], [1], [2], [3]]),
    ]
    for clefs, current in cases:
        layout = _layout(clefs, current)
        original = [(s.i, list(s.box)) for s in layout.syms]
        result = group_source_systems(layout)
        assert result.changed and result.status == "grouped_four_part_cadence"
        assert result.systems == [list(range(i, i + 4)) for i in range(0, len(clefs), 4)]
        assert [(s.i, s.box) for s in layout.syms] == original
        assert [s.system for s in layout.staves] == [i // 4 for i in range(len(clefs))]
        assert [s.pos for s in layout.staves] == [i % 4 for i in range(len(clefs))]


def test_preserves_normal_three_part_score():
    layout = _layout(["clef_G2", "clef_G2", "clef_F4"], [[0, 1, 2]])
    before = [list(s.staves) for s in layout.systems]
    result = group_source_systems(layout)
    assert not result.changed and result.status == "three_part_cadence"
    assert [list(s.staves) for s in layout.systems] == before


def test_abstains_on_missing_or_ambiguous_terminal_bass_clef():
    for clefs in (["clef_G2"] * 4, ["clef_G2", "clef_G2", None, "clef_F4"]):
        layout = _layout(clefs, [[0], [1], [2], [3]])
        before = [list(s.staves) for s in layout.systems]
        result = group_source_systems(layout)
        assert not result.changed and result.status == "ambiguous_opening_cadence"
        assert [list(s.staves) for s in layout.systems] == before


def _cached_layout(song_id):
    root = Path(__file__).parent / "experiments/missing-proposals/final-d190393b6a83/predictions"
    data = json.loads((root / f"{song_id}.trace.json").read_text())
    staves = [Staff(**x) for x in data["staves"]]
    syms = [Sym(**x) for x in data["syms"]]
    systems = [System(**x) for x in data["systems"]]
    width = max((s.box[2] for s in syms), default=1)
    height = max((s.box[3] for s in syms), default=1)
    return Layout(syms, staves, systems, sp=staves[0].sp, width=width, height=height)


def _protected_geometry(layout):
    return (
        [(s.i, s.cls, tuple(s.box), s.staff, s.bar) for s in layout.syms],
        [(tuple(s.bars), s.sp, s.y0, s.y1, s.x0, s.x1, s.line_x0) for s in layout.staves],
    )


def test_five_cached_regressions_group_from_source_cadence_only():
    cases = {
        "1911-Origin-JPK-0052": [[0, 1, 2, 3], [4, 5, 6, 7]],
        "1911-s0288-the-golden-harp": [[0, 1, 2, 3]],
        "1911-s0384-monroe": [[0, 1, 2, 3], [4, 5, 6, 7]],
        "1911-s0412-farewell-to-all": [[0, 1, 2, 3]],
        "1911-s0078-salem": [[0, 1, 2, 3]],
    }
    for song_id, expected in cases.items():
        layout = _cached_layout(song_id)
        protected = _protected_geometry(layout)
        result = group_source_systems(layout)
        assert result.changed and result.systems == expected
        assert _protected_geometry(layout) == protected


def test_cached_normal_three_part_score_is_preserved():
    layout = _cached_layout("1911-s0092-edgefield")
    protected = _protected_geometry(layout)
    before = [list(s.staves) for s in layout.systems]
    result = group_source_systems(layout)
    assert not result.changed and result.status == "three_part_cadence"
    assert [list(s.staves) for s in layout.systems] == before
    assert _protected_geometry(layout) == protected
