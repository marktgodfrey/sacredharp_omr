"""Staff-centered detector crop planning and detection merging helpers."""
from __future__ import annotations

import math


def plan_staff_tiles(staves, image_size, *, target_spacing=16.0, max_tile_side=2048, max_upscale=1.0):
    """Plan overlapping staff crops. image_size is (width, height); coordinates stay in source pixels."""
    width, height = map(int, image_size)
    if width <= 0 or height <= 0 or max_tile_side <= 0 or target_spacing <= 0 or max_upscale <= 0:
        return []
    result = []
    for si, st in enumerate(staves):
        sp = float(st.sp)
        if sp <= 0:
            continue
        scale = min(float(target_spacing) / sp, float(max_upscale))
        x0, x1 = float(st.x0), float(st.x1)
        left, right = max(0, math.floor(x0 - 2 * sp)), min(width, math.ceil(x1 + 2 * sp))
        top, bottom = max(0, math.floor(float(st.y0) - 3 * sp)), min(height, math.ceil(float(st.y1) + 3 * sp))
        if right <= left or bottom <= top:
            continue
        max_original = max(1, int(math.floor(max_tile_side / scale)))
        # Keep vertical context where possible. If the padded staff itself exceeds the limit,
        # the image bounds remain authoritative and the tile is still useful at reduced scale.
        if bottom - top > max_original:
            top = max(0, min(height - max_original, int(round((float(st.y0) + float(st.y1)) / 2 - max_original / 2))))
            bottom = min(height, top + max_original)
        span = right - left
        if span <= max_original:
            starts = [left]
        else:
            overlap = min(max(1, int(math.ceil(4 * sp))), max_original - 1) if max_original > 1 else 0
            step = max(1, max_original - overlap)
            starts = list(range(left, right - max_original + 1, step))
            last = right - max_original
            if starts[-1] != last:
                starts.append(last)
        for ti, start in enumerate(starts):
            end = min(right, start + max_original)
            result.append({"crop": [int(start), int(top), int(end), int(bottom)], "scale": scale,
                           "staff_index": si, "core": [int(start), int(top), int(end), int(bottom)]})
    return result


def _family(cls):
    return str(cls).split("_", 1)[0]


def _iou(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0., x1 - x0) * max(0., y1 - y0)
    area_a = max(0., a[2] - a[0]) * max(0., a[3] - a[1])
    area_b = max(0., b[2] - b[0]) * max(0., b[3] - b[1])
    return inter / (area_a + area_b - inter) if area_a + area_b > inter else 0.


def merge_tile_detections(base, tile_runs):
    """Merge tile note/rest candidates into base records; return (records, diagnostics)."""
    merged = [dict(d) for d in base]
    candidates = []
    for run in tile_runs:
        x0, y0 = run["crop"][:2]
        for item in run.get("detections", []):
            d = dict(item)
            fam = _family(d.get("cls", ""))
            if fam not in ("note", "rest"):
                continue
            if "xyxy" in d:
                d["xyxy"] = [float(d["xyxy"][0]) + x0, float(d["xyxy"][1]) + y0,
                             float(d["xyxy"][2]) + x0, float(d["xyxy"][3]) + y0]
            if "bbox" in d:
                b = d["bbox"]
                d["bbox"] = [float(b[0]) + x0, float(b[1]) + y0, float(b[2]), float(b[3])]
            candidates.append(d)
    kept = 0
    suppressed = 0
    for d in sorted(candidates, key=lambda d: float(d.get("conf", 0)), reverse=True):
        fam = _family(d.get("cls", ""))
        box = d.get("xyxy")
        if box is None:
            continue
        matches = [i for i, old in enumerate(merged) if _family(old.get("cls", "")) == fam and
                   old.get("xyxy") is not None and _iou(old["xyxy"], box) >= .5]
        if matches:
            suppressed += 1
            # Keep the strongest same-family observation, including its attribute heads.
            winner = max(matches, key=lambda i: float(merged[i].get("conf", 0)))
            if float(d.get("conf", 0)) > float(merged[winner].get("conf", 0)):
                merged[winner] = d
        else:
            merged.append(d)
            kept += 1
    return merged, {"tile_candidates": len(candidates), "tile_added": kept,
                    "same_family_suppressed": suppressed, "structural_ignored": sum(
                        1 for r in tile_runs for d in r.get("detections", [])
                        if _family(d.get("cls", "")) not in ("note", "rest"))}
