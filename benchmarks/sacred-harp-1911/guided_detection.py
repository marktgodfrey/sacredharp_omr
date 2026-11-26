"""Opt-in, image-guided recovery tile planning and conservative proposal merge.

This benchmark helper uses only a Reading, scan geometry and image-only head
verifications. It never infers pitch or writes a symbol into the Reading.
"""
from __future__ import annotations

import math


def _family(cls):
    return str(cls).split("_", 1)[0]


def _box(d):
    b = d.get("xyxy")
    if b is None:
        return None
    try:
        b = list(map(float, b))
    except (TypeError, ValueError):
        return None
    return b if len(b) == 4 and b[2] > b[0] and b[3] > b[1] else None


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0., x1 - x0) * max(0., y1 - y0)
    aa = max(0., a[2] - a[0]) * max(0., a[3] - a[1])
    ab = max(0., b[2] - b[0]) * max(0., b[3] - b[1])
    return inter / (aa + ab - inter) if aa + ab > inter else 0.


def _verified(rd, verifications):
    """Return eligible verified heads, keyed by symbol id."""
    out = {}
    syms = {int(s.i): s for s in rd.layout.syms}
    for sid, v in verifications.items():
        try:
            sid = int(sid)
            sym = syms[sid]
            box = list(map(float, sym.box))
            st = rd.layout.staves[int(sym.staff)]
            tok = rd.tok[sid]
            cls = str(tok["cls"]["v"])
            real = tok["real"]
            p = float(real.get("conflict_original_p", real.get("p", 0.)))
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            continue
        if not v.get("stem_found") or not (.52 * st.sp <= box[2]-box[0] <= 1.8 * st.sp
                                             and .48 * st.sp <= box[3]-box[1] <= 1.8 * st.sp):
            continue
        if _family(cls) == "rest" or (_family(cls) == "note" and p < .5):
            out[sid] = {"sym": sym, "box": box, "staff": int(sym.staff), "bar": int(sym.bar),
                        "sp": float(st.sp), "class": cls, "real_p": p}
    return out


def plan_recovery_tiles(rd, image_size, verifications):
    """Plan native-resolution crops around stem-verified head candidates.

    Crops for nearby heads merge within one staff/bar if the crop at target
    spacing fits a 1024-pixel inference width. ``image_size`` is (width,height).
    """
    try:
        width, height = map(int, image_size)
    except (TypeError, ValueError):
        return []
    if width <= 0 or height <= 0:
        return []
    groups = {}
    for sid, h in _verified(rd, verifications).items():
        groups.setdefault((h["staff"], h["bar"]), []).append((sid, h))
    tiles = []
    for (staff_i, bar_i), heads in sorted(groups.items()):
        st = rd.layout.staves[staff_i]
        sp = float(st.sp)
        if sp <= 0:
            continue
        scale = min(32. / sp, 1.)
        max_source_w = max(1, int(math.floor(1024 / scale)))
        top = max(0, math.floor(float(st.y0) - 3 * sp))
        bottom = min(height, math.ceil(float(st.y1) + 3 * sp))
        if bottom <= top:
            continue
        # A candidate contributes +/-8 spaces. Merge only while the union fits.
        chunks, chunk = [], []
        for sid, h in sorted(heads, key=lambda item: item[1]["box"][0]):
            x0, _, x1, _ = h["box"]
            left, right = max(0, math.floor(x0 - 8*sp)), min(width, math.ceil(x1 + 8*sp))
            if right <= left:
                continue
            union_left = min([left] + [r[1] for r in chunk]) if chunk else left
            union_right = max([right] + [r[2] for r in chunk]) if chunk else right
            if chunk and union_right - union_left > max_source_w:
                chunks.append(chunk)
                chunk = []
            chunk.append((sid, left, right))
        if chunk:
            chunks.append(chunk)
        for chunk in chunks:
            left = max(0, min(r[1] for r in chunk))
            right = min(width, max(r[2] for r in chunk))
            if right <= left:
                continue
            tiles.append({"crop": [int(left), int(top), int(right), int(bottom)], "scale": scale,
                          "staff_index": staff_i, "bar_index": bar_i,
                          "head_ids": [int(r[0]) for r in chunk]})
    return tiles


def merge_recovery_detections(base_dets, tile_runs, rd, verifications):
    """Add only tile note proposals tightly aligned with verified heads.

    Returns ``(merged_detections, diagnostics)``. Tile observations are retained
    in diagnostics even when same-family NMS suppresses them, so duration-class
    alternatives remain auditable. Rest and structural detections are ignored.
    """
    heads = _verified(rd, verifications)
    merged = [dict(d) for d in base_dets]
    diagnostics = {"tile_candidates": 0, "accepted_proposals": [], "duration_alternatives": [],
                   "rejected_unverified_or_geometry": 0, "same_family_suppressed": 0,
                   "ignored_non_note": 0}
    candidates = []
    for run in tile_runs:
        crop = run.get("crop", [0, 0, 0, 0])
        try:
            ox, oy = float(crop[0]), float(crop[1])
        except (TypeError, ValueError, IndexError):
            continue
        for item in run.get("detections", []):
            fam = _family(item.get("cls", ""))
            if fam != "note":
                diagnostics["ignored_non_note"] += 1
                continue
            b = _box(item)
            if b is None:
                diagnostics["rejected_unverified_or_geometry"] += 1
                continue
            d = dict(item)
            # Detector.run_array returns coordinates in the crop's native pixel
            # frame even when its inference image was scaled.
            d["xyxy"] = [b[0]+ox, b[1]+oy, b[2]+ox, b[3]+oy]
            if d.get("bbox") is not None:
                try:
                    bx, by, bw, bh = map(float, d["bbox"])
                    d["bbox"] = [bx+ox, by+oy, bw, bh]
                except (TypeError, ValueError):
                    d.pop("bbox", None)
            b = d["xyxy"]
            cx, cy = (b[0]+b[2])/2, (b[1]+b[3])/2
            matching = []
            for sid, h in heads.items():
                hb, sp = h["box"], h["sp"]
                hx, hy = (hb[0]+hb[2])/2, (hb[1]+hb[3])/2
                if abs(cx-hx) <= .75*sp and abs(cy-hy) <= .75*sp:
                    matching.append((sid, h))
            if not matching:
                diagnostics["rejected_unverified_or_geometry"] += 1
                continue
            sid, h = min(matching, key=lambda pair: abs(cx-(pair[1]["box"][0]+pair[1]["box"][2])/2)
                         + abs(cy-(pair[1]["box"][1]+pair[1]["box"][3])/2))
            w, hh = b[2]-b[0], b[3]-b[1]
            record = {"sym_id": int(sid), "cls": d.get("cls"), "conf": float(d.get("conf", 0)),
                      "xyxy": b, "head_box": h["box"]}
            diagnostics["tile_candidates"] += 1
            if not (.4*h["sp"] <= w <= 2*h["sp"] and .35*h["sp"] <= hh <= 2*h["sp"]):
                diagnostics["rejected_unverified_or_geometry"] += 1
                continue
            diagnostics["duration_alternatives"].append(record)
            d["recovery_sym_id"] = int(sid)
            d["recovery_head_box"] = h["box"]
            candidates.append(d)
    for d in sorted(candidates, key=lambda item: float(item.get("conf", 0)), reverse=True):
        b = _box(d)
        matches = [i for i, old in enumerate(merged) if _family(old.get("cls", "")) == "note"
                   and _box(old) is not None and _iou(_box(old), b) >= .5]
        outcome = {"sym_id": d["recovery_sym_id"], "cls": d.get("cls"),
                   "conf": float(d.get("conf", 0)), "xyxy": b,
                   "replaced_base": False, "added": False}
        if matches:
            diagnostics["same_family_suppressed"] += 1
            winner = max(matches, key=lambda i: float(merged[i].get("conf", 0)))
            if float(d.get("conf", 0)) > float(merged[winner].get("conf", 0)):
                merged[winner] = d
                outcome["replaced_base"] = True
        else:
            merged.append(d)
            outcome["added"] = True
        diagnostics["accepted_proposals"].append(outcome)
    return merged, diagnostics
