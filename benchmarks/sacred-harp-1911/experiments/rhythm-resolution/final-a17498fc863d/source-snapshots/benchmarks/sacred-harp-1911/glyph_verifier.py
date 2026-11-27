"""Conservative image-only check for a notehead's stem.

This helper deliberately inspects only the supplied image and geometry.  It does
not use a symbol class, pitch, key, reference transcription, or note shape.
"""
from __future__ import annotations

import numpy as np


def _ink_array(image):
    """Return grayscale image pixels, accepting PIL images or array-like data."""
    if hasattr(image, "convert"):
        return np.asarray(image.convert("L"))
    a = np.asarray(image)
    if a.ndim == 3:
        # RGB/RGBA input; use a simple luminance approximation.
        a = np.asarray(a[..., :3], dtype=float) @ np.array([.299, .587, .114])
    return a


def _has_head_sized_component(mask, staff_space):
    """Require one connected ink component with extent in both dimensions."""
    h, w = mask.shape
    min_span = max(3, int(np.ceil(.35 * staff_space)))
    seen = np.zeros(mask.shape, dtype=bool)
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if seen[y, x]:
            continue
        seen[y, x] = True
        stack = [(y, x)]
        min_x = max_x = x
        min_y = max_y = y
        while stack:
            cy, cx = stack.pop()
            min_x, max_x = min(min_x, cx), max(max_x, cx)
            min_y, max_y = min(min_y, cy), max(max_y, cy)
            for ny in range(max(0, cy - 1), min(h, cy + 2)):
                for nx in range(max(0, cx - 1), min(w, cx + 2)):
                    if mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if max_x - min_x + 1 >= min_span and max_y - min_y + 1 >= min_span:
            return True
    return False


def verify_head(image, box, staff_space, bar_box=None):
    """Check whether a tight head-like box has a vertical stem extending away.

    ``box`` and ``bar_box`` are ``(x0, y0, x1, y1)`` image coordinates.  A
    stem must run at an outer head edge for at least 1.5 staff spaces beyond the
    box.  Returned ``stem_score`` is a conservative 0..1 geometric/ink score;
    negative outcomes include a reason suitable for benchmark diagnostics.
    """
    result = {"stem_found": False, "stem_score": 0.0, "direction": None,
              "stem_x": None, "reason": "", "head_ink_fraction": 0.0,
              "supported_quadrants": 0, "ink_threshold": None}
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
    # Tall rest boxes and broad structural boxes are not head candidates.
    if not (.52 * sp <= w <= 1.8 * sp and .48 * sp <= h <= 1.8 * sp
            and .5 <= w / h <= 1.9):
        result["reason"] = "box_not_head_like"
        return result

    gray = _ink_array(image)
    if gray.ndim != 2 or not gray.size:
        result["reason"] = "invalid_image"
        return result
    ih, iw = gray.shape
    # Restrict work to the candidate and its possible stem extensions. This
    # keeps repeated checks cheap on full-page scans.
    xoff = max(0, int(np.floor(x0 - 4 * sp)))
    yoff = max(0, int(np.floor(y0 - 4 * sp)))
    xend = min(iw, int(np.ceil(x1 + 4 * sp)))
    yend = min(ih, int(np.ceil(y1 + 4 * sp)))
    gray = gray[yoff:yend, xoff:xend]
    ih, iw = gray.shape
    x0, x1, y0, y1 = x0 - xoff, x1 - xoff, y0 - yoff, y1 - yoff
    # Estimate paper tone from the local ROI. The margin is fixed by image
    # contrast behavior, not fitted to benchmark labels; clipping avoids
    # turning low-contrast paper texture or very dark crops into ink wholesale.
    paper = float(np.percentile(gray, 90))
    threshold = float(np.clip(paper - 40.0, 130.0, 205.0))
    result["ink_threshold"] = round(threshold, 1)
    ink = gray < threshold
    bx0, by0 = max(0, int(np.floor(x0))), max(0, int(np.floor(y0)))
    bx1, by1 = min(iw, int(np.ceil(x1))), min(ih, int(np.ceil(y1)))
    if bx1 <= bx0 or by1 <= by0:
        result["reason"] = "box_outside_image"
        return result

    head = ink[by0:by1, bx0:bx1].copy()
    # Identify staff rows from ink extending outside the candidate on both
    # sides. Occupancy inside a filled head is not evidence of a staff line.
    ext = max(1, int(round(2 * sp)))
    left_strip = ink[by0:by1, max(0, bx0 - ext):max(0, bx0 - 1)]
    right_strip = ink[by0:by1, min(iw, bx1 + 1):min(iw, bx1 + ext + 1)]
    if left_strip.shape[1] and right_strip.shape[1]:
        # A vertical stem can contribute two or more pixels to each strip at
        # many rows. Require a meaningful fraction of each strip to be ink so
        # that only thin, horizontally continuous staff lines are removed.
        left_coverage = np.count_nonzero(left_strip, axis=1) / left_strip.shape[1]
        right_coverage = np.count_nonzero(right_strip, axis=1) / right_strip.shape[1]
        candidate_rows = (left_coverage >= .35) & (right_coverage >= .35)
        # Horizontal runs wider than a staff stroke usually come from nearby
        # filled heads (or other glyphs), not a thin staff line.
        max_staff_thickness = max(1, int(np.ceil(.3 * sp)))
        staff_rows = np.zeros_like(candidate_rows)
        start = None
        for row, present in enumerate(np.r_[candidate_rows, False]):
            if present and start is None:
                start = row
            elif not present and start is not None:
                if row - start <= max_staff_thickness:
                    staff_rows[start:row] = True
                start = None
        head[staff_rows, :] = False
    head_count = int(np.count_nonzero(head))
    head_fraction = head_count / max(1, (bx1 - bx0) * (by1 - by0))
    mid_y, mid_x = head.shape[0] // 2, head.shape[1] // 2
    quadrants = (head[:mid_y, :mid_x], head[:mid_y, mid_x:],
                 head[mid_y:, :mid_x], head[mid_y:, mid_x:])
    supported = sum(np.count_nonzero(q) >= 2 for q in quadrants if q.size)
    result["head_ink_fraction"] = round(head_fraction, 3)
    result["supported_quadrants"] = int(supported)
    # This accepts both filled heads and hollow outlines while rejecting a
    # nearby stem that contributes ink in only one local quadrant.
    if (head_count < max(4, int(.03 * (bx1 - bx0) * (by1 - by0)))
            or supported < 3 or not _has_head_sized_component(head, sp)):
        result["reason"] = "no_head_ink"
        return result

    # Stem is typically just outside a head's left/right edge. Check a narrow
    # strip, but include the edge itself to tolerate touching/overprinted heads.
    band = max(1, int(round(.35 * sp)))
    min_run = max(2, int(np.ceil(1.5 * sp)))
    max_run = max(min_run, int(np.ceil(3.5 * sp)))
    gap_allowance = max(1, int(round(.30 * sp)))
    candidates = []
    for side, edge, lo, hi in (("left", x0, -1, 1), ("right", x1 - 1, -1, 1)):
        cx = int(round(edge))
        xa, xb = max(0, cx - band), min(iw, cx + band + 1)
        if xb <= xa:
            continue
        for direction in ("up", "down"):
            if direction == "up":
                ya, yb = max(0, int(np.floor(y0 - max_run - 1))), by0
            else:
                ya, yb = by1, min(ih, int(np.ceil(y1 + max_run + 1)))
            if yb <= ya:
                continue
            # Ignore a candidate coincident with the supplied barline box.
            if bar_box is not None:
                try:
                    qx0, qy0, qx1, qy1 = map(float, bar_box)
                    near_boundary = min(abs(edge + xoff - qx0), abs(edge + xoff - qx1)) <= .4 * sp
                    long_measure_box = qy1 - qy0 >= 3 * sp
                    if near_boundary and long_measure_box and qy0 - yoff < y1 + max_run and qy1 - yoff > y0 - max_run:
                        continue
                except (TypeError, ValueError):
                    pass
            rows = np.any(ink[ya:yb, xa:xb], axis=1)
            # Longest vertical run, allowing only a small number of broken scan
            # rows. Staff lines cannot satisfy this vertical extent test.
            run = best = 0
            gaps = 0
            for present in rows:
                if present:
                    run += 1 + gaps
                    gaps = 0
                    best = max(best, run)
                elif run and gaps < gap_allowance:
                    gaps += 1
                else:
                    run = gaps = 0
            if best >= min_run:
                # Require ink at the head boundary, so a nearby unrelated line
                # cannot validate an otherwise isolated candidate.
                edge_rows = ink[max(0, by0 - 1):min(ih, by1 + 1), xa:xb]
                if not np.any(edge_rows):
                    continue
                candidates.append((best, side, direction, cx))

    if not candidates:
        result["reason"] = "no_stem_evidence"
        return result
    length, side, direction, cx = max(candidates)
    result.update(stem_found=True,
                stem_score=round(min(1.0, length / max_run), 3),
                  direction=direction, stem_x=int(cx + xoff), reason="vertical_extension")
    return result
