"""Desktop validation: Core ML neural stages with the upstream Python score reader.

This is a parity harness, not an iOS runtime. Python/Torch still implement ROI
sampling, page geometry, tokens, discrete rhythm decoding and MusicXML writing.
The Swift package independently implements detector ROI sampling and decoding.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from threading import Lock

import numpy as np
import torch
from PIL import Image

from .coreml import HEADS, INPUT_KEYS
from .detect import Detector, imgsz_for, measure_space, staff_space
from .detector.small import models as M
from .detector.small.arch2 import PeakRelational, _sincos_pos
from .detector.small.data import ATTR_OFFSETS, ATTR_SIZES
from .detector.small.export import ATTRS
from .model import EvidenceNet, PRIOR_HEADS
from .vocab import CLS_FAM, N_CLS, N_FAM


def default_compute_units():
    """Permit the Mac GPU by default; callers can explicitly restrict to CPU."""
    return "CPU_AND_GPU" if sys.platform == "darwin" else "CPU_ONLY"


class RetainedModel:
    """Keep CoreML provider buffers alive across consecutive predictions.

    coremltools 9.0 on macOS 26.4 can crash while materializing an output
    array on repeated reader calls if the preceding call's buffers have been
    released. Retain one successful input/output pair per model, replacing it
    only after the next prediction completes. Serialize that handoff so callers
    sharing a model cannot release buffers during another prediction.
    """

    def __init__(self, model):
        self.model = model
        self._buffers = None
        self._lock = Lock()

    def predict(self, inputs):
        with self._lock:
            outputs = self.model.predict(inputs)
            self._buffers = (inputs, outputs)
            return outputs


def load(path, units=None):
    import coremltools as ct
    units = default_compute_units() if units is None else units
    return RetainedModel(ct.models.MLModel(str(path), compute_units=getattr(ct.ComputeUnit, units)))


class SymbolModel:
    """Upstream decoder interface with every learned operation in Core ML."""
    decode_out = PeakRelational.decode_out

    def __init__(self, directory, manifest, units):
        self.backbone = load(directory / "DetectorBackbone.mlpackage", units)
        self.verifier = load(directory / "DetectorVerifier.mlpackage", units)
        self.n_cls = len(manifest["classes"])
        self.k_infer = manifest["max_candidates"]
        self.stride, self.roi, self.d = manifest["stride"], manifest["roi"], manifest["position_dim"]

    def __call__(self, image):
        actual = self.backbone.predict({"image": image.numpy()})
        return {k: torch.from_numpy(actual[n].copy()) for k, n in
                (("f", "features"), ("obj", "objectness"), ("reg", "regression"))}

    def _run(self, out, cy, cx, pad):
        from torchvision.ops import roi_align
        from .detector.small.models import gather_at
        f, reg = out["f"], out["reg"]
        batch, _, _, width = f.shape
        count = cy.shape[1]
        cell = cy * width + cx
        r = gather_at(reg, cell)
        w, h = r[..., 0].clamp(max=6).exp() * 4, r[..., 1].clamp(max=6).exp() * 4
        px, py = (cx.float() + r[..., 2]) * 4, (cy.float() + r[..., 3]) * 4
        bi = torch.arange(batch)[:, None].expand(batch, count)
        boxes = torch.stack([bi.float().reshape(-1), (px - w / 2).reshape(-1), (py - h / 2).reshape(-1),
                             (px + w / 2).reshape(-1), (py + h / 2).reshape(-1)], 1)
        roi = roi_align(f, boxes, (self.roi, self.roi), spatial_scale=.25, sampling_ratio=2, aligned=True)
        regions = torch.cat([roi.reshape(batch, count, -1), gather_at(f, cell)], -1)
        positions = _sincos_pos(cy.reshape(-1), cx.reshape(-1), self.d).reshape(batch, count, -1)
        pad = pad.clone()
        pad[:, 0] = False
        actual = self.verifier.predict({"regions": regions.numpy(), "positions": positions.numpy(),
                                        "padding": pad.numpy().astype(np.int32)})
        return (*(torch.from_numpy(actual[k].copy()) for k in ("classes", "refinement", "attributes")), r)


class CoreMLDetector(Detector):
    def __init__(self, directory: Path, units=None):
        manifest = json.loads((directory / "manifest.json").read_text())["detector"]
        self.classes = manifest["classes"]
        self.torch, self.M, self.device = torch, M, "cpu"
        self.model = SymbolModel(directory, manifest, units)
        self.attr_cls = [c.partition("_")[0] in M.ATTR_CLASS_PREFIXES for c in self.classes]
        self.slices = {a: (ATTR_OFFSETS[a], ATTR_SIZES[a]) for a in ATTRS}
        self.vocab = manifest["attributes"]


class CoreMLEvidence(torch.nn.Module):
    priors = EvidenceNet.priors

    def __init__(self, directory: Path, units=None):
        super().__init__()
        self.native = load(directory / "Evidence.mlpackage", units)
        self.feat_dim, self.onset_trained = 0, True
        mask = torch.zeros(N_FAM, N_CLS, dtype=torch.bool)
        for c, f in enumerate(CLS_FAM):
            mask[f, c] = True
        self.register_buffer("fam_mask", mask)

    def forward(self, b, need_attn=False):
        if need_attn:
            raise ValueError("Core ML export omits visualization attention maps; use attention=False")
        args = {k: b[k].numpy().astype(np.int32 if k in
                {"fam", "cls_ids", "staffpos", "nstaves", "sys", "col", "pos_v", "cls_mask", "attr_mask", "pad"}
                else np.float32) for k in INPUT_KEYS}
        actual = self.native.predict(args)
        out = {k: torch.from_numpy(actual[k].copy()) for k in HEADS}
        out["_evidence"] = {k: torch.from_numpy(actual["evidence_" + k].copy()) for k in PRIOR_HEADS}
        return out


def run(page, models, out, units=None, clean_layout=False, four_staff=False):
    from . import write, view
    from .revise import read_revised
    from .vision.page.staves import find_staves
    from .shapenotes import transform
    units = default_compute_units() if units is None else units
    started = time.perf_counter()
    torch.set_num_threads(4)
    im = Image.open(page).convert("L")
    layout_image = im
    if clean_layout:
        from .front import clean_page
        layout_image = Image.fromarray(clean_page(np.asarray(im)))
    detector = CoreMLDetector(models, units)
    ink = find_staves(im).spacing
    arr, scale = detector.prepare(im, 2048)
    dets = detector.run_array(arr, scale)
    size = imgsz_for(staff_space(ink, measure_space(dets)), max(im.size))
    if size != 2048:
        arr, scale = detector.prepare(im, size)
        dets = detector.run_array(arr, scale)
    model = CoreMLEvidence(models, units)
    rd = read_revised(dets, im.width, im.height, model, attention=False, image=layout_image)
    xml = write.write(rd, image=layout_image)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / (page.stem + ".musicxml")
    dest.write_text(xml)
    shape_dest = out / (page.stem + ".shapes.musicxml")
    tree, assumed_key = transform(dest)
    tree.write(shape_dest, encoding="utf-8", xml_declaration=True)
    arrangement_report = None
    if four_staff:
        from .registers import arrange_for_singing
        import xml.etree.ElementTree as ET
        arranged, arrangement_report = arrange_for_singing(dest)
        shaped, _ = transform(ET.tostring(arranged.getroot(), encoding="utf-8"))
        arranged_dest = out / (page.stem + ".4staff.shapes.musicxml")
        shaped.write(arranged_dest, encoding="utf-8", xml_declaration=True)
        (out / (page.stem + ".arrangement.json")).write_text(json.dumps(arrangement_report, indent=2) + "\n")
    (out / (page.stem + ".html")).write_text(view.page_html(rd, page, xml, page.stem))
    report = {"backend": "CoreML neural stages + Python layout/decoding", "compute_units": units,
              "input": str(page), "detector_size": size, "detections": len(dets), "clean_layout": clean_layout,
              "staves": len(rd.layout.staves), "systems": len(rd.layout.systems), "symbols": len(rd.tok),
              "elapsed_seconds": time.perf_counter() - started, "shape_key_assumed_C_major": assumed_key,
              "four_staff": four_staff, "arrangement": arrangement_report}
    (out / (page.stem + ".report.json")).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("page", type=Path)
    p.add_argument("--models", type=Path, default=Path("out/coreml"))
    p.add_argument("--out", type=Path, default=Path("out/coreml-reader"))
    p.add_argument("--compute-units", choices=("CPU_ONLY", "CPU_AND_GPU", "ALL"),
                   default=default_compute_units(), help="CoreML compute policy (default: %(default)s)")
    p.add_argument("--clean-layout", action="store_true", help="normalize scan shading before staff/system layout")
    p.add_argument("--four-staff", action="store_true", help="split SATB, swap soprano/tenor, optimize octaves and write four shape-note staves")
    a = p.parse_args()
    run(a.page, a.models, a.out, a.compute_units, a.clean_layout, a.four_staff)


if __name__ == "__main__":
    main()
