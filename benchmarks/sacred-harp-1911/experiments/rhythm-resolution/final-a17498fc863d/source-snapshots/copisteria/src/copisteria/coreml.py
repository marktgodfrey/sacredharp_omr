"""Core ML export adapters for the released copista detector and evidence model.

Modified for the native iOS experiment. No upstream inference behavior is changed.
The detector is split at ROI sampling, which is implemented by the native host.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .detect import Detector
from .features import N_GEO
from .model import PRIOR_HEADS
from .read import load_model
from .train import TOKEN_KEYS
from .vocab import N_VOICE

INPUT_KEYS = TOKEN_KEYS + ("cls_mask", "attr_mask", "pad")
HEADS = ("real", "cls", "dots", "pos", "voice", "grace", "alter", "chord", "tie", "tup", "key", "time",
         "clef", "onset_beat", "onset_frac")
EVIDENCE_OUTPUTS = HEADS + tuple("evidence_" + k for k in PRIOR_HEADS)
INTEGER_KEYS = {"fam", "cls_ids", "staffpos", "nstaves", "sys", "col", "pos_v", "cls_mask", "attr_mask", "pad"}


class Backbone(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, image):
        # Equivalent to FPN.forward for the required multiples-of-32 input.
        # Explicit factors avoid a Core ML dynamic-nearest-resize conversion failure.
        p2, p3, p4, p5 = self.model.enc(image)
        fpn = self.model.fpn
        x = fpn.lat[3](p5)
        for k, f in ((2, p4), (1, p3), (0, p2)):
            x = torch.nn.functional.interpolate(x, scale_factor=2., mode="nearest") + fpn.lat[k](f)
            x = fpn.smooth[k](x)
        return x, self.model.obj(x), self.model.reg(x)


class Verifier(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.proj, self.dec = model.proj, model.dec
        self.cls, self.refine, self.attr = model.cls, model.refine, model.attr

    def forward(self, regions, positions, padding):
        # Explicit attention avoids scalar-cast ops emitted by newer PyTorch MHA.
        h = self.proj(regions) + positions
        for layer in self.dec.enc.layers:
            z = layer.norm1(h)
            batch, length, dim = z.shape
            heads = layer.self_attn.num_heads
            q, k, v = torch.nn.functional.linear(z, layer.self_attn.in_proj_weight,
                                                layer.self_attn.in_proj_bias).chunk(3, -1)
            q = q.reshape(batch, length, heads, -1).transpose(1, 2)
            k = k.reshape(batch, length, heads, -1).transpose(1, 2)
            v = v.reshape(batch, length, heads, -1).transpose(1, 2)
            weights = ((q @ k.transpose(-1, -2)) * (layer.self_attn.head_dim ** -.5))
            weights = weights.masked_fill(padding.bool()[:, None, None, :], float("-inf")).softmax(-1)
            z = (weights @ v).transpose(1, 2).reshape(batch, length, dim)
            h = h + layer.self_attn.out_proj(z)
            h = h + layer.linear2(torch.nn.functional.gelu(layer.linear1(layer.norm2(h))))
        return self.cls(h), self.refine(h), self.attr(h)


class Evidence(nn.Module):
    def __init__(self, model):
        super().__init__()
        if model.refine or model.feat_dim:
            raise ValueError("Only the released base evidence model is supported")
        self.model = model

    def forward(self, *args):
        # The released embed/priors, with logit expressed using supported ops.
        from .vocab import N_CLS, N_POS, POS_MAX
        from .model import EPS_LOGP
        b = dict(zip(INPUT_KEYS, args))
        m = self.model
        fam, ids, cp = b["fam"].long(), b["cls_ids"].long(), b["cls_p"]
        pv, pp, p = b["pos_v"].long(), b["pos_p"], b["p"]
        clamped = p.clamp(1e-3, 1 - 1e-3)
        logit = clamped.log() - (1 - clamped).log()
        e = (m.cls_emb(ids) * cp[..., None]).sum(2)
        mask = b["cls_mask"].float()[..., None]
        e = e * (1 - mask) + m.mask_emb * mask
        has = (pv > -99).long()
        pi = has * (pv.clamp(-POS_MAX, POS_MAX) + POS_MAX) + (1 - has) * N_POS
        num = torch.cat([b["geo"], p[..., None], logit[..., None] / 5, pp[..., None], b["dots_p"],
                         b["voice_p"], b["grace_p"], b["stem_p"], mask, b["attr_mask"].float()[..., None]], -1)
        x = (e + m.fam_emb(fam) + m.staffpos_emb(b["staffpos"].long())
             + m.nstaves_emb(b["nstaves"].long()) + m.pos_emb(pi) + m.num(num))
        # Ordered where preserves scatter's last-write behavior for duplicate ids,
        # without Core ML scatter's symbolic-shape restrictions.
        classes = torch.arange(N_CLS, device=p.device)[None, None, :]
        logp = torch.zeros_like(p[..., None] + classes.float()) + EPS_LOGP
        for slot in range(3):
            selected = (ids[..., slot, None] == classes).float()
            logp = selected * cp[..., slot, None].clamp_min(1e-4).log() + (1 - selected) * logp
        fm = m.fam_mask[fam]
        uni = -fm.float() * fm.float().sum(-1, keepdim=True).clamp_min(1.).log() + (~fm).float() * EPS_LOGP
        pri = {"cls": mask * uni + (1 - mask) * logp, "real": logit[..., None]}
        for k in ("dots", "voice", "grace"):
            z = (b[k + "_p"] + 1e-3).log()
            pri[k] = (b["dots_p"].sum(-1, keepdim=True) != 0).float() * z
        idx = pv.clamp(-POS_MAX, POS_MAX) + POS_MAX
        positions = torch.arange(N_POS, device=p.device)[None, None, :]
        soft = (idx[..., None] == positions).float() * pp[..., None]
        side = ((1 - pp) / 2)[..., None]
        soft = soft + ((idx - 1).clamp(0, N_POS - 1)[..., None] == positions).float() * side
        soft = soft + ((idx + 1).clamp(0, N_POS - 1)[..., None] == positions).float() * side
        pri["pos"] = (pv > -99).float()[..., None] * (soft + 1e-3).log()
        basis = m.basis(b, torch.float32)
        for block in m.blocks:
            batch, length, dim = x.shape
            q, k, v = block.qkv(block.n1(x)).chunk(3, -1)
            q = q.reshape(batch, length, block.h, -1).transpose(1, 2)
            k = k.reshape(batch, length, block.h, -1).transpose(1, 2)
            v = v.reshape(batch, length, block.h, -1).transpose(1, 2)
            bias = torch.einsum("hk,bkij->bhij", block.rel, basis)
            weights = (q @ k.transpose(-1, -2)) * ((m.cfg["d"] // block.h) ** -.5) + bias
            weights = (weights + b["pad"].float()[:, None, None, :] * -1e9).softmax(-1)
            y = (weights @ v).transpose(1, 2).reshape(batch, length, dim)
            x = x + block.o(y)
            x = x + block.ff(block.n2(x))
        o = m._heads(m.norm(x), pri)
        return tuple(o[k] for k in HEADS) + tuple(o["_evidence"][k] for k in PRIOR_HEADS)


def example_tokens(length=32):
    """Deterministic, valid nontrivial tokens used for conversion smoke checks."""
    g = torch.Generator().manual_seed(1729)
    b = {k: torch.zeros(1, length, dtype=torch.int32 if k in INTEGER_KEYS else torch.float32)
         for k in INPUT_KEYS}
    b["cls_ids"] = torch.arange(length * 3, dtype=torch.int32).reshape(1, length, 3) % 270
    b["cls_p"] = torch.tensor([.6, .3, .1]).expand(1, length, 3).clone()
    b["p"] = torch.rand(1, length, generator=g) * .9 + .05
    b["geo"] = torch.randn(1, length, N_GEO, generator=g) * .3
    b["nstaves"].fill_(4)
    b["staffpos"] = torch.arange(length, dtype=torch.int32)[None] % 4
    b["col"] = torch.arange(length, dtype=torch.int32)[None] // 8
    b["sys"] = torch.arange(length, dtype=torch.int32)[None] // 24
    b["pos_v"] = torch.arange(length, dtype=torch.int32)[None] % 13 - 6
    b["pos_p"].fill_(.8)
    for k, n in (("dots_p", 4), ("voice_p", N_VOICE), ("grace_p", 3), ("stem_p", 3)):
        b[k] = torch.softmax(torch.randn(1, length, n, generator=g), -1)
    return b


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export(out, detector, evidence, *, height=1024, width=768, precision="float32", verify=True):
    import coremltools as ct
    from .detector.small.export import ATTR_VOCAB
    from . import vocab

    if height % 32 or width % 32 or min(height, width) < 32:
        raise ValueError("Image dimensions must be positive multiples of 32")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    torch.backends.mha.set_fastpath_enabled(False)
    torch.manual_seed(1729)
    det = Detector(detector, device="cpu")
    if not all(hasattr(det.model, k) for k in ("proj", "dec", "cls", "refine", "attr")):
        raise ValueError("This exporter requires an obj-recall detector")
    ev = load_model(evidence)
    region_dim, d = det.model.proj.in_features, det.model.d
    tokens = example_tokens()
    candidate_count = ct.RangeDim(1, det.model.k_infer, default=32)
    token_count = ct.RangeDim(1, 1024, default=32)
    jobs = [
        ("DetectorBackbone", Backbone(det.model), (torch.rand(1, 1, height, width),), ["image"],
         ["features", "objectness", "regression"],
         [(1, 1, ct.RangeDim(32, 4096, default=height), ct.RangeDim(32, 4096, default=width))]),
        ("DetectorVerifier", Verifier(det.model),
         (torch.randn(1, 32, region_dim), torch.randn(1, 32, d), torch.zeros(1, 32, dtype=torch.int32)),
         ["regions", "positions", "padding"], ["classes", "refinement", "attributes"],
         [(1, candidate_count, region_dim), (1, candidate_count, d), (1, candidate_count)]),
        ("Evidence", Evidence(ev), tuple(tokens[k] for k in INPUT_KEYS), list(INPUT_KEYS), list(EVIDENCE_OUTPUTS),
         [(1, token_count, *tokens[k].shape[2:]) for k in INPUT_KEYS]),
    ]
    manifest = {"format_version": 1, "deployment_target": "iOS18", "precision": precision,
                "torch": torch.__version__, "coremltools": ct.__version__,
                "checkpoints": {"detector_sha256": _hash(detector), "evidence_sha256": _hash(evidence)},
                "detector": {"parameters": sum(p.numel() for p in det.model.parameters()),
                             "classes": det.classes, "attributes": ATTR_VOCAB, "stride": det.model.stride,
                             "roi": det.model.roi, "region_dim": region_dim, "position_dim": d,
                             "max_candidates": det.model.k_infer, "background_index": len(det.classes)},
                "vocab": {k: getattr(vocab, k) for k in ("CLASSES", "FAMILIES", "ALTERS", "CLEFS", "KEYS", "TIMES", "TUPLETS")},
                "models": {}, "verification": {}}
    for name, wrapper, args, names, outputs, shapes in jobs:
        print(f"Exporting {name}", flush=True)
        wrapper.eval()
        with torch.no_grad():
            traced = torch.jit.trace(wrapper, args, check_trace=True)
        ml = ct.convert(traced, source="pytorch", convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                        compute_precision=ct.precision.FLOAT32 if precision == "float32" else ct.precision.FLOAT16,
                        inputs=[ct.TensorType(name=n, shape=s, dtype=np.int32 if a.dtype == torch.int32 else np.float32)
                                for n, s, a in zip(names, shapes, args)],
                        outputs=[ct.TensorType(name=n, dtype=np.float32) for n in outputs])
        ml.short_description = f"Copisteria {name}: native shape-note OMR experiment"
        ml.license = "Apache-2.0; retain upstream LICENSE and NOTICE"
        ml.save(str(out / f"{name}.mlpackage"))
        manifest["models"][name] = {"inputs": names, "outputs": outputs}
        if verify:
            cpu = ct.models.MLModel(str(out / f"{name}.mlpackage"), compute_units=ct.ComputeUnit.CPU_ONLY)
            checks = []
            # A second shape catches traces that accidentally freeze token counts / image dimensions.
            variants = [args]
            if name == "DetectorBackbone":
                variants.append((torch.rand(1, 1, 256, 320),))
            elif name == "DetectorVerifier":
                variants.append((torch.randn(1, 17, region_dim), torch.randn(1, 17, d), torch.zeros(1, 17, dtype=torch.int32)))
            else:
                b = example_tokens(17)
                b["pad"][0, -3:] = 1
                variants.append(tuple(b[k] for k in INPUT_KEYS))
            for variant in variants:
                with torch.no_grad():
                    ref = wrapper(*variant)
                actual = cpu.predict({n: a.numpy() for n, a in zip(names, variant)})
                per_head = {}
                for n, want in zip(outputs, ref):
                    want = want.numpy()
                    got = actual[n]
                    if got.shape != want.shape or not np.isfinite(got).all():
                        raise AssertionError(f"{name}/{n}: invalid shape or nonfinite output")
                    error = float(np.max(np.abs(got - want)))
                    # Float32 is the parity baseline; fp16 is an optional later optimization.
                    np.testing.assert_allclose(got, want, atol=.003 if precision == "float32" else .15,
                                               rtol=.003 if precision == "float32" else .03,
                                               err_msg=f"{name}/{n}")
                    per_head[n] = error
                checks.append({"input_shapes": [list(a.shape) for a in variant], "max_abs_error": per_head})
            manifest["verification"][name] = checks
            print(f"Verified {name}: max error {max(max(c['max_abs_error'].values()) for c in checks):.6g}", flush=True)
        # Keep partial results reviewable if a later stage fails.
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="out/coreml")
    p.add_argument("--detector", default="models/small/v7_obj-recall-30m_best.pt")
    p.add_argument("--evidence", default="models/evidence-2m.pt")
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--width", type=int, default=768)
    p.add_argument("--precision", choices=("float32", "float16"), default="float32")
    p.add_argument("--skip-verify", action="store_true", help="convert only; native prediction needs macOS")
    a = p.parse_args(argv)
    export(a.out, a.detector, a.evidence, height=a.height, width=a.width, precision=a.precision, verify=not a.skip_verify)


if __name__ == "__main__":
    main()
