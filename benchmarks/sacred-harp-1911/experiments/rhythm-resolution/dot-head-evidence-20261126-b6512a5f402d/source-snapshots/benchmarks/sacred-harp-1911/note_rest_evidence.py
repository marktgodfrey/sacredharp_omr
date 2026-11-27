"""Opt-in image evidence for a short stem attached to a notehead-like glyph.

This helper reports geometry only. It does not classify a symbol or rewrite a
note/rest decision; callers should combine it with independent note evidence.
"""
from __future__ import annotations

import math

import numpy as np

from glyph_verifier import _ink_array, verify_head


def short_stem_evidence(image, box, staff_space, bar_box=None):
    """Find a short, edge-anchored vertical extension from retained head ink.

    A candidate must have a head-like box and head ink supported in three
    quadrants. A narrow edge column must connect to the head boundary and
    continue at least 0.8 staff spaces, with at least 70% ink occupancy and
    only small scan gaps. Long measure boundaries supplied as ``bar_box`` are
    excluded. The return value contains no pitch or symbol classification.
    """
    result = {"found": False, "score": 0.0, "direction": None,
              "stem_x": None, "reason": "", "head_ink_fraction": 0.0}
    try:
        x0, y0, x1, y1 = map(float, box)
        sp = float(staff_space)
    except (TypeError, ValueError):
        result["reason"] = "invalid_geometry"
        return result
    if sp <= 0 or x1 <= x0 or y1 <= y0:
        result["reason"] = "invalid_geometry"
        return result

    w, h = x1 - x0, y1 - y0
    if not (.52 * sp <= w <= 1.8 * sp and .48 * sp <= h <= 1.8 * sp
            and .5 <= w / h <= 1.9):
        result["reason"] = "box_not_head_like"
        return result

    head_check = verify_head(image, box, sp, bar_box=bar_box)
    result["head_ink_fraction"] = head_check["head_ink_fraction"]
    if head_check["head_ink_fraction"] < .03 or head_check["supported_quadrants"] < 3:
        result["reason"] = "no_head_ink"
        return result

    # Limit conversion, percentile estimation, and the ink mask to the box plus
    # the maximum stem search distance. For PIL inputs this also avoids making
    # a full-page RGB-to-gray array for every candidate.
    if hasattr(image, "size") and not isinstance(image, np.ndarray):
        iw, ih = image.size
    else:
        source = np.asarray(image)
        if source.ndim < 2:
            result["reason"] = "invalid_image"
            return result
        ih, iw = source.shape[:2]
    xoff = max(0, int(math.floor(x0 - 2 * sp)))
    yoff = max(0, int(math.floor(y0 - 2 * sp)))
    xend = min(iw, int(math.ceil(x1 + 2 * sp)))
    yend = min(ih, int(math.ceil(y1 + 2 * sp)))
    if xend <= xoff or yend <= yoff:
        result["reason"] = "invalid_image"
        return result
    if hasattr(image, "crop"):
        crop = image.crop((xoff, yoff, xend, yend))
    else:
        crop = source[yoff:yend, xoff:xend]
    gray = _ink_array(crop)
    if gray.ndim != 2 or not gray.size:
        result["reason"] = "invalid_image"
        return result
    ih, iw = gray.shape
    x0, x1, y0, y1 = x0 - xoff, x1 - xoff, y0 - yoff, y1 - yoff
    paper = float(np.percentile(gray, 90))
    threshold = float(np.clip(paper - 40.0, 130.0, 205.0))
    ink = gray < threshold
    bx0, by0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
    bx1, by1 = min(iw, int(math.ceil(x1))), min(ih, int(math.ceil(y1)))
    if bx1 <= bx0 or by1 <= by0:
        result["reason"] = "box_outside_image"
        return result

    min_extension = max(2, int(math.ceil(.8 * sp)))
    max_extension = max(min_extension, int(math.ceil(1.5 * sp)))
    gap_limit = max(0, int(math.floor(.15 * sp)))
    band = max(1, int(math.ceil(.16 * sp)))
    candidates = []

    for side, edge in (("left", bx0), ("right", bx1 - 1)):
        # A supplied tall measure box marks a structural boundary at this edge.
        if bar_box is not None:
            try:
                qx0, qy0, qx1, qy1 = map(float, bar_box)
                near_boundary = min(abs(edge + xoff - qx0), abs(edge + xoff - qx1)) <= .4 * sp
                long_boundary = qy1 - qy0 >= 3 * sp
                overlaps_search = qy0 < by1 + yoff + max_extension and qy1 > by0 + yoff - max_extension
                if near_boundary and long_boundary and overlaps_search:
                    continue
            except (TypeError, ValueError):
                pass

        xa, xb = max(0, edge - band), min(iw, edge + band + 1)
        for direction in ("up", "down"):
            if direction == "up":
                anchor = ink[max(0, by0 - 1):min(ih, by0 + 2), xa:xb]
                outside = ink[max(0, by0 - max_extension):by0, xa:xb][::-1]
            else:
                anchor = ink[max(0, by1 - 2):min(ih, by1 + 1), xa:xb]
                outside = ink[by1:min(ih, by1 + max_extension), xa:xb]
            if not anchor.size or not outside.size:
                continue

            # Evaluate each narrow column independently; unrelated vertical
            # marks nearby cannot qualify unless they touch the head boundary.
            for j in range(outside.shape[1]):
                if not np.any(anchor[:, j]):
                    continue
                rows = outside[:, j]
                if len(rows) < min_extension:
                    continue
                prefix = rows[:min_extension]
                occupancy = float(np.count_nonzero(prefix)) / min_extension
                gaps = min_extension - int(np.count_nonzero(prefix))
                if occupancy < .70 or gaps > gap_limit:
                    continue
                run = best = gap = 0
                for present in prefix:
                    if present:
                        run += 1 + gap
                        gap = 0
                        best = max(best, run)
                    elif run and gap < gap_limit:
                        gap += 1
                    else:
                        run = gap = 0
                if best < min_extension:
                    continue
                candidates.append((occupancy, side, direction, xa + j))

    if not candidates:
        result["reason"] = "no_short_stem_evidence"
        return result
    score, _, direction, stem_x = max(candidates)
    result.update(found=True, score=round(score, 3), direction=direction,
                  stem_x=int(stem_x + xoff), reason="edge_anchored_short_stem")
    return result
