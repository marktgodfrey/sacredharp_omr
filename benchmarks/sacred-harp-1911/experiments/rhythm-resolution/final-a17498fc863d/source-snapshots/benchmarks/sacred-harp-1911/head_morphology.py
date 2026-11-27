"""Source-pixel morphology measurements for a candidate square notehead."""
from __future__ import annotations

import numpy as np


def _gray_array(image):
    if hasattr(image, "convert"):
        return np.asarray(image.convert("L"))
    pixels = np.asarray(image)
    if pixels.ndim == 3:
        pixels = np.asarray(pixels[..., :3], dtype=float) @ np.array([.299, .587, .114])
    return pixels


def _enclosed_white_components(white, inside=None):
    """Return sizes of 4-connected white components not touching the crop edge."""
    h, w = white.shape
    outside = np.zeros((h, w), dtype=bool)
    stack = []
    if h and w:
        stack.extend((0, x) for x in range(w) if white[0, x])
        stack.extend((h - 1, x) for x in range(w) if white[h - 1, x])
        stack.extend((y, 0) for y in range(h) if white[y, 0])
        stack.extend((y, w - 1) for y in range(h) if white[y, w - 1])
    while stack:
        y, x = stack.pop()
        if outside[y, x] or not white[y, x]:
            continue
        outside[y, x] = True
        if y:
            stack.append((y - 1, x))
        if y + 1 < h:
            stack.append((y + 1, x))
        if x:
            stack.append((y, x - 1))
        if x + 1 < w:
            stack.append((y, x + 1))

    holes = []
    seen = outside.copy()
    ys, xs = np.nonzero(white & ~seen)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if seen[y, x]:
            continue
        seen[y, x] = True
        component = [(y, x)]
        size = within = 0
        while component:
            cy, cx = component.pop()
            size += 1
            within += int(inside is None or inside[cy, cx])
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and white[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    component.append((ny, nx))
        # An adjacent closed counter or a rectangle formed by staff/bar lines
        # outside the candidate is not an interior hole of this head.
        if within >= .9*size:
            holes.append(size)
    return holes


def head_morphology(image, box, threshold):
    """Measure hollow-square evidence using only source pixels and a box.

    ``box`` is ``(x0, y0, x1, y1)`` in source-image coordinates. Edge
    coverage is the fraction of orthogonal rows or columns that contain any
    ink within that edge's outer quarter-band. The central measurement is the
    ink fraction in the middle half of the box in both dimensions.
    """
    result = {
        "central_ink_fraction": 0.0,
        "edge_coverage": {side: 0.0 for side in ("top", "bottom", "left", "right")},
        "hollow_square": False,
        "enclosed_white_area_fraction": 0.0,
        "largest_hole_pixels": 0,
        "hollow_head": False,
    }
    try:
        x0, y0, x1, y1 = map(float, box)
        cut = float(threshold)
        gray = _gray_array(image)
    except (TypeError, ValueError):
        return result
    if gray.ndim != 2 or not gray.size or not np.isfinite(cut) or x1 <= x0 or y1 <= y0:
        return result

    ih, iw = gray.shape
    xa, ya = max(0, int(np.floor(x0))), max(0, int(np.floor(y0)))
    xb, yb = min(iw, int(np.ceil(x1))), min(ih, int(np.ceil(y1)))
    if xb <= xa or yb <= ya:
        return result
    ink = gray[ya:yb, xa:xb] < cut
    h, w = ink.shape
    if h == 0 or w == 0:
        return result

    cy0, cy1 = h // 4, max(h // 4 + 1, int(np.ceil(.75 * h)))
    cx0, cx1 = w // 4, max(w // 4 + 1, int(np.ceil(.75 * w)))
    center = ink[cy0:cy1, cx0:cx1]
    result["central_ink_fraction"] = float(np.count_nonzero(center) / center.size)

    bh, bw = max(1, int(np.ceil(.25 * h))), max(1, int(np.ceil(.25 * w)))
    result["edge_coverage"] = {
        "top": float(np.any(ink[:bh, :], axis=0).mean()),
        "bottom": float(np.any(ink[h-bh:, :], axis=0).mean()),
        "left": float(np.any(ink[:, :bw], axis=1).mean()),
        "right": float(np.any(ink[:, w-bw:], axis=1).mean()),
    }
    ratio = w / h
    result["hollow_square"] = bool(
        result["central_ink_fraction"] <= .25
        and all(value >= .7 for value in result["edge_coverage"].values())
        and .7 <= ratio <= 1.4
    )

    # Expand the local search just enough to preserve outline gaps caused by
    # an attached stem while still requiring a white component enclosed by ink.
    pad = max(1, int(np.ceil(.15 * w)))
    ex0, ey0 = max(0, xa - pad), max(0, ya - pad)
    ex1, ey1 = min(iw, xb + pad), min(ih, yb + pad)
    local_white = gray[ey0:ey1, ex0:ex1] >= cut
    inside = np.zeros(local_white.shape, dtype=bool)
    inside[ya-ey0:yb-ey0, xa-ex0:xb-ex0] = True
    holes = _enclosed_white_components(local_white, inside)
    largest = max(holes, default=0)
    total = sum(holes)
    box_area = max(1, w * h)
    result["largest_hole_pixels"] = int(largest)
    result["enclosed_white_area_fraction"] = float(total / box_area)
    result["hollow_head"] = bool(largest >= .05 * box_area)
    return result
