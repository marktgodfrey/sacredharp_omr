"""Temporary detector-input normalization for image-verified noteheads.

The source image is copied before edits. This module accepts only geometric
stem evidence and scan pixels; it does not use symbol labels or music theory.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw


def normalize_verified_heads(crop_image, crop_origin, heads):
    """Replace verified head interiors with generic oval heads on a copy.

    ``crop_origin`` is the source-image ``(x, y)`` coordinate of the crop's
    upper-left corner. Each head supplies source-coordinate ``box``,
    ``staff_space``, and a ``verify_head`` result in ``evidence``. Returns a
    new PIL image and an audit dictionary; the input image is never modified.
    """
    source = crop_image.copy()
    mode = source.mode
    if mode not in ("L", "RGB"):
        source = source.convert("RGB")
        mode = "RGB"
    output = source.copy()
    arr = np.asarray(source.convert("L"))
    ox, oy = map(float, crop_origin)
    audit = {"considered": len(heads), "normalized": 0, "abstained": 0, "items": []}

    for index, item in enumerate(heads):
        record = {"index": index, "status": "abstained", "reason": ""}
        audit["abstained"] += 1
        evidence = item.get("evidence") or {}
        if evidence.get("stem_found") is not True:
            record["reason"] = "unverified_stem"
            audit["items"].append(record)
            continue
        try:
            x0, y0, x1, y1 = map(float, item["box"])
            sp = float(item["staff_space"])
        except (KeyError, TypeError, ValueError):
            record["reason"] = "invalid_geometry"
            audit["items"].append(record)
            continue
        w, h = x1 - x0, y1 - y0
        if sp <= 0 or not (.55 * sp <= w <= 1.65 * sp and .5 * sp <= h <= 1.65 * sp):
            record["reason"] = "invalid_head_size"
            audit["items"].append(record)
            continue
        # Require the entire working box and a small context ring inside crop.
        x0i, y0i = int(np.floor(x0 - ox)), int(np.floor(y0 - oy))
        x1i, y1i = int(np.ceil(x1 - ox)), int(np.ceil(y1 - oy))
        if x0i < 1 or y0i < 1 or x1i >= source.width - 1 or y1i >= source.height - 1:
            record["reason"] = "head_outside_crop"
            audit["items"].append(record)
            continue

        pad = max(2, int(round(.6 * sp)))
        xa, ya = max(0, x0i - pad), max(0, y0i - pad)
        xb, yb = min(source.width, x1i + pad), min(source.height, y1i + pad)
        patch_gray = arr[ya:yb, xa:xb]
        # Estimate local paper and ink from context surrounding this head.
        context = np.ones(patch_gray.shape, dtype=bool)
        context[y0i - ya:y1i - ya, x0i - xa:x1i - xa] = False
        context_values = patch_gray[context]
        if context_values.size < 4:
            record["reason"] = "insufficient_context"
            audit["items"].append(record)
            continue
        paper = float(np.percentile(context_values, 90))
        ink_threshold = float(np.clip(paper - 40, 130, 205))
        original_box = arr[y0i:y1i, x0i:x1i]
        ext = max(1, int(round(1.5 * sp)))
        staff_rows = np.zeros(y1i - y0i, dtype=bool)
        for row in range(y0i, y1i):
            lx = arr[row, max(0, x0i - ext):max(0, x0i - 1)]
            rx = arr[row, min(source.width, x1i + 1):min(source.width, x1i + ext + 1)]
            # A single unrelated mark on each side is not enough to call a
            # row a staff line. Require sustained support on both sides while
            # allowing moderate breaks in a scanned rule.
            left_support = max(3, int(np.ceil(.35 * lx.size)))
            right_support = max(3, int(np.ceil(.35 * rx.size)))
            staff_rows[row - y0i] = bool(
                lx.size >= 3 and rx.size >= 3
                and np.count_nonzero(lx < ink_threshold) >= left_support
                and np.count_nonzero(rx < ink_threshold) >= right_support
            )
        cy0, cy1 = int(.32 * original_box.shape[0]), int(.68 * original_box.shape[0])
        cx0, cx1 = int(.32 * original_box.shape[1]), int(.68 * original_box.shape[1])
        center = original_box[cy0:cy1, cx0:cx1]
        center = center[~staff_rows[cy0:cy1], :]
        center_fraction = float(np.mean(center < ink_threshold)) if center.size else 0.0
        if center_fraction <= .18:
            style = "hollow"
        elif center_fraction >= .82:
            style = "solid"
        else:
            record["reason"] = "uncertain_fill"
            audit["items"].append(record)
            continue

        # Keep the attached stem pixels and any horizontal staff row that
        # demonstrably continues beyond both sides of the candidate.
        protected = np.zeros((y1i - y0i, x1i - x0i), dtype=bool)
        stem_x = evidence.get("stem_x")
        if stem_x is not None:
            local_stem = int(round(float(stem_x) - ox))
            stem_half = max(1, int(round(.12 * sp)))
            sx0, sx1 = max(x0i, local_stem - stem_half), min(x1i, local_stem + stem_half + 1)
            if sx1 > sx0:
                stem_pixels = arr[y0i:y1i, sx0:sx1] < ink_threshold
                protected[:, sx0 - x0i:sx1 - x0i] |= stem_pixels
        for row_offset, is_staff in enumerate(staff_rows):
            if is_staff:
                protected[row_offset, :] |= arr[y0i + row_offset, x0i:x1i] < ink_threshold

        # Work in grayscale, then convert back to the source's L/RGB mode.
        output_arr = np.asarray(output).copy()
        box = output_arr[y0i:y1i, x0i:x1i]
        box[:] = int(round(paper))
        original_pixels = np.asarray(source)[y0i:y1i, x0i:x1i]
        box[protected] = original_pixels[protected]

        mask = Image.new("L", (x1i - x0i, y1i - y0i), 0)
        draw = ImageDraw.Draw(mask)
        ellipse_box = (0, 0, mask.width - 1, mask.height - 1)
        if style == "solid":
            draw.ellipse(ellipse_box, fill=255)
        else:
            draw.ellipse(ellipse_box, outline=255, width=max(1, int(round(.10 * sp))))
        ellipse = np.asarray(mask) > 0
        ink_value = float(np.percentile(context_values[context_values < ink_threshold], 50)) if np.any(context_values < ink_threshold) else 0.0
        box[ellipse & ~protected] = int(round(ink_value))
        output = Image.fromarray(output_arr.astype(np.uint8), mode=mode)
        audit["normalized"] += 1
        audit["abstained"] -= 1
        record.update(status="normalized", reason="verified_" + style, style=style,
                      center_ink_fraction=round(center_fraction, 3))
        audit["items"].append(record)

    return output, audit
