"""Measure attached vertical ink continuing from a notehead edge.

This module reports image geometry only. It does not infer note classes or
duration values.
"""
from __future__ import annotations

import math

import numpy as np

from glyph_verifier import _ink_array


def attached_stem_evidence(image, head_box, staff_space, bar_box=None):
    """Measure connected near-vertical extensions above and below a head.

    ``head_box`` and optional ``bar_box`` are ``(x0, y0, x1, y1)`` image
    coordinates. A stem must touch ink at the head edge and continue through
    a narrow vertical band. Scan gaps up to 0.12 staff spaces are tolerated.
    """
    result = {"visible": False, "max_up_staff_spaces": 0.0,
              "max_down_staff_spaces": 0.0, "short_stub": False,
              "long_stem": False, "direction": None, "reason": ""}
    try:
        x0, y0, x1, y1 = map(float, head_box)
        sp = float(staff_space)
    except (TypeError, ValueError):
        result["reason"] = "invalid_geometry"
        return result
    if sp <= 0 or x1 <= x0 or y1 <= y0:
        result["reason"] = "invalid_geometry"
        return result
    if hasattr(image, "size") and not isinstance(image, np.ndarray):
        iw, ih = image.size
    else:
        source = np.asarray(image)
        if source.ndim < 2:
            result["reason"] = "invalid_image"
            return result
        ih, iw = source.shape[:2]
    # Search only a small margin; target lengths beyond 2.5 spaces are
    # reported as capped because longer continuation adds no stem evidence.
    margin = 2.5 * sp
    xa0, ya0 = max(0, int(math.floor(x0 - .25 * sp))), max(0, int(math.floor(y0 - margin)))
    xa1, ya1 = min(iw, int(math.ceil(x1 + .25 * sp))), min(ih, int(math.ceil(y1 + margin)))
    if xa1 <= xa0 or ya1 <= ya0:
        result["reason"] = "box_outside_image"
        return result
    crop = image.crop((xa0, ya0, xa1, ya1)) if hasattr(image, "crop") else source[ya0:ya1, xa0:xa1]
    gray = _ink_array(crop)
    if gray.ndim != 2 or not gray.size:
        result["reason"] = "invalid_image"
        return result
    threshold = float(np.clip(float(np.percentile(gray, 90)) - 40.0, 130.0, 205.0))
    ink = gray < threshold
    bx0, bx1 = max(0, int(math.floor(x0 - xa0))), min(gray.shape[1], int(math.ceil(x1 - xa0)))
    by0, by1 = max(0, int(math.floor(y0 - ya0))), min(gray.shape[0], int(math.ceil(y1 - ya0)))
    if bx1 <= bx0 or by1 <= by0:
        result["reason"] = "box_outside_image"
        return result

    band = max(1, int(math.ceil(.04 * sp)))
    gap = max(0, int(math.floor(.12 * sp)))
    max_px = max(1, int(math.ceil(2.5 * sp)))
    row_ink = np.count_nonzero(ink[by0:by1, bx0:bx1], axis=1)
    dense_rows = np.flatnonzero(row_ink >= max(2, int(math.ceil(.18 * (bx1 - bx0)))))
    if len(dense_rows):
        head_top, head_bottom = by0 + int(dense_rows[0]), by0 + int(dense_rows[-1])
    else:
        head_top, head_bottom = by0, by1 - 1
    measurements = {}
    for direction in ("up", "down"):
        best = 0
        box_edge = by0 if direction == "up" else by1 - 1
        dense_edge = head_top if direction == "up" else head_bottom
        for raw_side in (bx0, bx0 + .2 * sp, bx1 - 1 - .2 * sp, bx1 - 1):
            side = int(round(raw_side))
            # A structural bar boundary near this head edge is not a stem.
            if bar_box is not None:
                try:
                    qx0, _, qx1, _ = map(float, bar_box)
                    if min(abs(side + xa0 - qx0), abs(side + xa0 - qx1)) <= .3 * sp:
                        continue
                except (TypeError, ValueError):
                    pass
            for x in range(max(0, side-band), min(gray.shape[1], side+band+1)):
                # First follow continuation outside the supplied head box.
                # The anchor may be within 0.1 staff spaces horizontally to
                # accommodate a stem just outside a tight detector rectangle.
                margin = max(1, int(math.ceil(.1 * sp)))
                near_x0, near_x1 = max(0, x-margin), min(gray.shape[1], x+margin+1)
                anchor = ink[max(0, box_edge-1):min(gray.shape[0], box_edge+2), near_x0:near_x1]
                outward = (ink[max(0, box_edge-max_px):box_edge, x][::-1] if direction == "up"
                           else ink[box_edge+1:min(gray.shape[0], box_edge+1+max_px), x])
                run = last_ink = 0
                if np.any(anchor):
                    for present in outward:
                        run += 1
                        if present:
                            last_ink = run
                        elif run - last_ink > gap:
                            break
                best = max(best, last_ink)

                # Some tight detector boxes include a short attached stub.
                # Count its visible extension from the dense head boundary to
                # the box edge only when the line bridges that entire segment.
                if direction == "up" and dense_edge > box_edge:
                    inside = ink[box_edge:dense_edge+1, x][::-1]
                elif direction == "down" and dense_edge < box_edge:
                    inside = ink[dense_edge:box_edge+1, x]
                else:
                    inside = np.zeros(0, dtype=bool)
                if len(inside) and np.any(inside[-1:]):
                    present = np.flatnonzero(inside)
                    if len(present) and present[-1] >= len(inside)-gap-1:
                        best = max(best, len(inside) / sp)
        measurements[direction] = min(best / sp, 2.5)
    up, down = measurements.get("up", 0.0), measurements.get("down", 0.0)
    enough_context = (y0 - 1.2 * sp >= 0 and y1 + 1.2 * sp <= ih + ya0)
    result.update(visible=enough_context,
                  max_up_staff_spaces=round(up, 4),
                  max_down_staff_spaces=round(down, 4),
                  short_stub=max(up, down) >= .15,
                  long_stem=max(up, down) >= 1.2,
                  direction=("up" if up > down else "down" if down > up else None),
                  reason="measured" if enough_context else "insufficient_context")
    return result
