"""Image-only measurements for detached augmentation dots near noteheads.

This is a diagnostic helper. It does not alter a reading or decide a note value.
Coordinates are source-image pixels and ``head_box`` is (x0, y0, x1, y1).
"""
from __future__ import annotations

import numpy as np


def _gray_array(image):
    if hasattr(image, "convert"):
        return np.asarray(image.convert("L"))
    pixels = np.asarray(image)
    if pixels.ndim == 3:
        pixels = np.asarray(pixels[..., :3], dtype=float) @ np.array([.299, .587, .114])
    return pixels


def _components(mask):
    """8-connected foreground components as (area, x0, y0, x1, y1)."""
    h, w = mask.shape
    seen = np.zeros((h, w), dtype=bool)
    out = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        seen[y, x] = True
        stack = [(int(y), int(x))]
        area = 0
        xa = xb = int(x); ya = yb = int(y)
        while stack:
            cy, cx = stack.pop(); area += 1
            xa, xb = min(xa, cx), max(xb, cx)
            ya, yb = min(ya, cy), max(yb, cy)
            for ny in range(max(0, cy-1), min(h, cy+2)):
                for nx in range(max(0, cx-1), min(w, cx+2)):
                    if mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        out.append((area, xa, ya, xb+1, yb+1))
    return out


def detached_dot_evidence(image, head_box, staff_space, threshold=175):
    """Find compact ink just right of a head, suppressing inferred staff lines.

    Staff rows are inferred from long horizontal runs outside the head. Their
    pixels are removed from the search mask, except for a narrow local window
    around each plausible dot center so a dot printed on/near a staff line can
    survive. All reported sizes and offsets are normalized by staff space.
    """
    empty = {"present": False, "visible": False, "reason": "invalid_input",
             "staff_rows": [], "components": []}
    try:
        gray = _gray_array(image)
        x0, y0, x1, y1 = map(float, head_box)
        sp, cut = float(staff_space), float(threshold)
    except (TypeError, ValueError):
        return empty
    if gray.ndim != 2 or not gray.size or not np.isfinite(gray).all() or sp <= 0 or x1 <= x0 or y1 <= y0:
        return empty
    h, w = gray.shape
    ink = gray < cut
    xa, xb = max(0, int(np.floor(x0))), min(w, int(np.ceil(x1)))
    ya, yb = max(0, int(np.floor(y0))), min(h, int(np.ceil(y1)))
    if xb <= xa or yb <= ya:
        return empty

    # Search a compact augmentation-dot zone: right of head, near its vertical
    # center. The wider vertical allowance accommodates heads on staff lines.
    sx0 = max(0, int(np.floor(x1 + .08*sp)))
    sx1 = min(w, int(np.ceil(x1 + .82*sp)))
    sy0 = max(0, int(np.floor((y0+y1)/2 - .72*sp)))
    sy1 = min(h, int(np.ceil((y0+y1)/2 + .72*sp)))
    if sx1 <= sx0 or sy1 <= sy0:
        return {**empty, "visible": False, "reason": "outside_image"}

    # Look for staff-line rows across the search corridor and exterior head
    # margins. Long runs in both exterior margins are strong line evidence.
    ex0, ex1 = max(0, int(x0-.35*sp)), min(w, int(x1+1.5*sp))
    rows = []
    for yy in range(sy0, sy1):
        left_end = max(ex0, min(xa, sx0))
        right_start = min(ex1, max(xb, sx1))
        left = ink[yy, ex0:left_end]
        right = ink[yy, right_start:ex1]
        lengths = (int(np.count_nonzero(left)), int(np.count_nonzero(right)))
        # Require evidence on both sides, reducing confusion with stems or text.
        if lengths[0] >= .30*sp and lengths[1] >= .30*sp:
            rows.append(yy)

    search = ink[sy0:sy1, sx0:sx1].copy()
    # A line row can be identified, but do not erase the whole row: retain a
    # centered dot-sized window, which lets a compact mark on the line remain.
    for yy in rows:
        ly = yy-sy0
        # Retain pixels on the line row only when they have local vertical
        # support. This preserves a dot crossed by a staff line while removing
        # the long horizontal stroke itself.
        above = ink[max(0, yy-2):yy, sx0:sx1].any(axis=0) if yy else np.zeros(sx1-sx0, bool)
        below = ink[yy+1:min(h, yy+3), sx0:sx1].any(axis=0) if yy+1 < h else np.zeros(sx1-sx0, bool)
        search[ly, :] &= above | below

    comps = []
    for area, cx0, cy0, cx1, cy1 in _components(search):
        cw, ch = cx1-cx0, cy1-cy0
        width_n, height_n, area_n = cw/sp, ch/sp, area/(sp*sp)
        aspect = cw/max(1, ch)
        cx = (sx0+cx0+sx0+cx1)/2
        cy = (sy0+cy0+sy0+cy1)/2
        dx = (cx-(x0+x1)/2)/sp
        dy = (cy-(y0+y1)/2)/sp
        detached = cx0 > 0 and cy0 > 0 and cx1 < search.shape[1] and cy1 < search.shape[0]
        compact = (detached and .07 <= width_n <= .50 and .07 <= height_n <= .50
                   and .45 <= aspect <= 2.0 and .003 <= area_n <= .20)
        components = {"area_pixels": int(area), "box": [sx0+cx0, sy0+cy0, sx0+cx1, sy0+cy1],
                      "width_staff_spaces": round(width_n, 4),
                      "height_staff_spaces": round(height_n, 4),
                      "area_staff_spaces2": round(area_n, 5),
                      "center_offset_staff_spaces": [round(dx, 4), round(dy, 4)],
                      "compact_candidate": bool(compact)}
        if compact:
            comps.append(components)
    comps.sort(key=lambda c: c["area_pixels"], reverse=True)
    return {"present": bool(comps), "visible": True,
            "reason": "compact_detached_ink" if comps else "no_compact_detached_ink",
            "staff_rows": [int(r) for r in rows], "components": comps}
