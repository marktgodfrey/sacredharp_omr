"""Conservative source-ink grouping for Sacred Harp four-part systems.

This is an opt-in layout repair. It uses only detected opening clefs and the
existing staff/bar geometry; it never creates, moves, or resizes symbols.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GroupingResult:
    changed: bool
    status: str
    cadence: list[str | None]
    systems: list[list[int]]


def _opening_clef(layout, staff_index: int) -> str | None:
    """Return a confident G2/F4 clef nearest the left side of this staff."""
    st = layout.staves[staff_index]
    candidates = []
    bar_left = min((layout.syms[i].box[0] for i in st.bars), default=st.x0)
    left_boundary = st.line_x0 if st.line_x0 is not None else bar_left
    for sym in layout.syms:
        cls = getattr(sym, "cls", "")
        if cls not in {"clef_G2", "clef_F4"}:
            continue
        if getattr(sym, "p", 0.0) < 0.8:
            continue
        x1, y0, x2, y1 = sym.box
        # Require clear staff overlap and a clef in the opening region. Clefs
        # at later system changes/right margins are not opening evidence.
        vertical = min(y1, st.y1) - max(y0, st.y0)
        if vertical <= 0:
            continue
        # The staff line start is the best source boundary when available;
        # otherwise the first existing measure box supplies a conservative
        # proxy. Opening clefs can sit several spaces to its left.
        center_x = (x1 + x2) / 2
        if not left_boundary - 10 * st.sp <= center_x <= left_boundary + 6 * st.sp:
            continue
        candidates.append((abs(center_x - left_boundary), x1, -vertical, cls))
    if not candidates:
        return None
    candidates.sort()
    # Two plausible opening clefs make this staff ambiguous.
    if len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 0.75 * st.sp:
        return None
    return candidates[0][3]


def _columns(layout, group: list[int]) -> list[list[int]]:
    """Map extant bars to a reference staff by maximum horizontal overlap."""
    ref = max(group, key=lambda k: sum(not layout.syms[i].synthetic for i in layout.staves[k].bars))
    ref_boxes = [layout.syms[i].box for i in layout.staves[ref].bars]
    rows = []
    for k in group:
        row = []
        for i in layout.staves[k].bars:
            b = layout.syms[i].box
            overlaps = [max(0.0, min(b[2], r[2]) - max(b[0], r[0])) for r in ref_boxes]
            row.append(max(range(len(ref_boxes)), key=overlaps.__getitem__))
        rows.append(row)
    return rows


def group_source_systems(layout) -> GroupingResult:
    """Apply 3-treble-plus-terminal-bass grouping when every quartet is clear.

    Three-part (G2,G2,F4) layouts are recognized and left alone. Any missing
    or unexpected clef cadence causes an abstention and leaves layout intact.
    """
    from copisteria.front import System

    n = len(layout.staves)
    cadence = [_opening_clef(layout, i) for i in range(n)]
    existing = [list(s.staves) for s in layout.systems]
    if n == 0:
        return GroupingResult(False, "empty_layout", cadence, existing)
    # A normal three-part score is explicitly accepted unchanged.
    if n % 3 == 0 and all(cadence[i:i + 3] == ["clef_G2", "clef_G2", "clef_F4"]
                           for i in range(0, n, 3)):
        return GroupingResult(False, "three_part_cadence", cadence, existing)
    # Only infer four-part groupings from complete, repeated source cadences.
    if n % 4 or any(cadence[i:i + 4] != ["clef_G2", "clef_G2", "clef_G2", "clef_F4"]
                    for i in range(0, n, 4)):
        return GroupingResult(False, "ambiguous_opening_cadence", cadence, existing)

    groups = [list(range(i, i + 4)) for i in range(0, n, 4)]
    if existing == groups:
        return GroupingResult(False, "already_grouped", cadence, existing)
    rebuilt = []
    for system_index, group in enumerate(groups):
        rebuilt.append(System(staves=group, columns=_columns(layout, group)))
        for pos, staff_index in enumerate(group):
            layout.staves[staff_index].system = system_index
            layout.staves[staff_index].pos = pos
    layout.systems[:] = rebuilt
    return GroupingResult(True, "grouped_four_part_cadence", cadence, groups)
