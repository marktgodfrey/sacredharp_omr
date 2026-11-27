"""Image-only opening meter evidence from cross-song glyph templates.

Templates are learned from high-confidence, parallel-consistent meter reads in
the supplied source inputs. This module never changes a Reading or its tokens.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
PATCH_W, PATCH_H = 36, 96
MAX_TEMPLATES_PER_METER = 8


def _path(value):
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def _meter(cls):
    prefix = "meterSig_"
    if not cls.startswith(prefix):
        return None
    value = cls[len(prefix):].replace("_", "/")
    return value if value.count("/") == 1 and all(x.isdigit() for x in value.split("/")) else None


def _patch(gray, center_x, center_y, sp, staff_y0, *, normalize=True):
    """Take a staff-relative patch and mask the five horizontal staff lines."""
    w, h = 1.5 * sp, 4.0 * sp
    x0, x1 = int(round(center_x - w / 2)), int(round(center_x + w / 2))
    y0, y1 = int(round(center_y - h / 2)), int(round(center_y + h / 2))
    if x0 < 0 or y0 < 0 or x1 > gray.width or y1 > gray.height or x1 <= x0 or y1 <= y0:
        return None
    patch = np.asarray(gray.crop((x0, y0, x1, y1)), dtype=np.float32).copy()
    # Staff lines are regular at one staff-space intervals. Mask a narrow band
    # to prevent them from swamping the digit strokes in normalized matching.
    for i in range(5):
        yy = staff_y0 + i * sp
        local = int(round(yy - y0))
        if 0 <= local < patch.shape[0]:
            patch[max(0, local - 1):min(patch.shape[0], local + 2), :] = 255
    from PIL import Image as _Image
    patch = np.asarray(_Image.fromarray(np.uint8(np.clip(patch, 0, 255))).resize(
        (PATCH_W, PATCH_H), _Image.Resampling.BILINEAR), dtype=np.float32)
    if normalize:
        lo, hi = np.percentile(patch, [5, 98])
        if hi - lo > 12:
            patch = np.clip((patch - lo) * (255.0 / (hi - lo)), 0, 255)
    # Darkness image makes ink-positive correlation intuitive.
    return (255.0 - patch) / 255.0


def _trace_path(sample):
    for key in ("baseline_trace", "trace", "trace_path"):
        if sample.get(key):
            return _path(sample[key])
    return None


def build_meter_templates(samples):
    """Build a small diverse template bank from source inputs and raw traces.

    Each sample must provide an exact source image path under ``input`` (or
    ``image``) and a trace path under ``baseline_trace``, ``trace`` or
    ``trace_path``. A label is admitted only when at least two first-system
    staves contain the same >=.97 raw numeric meter label at a common x.
    Returns ``(bank, provenance)``.
    """
    candidates = defaultdict(list)
    provenance = {"source_samples": 0, "eligible_parallel_labels": 0,
                  "excluded_labels": 0, "templates_per_meter": {}}
    for sample in samples:
        image_path = _path(sample.get("input") or sample.get("image"))
        trace_path = _trace_path(sample)
        if trace_path is None or not image_path.is_file() or not trace_path.is_file():
            continue
        try:
            trace = json.loads(trace_path.read_text())
            image = Image.open(image_path).convert("L")
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        provenance["source_samples"] += 1
        staves = trace.get("staves", [])
        first_staff_ids = set((trace.get("systems") or [{}])[0].get("staves", []))
        grouped = defaultdict(list)
        for sym in trace.get("syms", []):
            label = _meter(str(sym.get("cls", "")))
            sid = int(sym.get("staff", -1))
            if (label is None or sid not in first_staff_ids or int(sym.get("bar", -1)) != 0
                    or float(sym.get("p", 0)) < .97 or sid >= len(staves)):
                continue
            x = (float(sym["box"][0]) + float(sym["box"][2])) / 2
            sp = float(staves[sid].get("sp", 0))
            if sp <= 0:
                continue
            grouped[label].append((sid, x, sp, sym))
        for label, rows in grouped.items():
            # Form common-x clusters and admit only labels repeated on distinct staves.
            rows.sort(key=lambda r: r[1])
            clusters = []
            for row in rows:
                if clusters and row[1] - clusters[-1][-1][1] <= .7 * np.median([r[2] for r in clusters[-1]]):
                    clusters[-1].append(row)
                else:
                    clusters.append([row])
            cluster = max(clusters, key=lambda c: len({r[0] for r in c}))
            if len({r[0] for r in cluster}) < 2:
                provenance["excluded_labels"] += 1
                continue
            provenance["eligible_parallel_labels"] += 1
            for sid, x, sp, sym in cluster:
                staff = staves[sid]
                cy = (float(staff["y0"]) + float(staff["y1"])) / 2
                patch = _patch(image, x, cy, sp, float(staff["y0"]))
                if patch is not None:
                    candidates[label].append({"template": patch, "sample_id": sample.get("id"),
                        "symbol_id": int(sym.get("i", -1)), "confidence": float(sym.get("p", 0)),
                        "staff_space": sp})
        image.close()

    bank = {}
    for label, rows in sorted(candidates.items()):
        # Keep one parallel staff exemplar per source page so the bank favors
        # print diversity across pages instead of repeated copies of one glyph.
        by_sample = {}
        for row in rows:
            key = str(row["sample_id"])
            if key not in by_sample or row["confidence"] > by_sample[key]["confidence"]:
                by_sample[key] = row
        rows = sorted(by_sample.values(), key=lambda r: (str(r["sample_id"]), r["symbol_id"]))
        # Farthest-point selection retains distinct print styles without letting
        # the frequent 4/4 label dominate the bank.
        selected_indexes = [0]
        while len(selected_indexes) < min(MAX_TEMPLATES_PER_METER, len(rows)):
            remaining = [i for i in range(len(rows)) if i not in selected_indexes]
            nxt = max(remaining, key=lambda i: min(float(np.mean(np.abs(rows[i]["template"] - rows[j]["template"])))
                                                    for j in selected_indexes))
            selected_indexes.append(nxt)
        selected = [rows[i] for i in selected_indexes]
        bank[label] = selected
        provenance["templates_per_meter"][label] = len(selected)
    return bank, provenance


def _first_note_x(rd, staff_id, events):
    candidates = []
    if events is not None:
        # Accept either writer-built rows or a flat list of writer events.
        try:
            for measures in events:
                for measure in measures:
                    for row in measure.get("staves", []):
                        if row and row.get("staff") == staff_id:
                            candidates += [float(e.x) for voice in row.get("voices", {}).values()
                                           for e in voice if getattr(e, "kind", "") in ("note", "rest")]
        except (AttributeError, TypeError):
            for e in events:
                if getattr(e, "kind", "") in ("note", "rest"):
                    si = int(getattr(e, "si", -1))
                    if 0 <= si < len(rd.layout.syms) and rd.layout.syms[si].staff == staff_id:
                        candidates.append(float(e.x))
    if not candidates:
        for s in rd.layout.syms:
            if (s.staff == staff_id and s.bar == 0 and not getattr(s, "synthetic", False)
                    and getattr(s, "p", 0) >= .5 and s.cls.startswith(("note_", "rest_"))):
                candidates.append(float(s.box[0]))
    return min(candidates) if candidates else None


def _score(patch, template):
    a, b = patch.ravel(), template.ravel()
    a = a - a.mean(); b = b - b.mean()
    den = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / den) if den else -1.0


def opening_meter_from_ink(rd, image, bank, events=None):
    """Return consensus evidence only when parallel opening-staff matches agree.

    Does not edit tokens or symbols. ``None`` is returned when the template
    score, class margin, horizontal alignment, or staff consensus is weak.
    """
    if not bank:
        return None
    gray = image.convert("L") if hasattr(image, "convert") else Image.fromarray(np.asarray(image).astype(np.uint8))
    first_ids = (rd.layout.systems[0].staves if rd.layout.systems else [])
    staff_regions = []
    for sid in first_ids:
        staff = rd.layout.staves[sid]
        first_note = _first_note_x(rd, sid, events)
        if first_note is None:
            continue
        bar = rd.layout.syms[staff.bars[0]].box
        # Start after the opening clef/key signature; scan only the short gap
        # before the first musical head, where a printed time glyph belongs.
        left_symbols = [s for s in rd.layout.syms if s.staff == sid and s.bar == 0
                        and s.cls.startswith(("clef_", "keySig_"))]
        # A failed measure detection can start after the printed signature.
        # The clef/key edge, rather than that box edge, bounds the search.
        left = max([float(s.box[2]) for s in left_symbols] or [float(bar[0])]) + .08 * staff.sp
        right = min(first_note - .08 * staff.sp, float(bar[2]))
        if right - left < .65 * staff.sp:
            continue
        staff_regions.append((sid, staff, left + .75 * staff.sp, right - .75 * staff.sp))
    if len(staff_regions) < 2:
        return None
    common_left = max(r[2] for r in staff_regions)
    common_right = min(r[3] for r in staff_regions)
    if common_right <= common_left:
        return None
    step = .08 * float(np.median([r[1].sp for r in staff_regions]))
    consensuses = []
    for x in np.arange(common_left, common_right + step / 2, step):
        grouped = defaultdict(list)
        for sid, staff, _, _ in staff_regions:
            center_y = (staff.y0 + staff.y1) / 2
            best = None
            for dy in (-.22, -.11, 0, .11, .22):
                patch = _patch(gray, float(x), center_y + dy * staff.sp, staff.sp, staff.y0)
                if patch is None:
                    continue
                scores = sorted(((max(_score(patch, t["template"]) for t in templates), label)
                                 for label, templates in bank.items()), reverse=True)
                if len(scores) < 2:
                    continue
                top, second = scores[0], scores[1]
                row = {"staff": int(sid), "x": float(x), "score": top[0],
                       "meter": top[1], "margin": top[0] - second[0]}
                if best is None or (row["score"], row["margin"]) > (best["score"], best["margin"]):
                    best = row
            if best and best["score"] >= .65 and best["margin"] >= .02:
                grouped[best["meter"]].append(best)
        for meter, votes in grouped.items():
            if len(votes) >= 2:
                consensuses.append((len(votes), float(np.mean([v["score"] for v in votes])),
                                    float(np.mean([v["margin"] for v in votes])), meter, votes, float(x)))
    if not consensuses:
        return None
    count, score, margin, meter, agreed, x = max(consensuses, key=lambda c: (c[0], c[1], c[2]))
    return {"meter": meter, "source": "parallel_staff_ink_templates", "staff_votes": agreed,
            "consensus_staff_count": count, "x": x, "mean_score": score,
            "minimum_margin": float(min(v["margin"] for v in agreed))}
