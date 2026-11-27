"""Probe source-derived square-note locations with the existing CoreML detector verifier.

This is a diagnostic, not a detector rerun or reader/layout change. It runs one
source crop at a time, scoring the normal local objectness peaks together with
forced cells around a reviewed physical head centre. Probabilities are retained
as raw model outputs; the forced location is never relabeled as a detection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PROBE_MAX_CANDIDATES = 2000
sys.path.insert(0, str(REPO / "copisteria" / "src"))


class PinnedInputs:
    """Keep CoreML input arrays alive until each synchronous prediction returns."""

    def __init__(self, model):
        self.model = model
        self.buffers = {}

    def predict(self, inputs):
        pinned = {}
        for name, value in inputs.items():
            key = (name, value.shape, value.dtype.str)
            if key not in self.buffers:
                self.buffers[key] = np.empty_like(value)
            np.copyto(self.buffers[key], value)
            pinned[name] = self.buffers[key]
        return self.model.predict(pinned)


def softmax(z: np.ndarray) -> np.ndarray:
    z = z.astype(np.float64)
    e = np.exp(z - z.max())
    return e / e.sum()


def crop_for_probe(image: Image.Image, box, staff_space: float, target_spacing=16.):
    """Crop +/- 8 staff spaces horizontally and +/- 5 vertically, then scale to target px/space."""
    if staff_space <= 0:
        raise ValueError(f"staff space must be positive, got {staff_space}")
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    x0, y0 = max(0, cx - 8 * staff_space), max(0, cy - 5 * staff_space)
    x1, y1 = min(image.width, cx + 8 * staff_space), min(image.height, cy + 5 * staff_space)
    crop_x0, crop_y0 = math.floor(x0), math.floor(y0)
    crop = image.crop((crop_x0, crop_y0, math.ceil(x1), math.ceil(y1))).convert("L")
    scale = target_spacing / staff_space
    w, h = max(32, round(crop.width * scale)), max(32, round(crop.height * scale))
    crop = crop.resize((w, h), Image.Resampling.LANCZOS)
    return np.asarray(crop, dtype=np.float32) / 255.0, scale, (crop_x0, crop_y0), (cx, cy)


def cells_for_probe(detector, image, box, staff_space, target_spacing=16.):
    """Return crop tensor, padded backbone output, and normal+forced verifier cells."""
    arr, scale, crop_origin, head_center = crop_for_probe(image, box, staff_space, target_spacing)
    stride = detector.model.stride
    h, w = arr.shape
    H, W = math.ceil(h / 32) * 32, math.ceil(w / 32) * 32
    x = torch.ones(1, 1, H, W, dtype=torch.float32)
    x[0, 0, :h, :w] = torch.from_numpy(arr)
    with torch.no_grad():
        out = detector.model.backbone.predict({"image": x.numpy()})
        # CoreMLDetector.SymbolModel expects backbone tensors in its normal torch form.
        out = {k: torch.from_numpy(np.asarray(out[n]).copy()) for k, n in
               (("f", "features"), ("obj", "objectness"), ("reg", "regression"))}

    obj = torch.sigmoid(out["obj"].float())[0, 0]
    pooled = torch.nn.functional.max_pool2d(obj[None, None], 3, 1, 1)[0, 0]
    valid_h, valid_w = math.ceil(h / stride), math.ceil(w / stride)
    # Match the ordinary decoder's conf=.05 proposal threshold. Feeding all
    # low-objectness maxima to the relational verifier changes its context.
    local = (obj == pooled) & (obj > .025)
    local[valid_h:, :] = False
    local[:, valid_w:] = False
    scores = obj[local]
    indices = torch.nonzero(local, as_tuple=False)
    # Three physical x positions by three y positions, each +/-0.2 staff space.
    cx, cy = head_center
    ox, oy = crop_origin
    forced = {}
    for dy in (-0.2, 0.0, 0.2):
        for dx in (-0.2, 0.0, 0.2):
            px = ((cx + dx * staff_space - ox) * scale) / stride
            py = ((cy + dy * staff_space - oy) * scale) / stride
            cell = (int(round(py)), int(round(px)))
            if 0 <= cell[0] < valid_h and 0 <= cell[1] < valid_w:
                forced.setdefault(cell, []).append({"dx_staff_spaces": dx, "dy_staff_spaces": dy})

    # The production manifest allows 4000 tokens; cap this diagnostic verifier
    # batch at 2000 to keep CoreML attention memory bounded, reserving cells for
    # the forced grid before taking natural objectness peaks.
    natural_cap = max(0, min(detector.model.k_infer, PROBE_MAX_CANDIDATES) - len(forced))
    k = min(natural_cap, len(scores))
    if k:
        _, order = torch.topk(scores, k)
        natural = [(int(indices[i, 0]), int(indices[i, 1])) for i in order]
    else:
        natural = []

    origins = {cell: {"natural_peak_rank": rank + 1, "forced_offsets": []}
               for rank, cell in enumerate(natural)}
    for cell, offsets in forced.items():
        origins.setdefault(cell, {"natural_peak_rank": None, "forced_offsets": []})
        origins[cell]["forced_offsets"] = offsets
    cells = list(origins)
    if not cells:
        raise RuntimeError("No verifier cells were produced")
    cy_t = torch.tensor([[c[0] for c in cells]], dtype=torch.long)
    cx_t = torch.tensor([[c[1] for c in cells]], dtype=torch.long)
    pad = torch.zeros((1, len(cells)), dtype=torch.bool)
    return out, cy_t, cx_t, pad, cells, origins, obj, (h, w, H, W), (crop_origin, head_center, scale)


def probe(detector, image_path: Path, box, staff_space: float, label: str, target_spacing=16.):
    from copisteria.detector.small.data import ATTR_OFFSETS, ATTR_SIZES
    from copisteria.detector.small.export import ATTRS, ATTR_VOCAB
    from copisteria.vocab import family

    image = Image.open(image_path).convert("L")
    out, cy, cx, pad, cells, origins, obj, dims, geom = cells_for_probe(detector, image, box, staff_space, target_spacing)
    with torch.no_grad():
        class_logits, refinement, attr_logits, regression = detector.model._run(out, cy, cx, pad)
    class_p = torch.softmax(class_logits[0].float(), dim=-1).cpu().numpy()
    refinement = refinement[0].float().cpu().numpy()
    attr_logits = attr_logits[0].float().cpu().numpy()
    regression = regression[0].float().cpu().numpy()
    class_names = detector.classes + ["background"]
    note_idx = [i for i, name in enumerate(detector.classes) if family(name) == "note"]
    nonnote_idx = [i for i, name in enumerate(detector.classes) if family(name) != "note"]
    image_h, image_w, padded_h, padded_w = dims
    (origin_x, origin_y), (head_x, head_y), scale = geom
    results = []
    stride = detector.model.stride
    for j, (y, x) in enumerate(cells):
        cp = class_p[j]
        note_best = max(note_idx, key=lambda i: cp[i])
        other_best = max(nonnote_idx, key=lambda i: cp[i])
        attrs = {}
        for name in ATTRS:
            off, n = ATTR_OFFSETS[name], ATTR_SIZES[name]
            ap = softmax(attr_logits[j, off:off + n])
            attrs[name] = {ATTR_VOCAB[name][i]: float(ap[i]) for i in range(n)}
        source_x = origin_x + (x * detector.model.stride) / scale
        source_y = origin_y + (y * detector.model.stride) / scale
        # Match PeakRelational.decode_out: detector regression plus verifier
        # residual, then convert this crop's pixels back to original page pixels.
        rr = regression[j]
        rf = refinement[j]
        logw, logh = rr[0] + rf[2], rr[1] + rf[3]
        dx, dy = rr[2] + rf[0], rr[3] + rf[1]
        refined_cx, refined_cy = float((x + dx) * stride), float((y + dy) * stride)
        bw, bh = math.exp(min(6.0, float(logw))) * stride, math.exp(min(6.0, float(logh))) * stride
        refined_xyxy = [float(v) for v in (
            origin_x + (refined_cx - bw / 2) / scale,
            origin_y + (refined_cy - bh / 2) / scale,
            origin_x + (refined_cx + bw / 2) / scale,
            origin_y + (refined_cy + bh / 2) / scale,
        )]
        results.append({
            "cell": [y, x], "origin": origins[(y, x)],
            "source_center": [source_x, source_y],
            "refined_source_xyxy": refined_xyxy,
            "head_center_distance_staff_spaces": math.hypot(source_x - head_x, source_y - head_y) / staff_space,
            "objectness_probability": float(obj[y, x]),
            "class_probabilities": {name: float(cp[i]) for i, name in enumerate(class_names)},
            "note_family_mass": float(cp[note_idx].sum()),
            "best_note": class_names[note_best], "best_note_probability": float(cp[note_best]),
            "best_other": class_names[other_best], "best_other_probability": float(cp[other_best]),
            "background_probability": float(cp[-1]),
            "attributes": attrs,
            "refinement": [float(v) for v in refinement[j]],
            "box_regression": [float(v) for v in regression[j]],
        })
    return {"label": label, "image": str(image_path), "head_box": list(map(float, box)),
            "staff_space_px": float(staff_space), "target_spacing_px": target_spacing, "crop_shape": [image_h, image_w],
            "padded_shape": [padded_h, padded_w], "model_max_candidates": detector.model.k_infer,
            "probe_natural_peak_cap": max(0, min(detector.model.k_infer, PROBE_MAX_CANDIDATES)
                - sum(bool(v['forced_offsets']) for v in origins.values())),
            "natural_peak_count": len([v for v in origins.values() if v["natural_peak_rank"]]),
            "forced_unique_cell_count": len([v for v in origins.values() if v["forced_offsets"]]),
            "verifier_cell_count": len(cells),
            "records": results}


def load_case(case_id: str):
    cases = json.loads((ROOT / "diagnostics/miss-trace/confirmed-misses.json").read_text())["cases"]
    case = next((c for c in cases if c["case_id"] == case_id), None)
    if case is None:
        raise ValueError(f"No confirmed-miss case {case_id}")
    manifest = json.loads((ROOT / "manifest.json").read_text())["samples"]
    sample = next(s for s in manifest if s["id"] == case["song_id"])
    image_path = ROOT / sample["input"]
    trace_path = ROOT / "reader-gallery/transcriptions" / f"{sample['id']}.trace.json"
    trace = json.loads(trace_path.read_text())
    sp = float(trace["staves"][case["staff"]]["sp"])
    return case, image_path, sp


def clamanda_controls():
    sample = next(s for s in json.loads((ROOT / "manifest.json").read_text())["samples"]
                  if s["title"] == "Clamanda")
    # Visually confirmed shallow rests from the existing source regressions.
    # The detector's rest class alone is not ground truth.
    boxes = [(117, (620.5, 592.0, 662.4, 608.6)),
             (19, (619.8, 907.3, 662.4, 924.2)),
             (70, (620.3, 1133.6, 662.4, 1149.2)),
             (139, (619.6, 1449.0, 662.5, 1465.1))]
    return sample, [(f"Clamanda confirmed half rest ID{i}", box, 31.) for i, box in boxes]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(path: Path) -> str:
    h = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        h.update(item.relative_to(path).as_posix().encode())
        h.update(bytes.fromhex(sha256_file(item)))
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="M013", help="confirmed missed-square-note case (default: M013)")
    parser.add_argument("--all-reviewed", "--all-18", dest="all_reviewed", action="store_true",
                        help="probe all 18 reviewed rest-only square-note cases (M013-M030)")
    parser.add_argument("--clamanda-controls", action="store_true",
                        help="also probe four recorded Clamanda rest boxes as controls")
    parser.add_argument("--target-spacing", type=float, default=16.)
    parser.add_argument("--out", type=Path, help="JSON output path (default: stdout)")
    args = parser.parse_args()
    torch.set_num_threads(4)
    from copisteria.coreml_runtime import CoreMLDetector
    detector = CoreMLDetector(REPO / "copisteria/out/coreml", units="CPU_ONLY")
    detector.model.backbone = PinnedInputs(detector.model.backbone)
    detector.model.verifier = PinnedInputs(detector.model.verifier)

    all_cases = json.loads((ROOT / "diagnostics/miss-trace/confirmed-misses.json").read_text())["cases"]
    if args.all_reviewed:
        selected = [c for c in all_cases if c["stage"] == "rest_only_no_recorded_note_proposal"]
        if len(selected) != 18:
            raise RuntimeError(f"Expected 18 rest-only cases; found {len(selected)}")
    else:
        selected = [next(c for c in all_cases if c["case_id"] == args.case)]
    output = []
    for case in selected:
        case, image_path, sp = load_case(case["case_id"])
        print(f"Probing {case['case_id']} ({len(output) + 1}/{len(selected)})", file=sys.stderr, flush=True)
        output.append(probe(detector, image_path, case["box"], sp,
                            f"{case['case_id']} confirmed printed note", args.target_spacing))
    if args.clamanda_controls:
        sample, controls = clamanda_controls()
        clamanda_path = ROOT / sample["input"]
        print("Probing four Clamanda recorded-rest controls", file=sys.stderr, flush=True)
        output.extend(probe(detector, clamanda_path, box, sp, label, args.target_spacing) for label, box, sp in controls)
    model_dir = REPO / "copisteria/out/coreml"
    provenance = {
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "model_manifest_sha256": sha256_file(model_dir / "manifest.json"),
        "backbone_model_sha256": sha256_tree(model_dir / "DetectorBackbone.mlpackage"),
        "verifier_model_sha256": sha256_tree(model_dir / "DetectorVerifier.mlpackage"),
        "input_sha256": {p["image"]: sha256_file(Path(p["image"])) for p in output},
    }
    encoded = json.dumps({"source_only": True, "compute_units": "CPU_ONLY", "provenance": provenance,
                          "probes": output}, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
