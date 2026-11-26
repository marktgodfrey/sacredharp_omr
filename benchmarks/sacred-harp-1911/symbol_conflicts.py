"""Post-evidence cleanup for near-identical note/rest readings."""
from __future__ import annotations


def _family(cls):
    return str(cls).split("_", 1)[0]


def _box(sym):
    return getattr(sym, "box", getattr(sym, "bbox", None))


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0., x1 - x0) * max(0., y1 - y0)
    aa = max(0., a[2] - a[0]) * max(0., a[3] - a[1])
    ab = max(0., b[2] - b[0]) * max(0., b[3] - b[1])
    return inter / (aa + ab - inter) if aa + ab > inter else 0.


def resolve_note_rest_conflicts(rd, *, min_probability=.95, min_margin=.2, min_iou=.5):
    """Suppress a lower-confidence overlapping note/rest token; return audit decisions."""
    layout = rd.layout
    rows = []
    for token_id, token in rd.tok.items():
        sym = layout.syms[token_id]
        real = token.get("real")
        reading = token.get("cls")
        if not real or not reading or _family(reading.get("v", "")) not in ("note", "rest"):
            continue
        rows.append((sym, token, float(real["p"]), reading["v"]))
    pairs = []
    for i, a in enumerate(rows):
        sa, ta, pa, ca = a
        if pa < .5:
            continue
        ba = _box(sa)
        if ba is None:
            continue
        for b in rows[i + 1:]:
            sb, tb, pb, cb = b
            if pb < .5 or sa.staff != sb.staff or sa.bar != sb.bar:
                continue
            if {_family(ca), _family(cb)} != {"note", "rest"}:
                continue
            bb = _box(sb)
            if bb is None:
                continue
            iou = _iou(ba, bb)
            wa, ha = ba[2] - ba[0], ba[3] - ba[1]
            wb, hb = bb[2] - bb[0], bb[3] - bb[1]
            if iou < min_iou or abs((ba[0] + ba[2] - bb[0] - bb[2]) / 2) > .5 * min(wa, wb) or \
                    abs((ba[1] + ba[3] - bb[1] - bb[3]) / 2) > .5 * min(ha, hb):
                continue
            if pa == pb:
                continue
            hi, lo = (a, b) if pa > pb else (b, a)
            if hi[2] >= min_probability and hi[2] - lo[2] >= min_margin:
                pairs.append(( -hi[2], hi[0].i, lo[0].i, hi, lo, iou))
    pairs.sort(key=lambda p: p[:3])
    suppressed = set()
    decisions = []
    for _, _, _, high, low, iou in pairs:
        winner, loser = high[0], low[0]
        if winner.i in suppressed or loser.i in suppressed:
            continue
        # Do not let a token that has already lost participate in a later decision.
        real = low[1]["real"]
        old_p = float(real["p"])
        real["conflict_original_p"] = old_p
        real["conflict_reason"] = "overlapping_note_rest"
        real["p"] = 0
        suppressed.add(loser.i)
        decisions.append({"winner_id": winner.i, "loser_id": loser.i,
                          "winner_cls": high[3], "loser_cls": low[3],
                          "winner_p": high[2], "loser_p": old_p, "iou": iou})
    return decisions
