"""Opt-in CoreML crop pilot; preserves the original 100-song benchmark outputs.

This experiment adds close detector views, then reads their merged detections
with the existing evidence model and writer. Full traces separate detection,
contextual interpretation, and final XML emission. No reference enters inference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from compare_musicxml import compare, parse_score
from detection_crops import plan_staff_tiles, merge_tile_detections
from reader_trace import capture_writer_trace, serialize_reading
from run_benchmark import ROOT, REPO, sha


class PinnedInputs:
    """Keep Python-owned input arrays alive while CoreML releases its bindings.

    The Python CoreML bridge can release a transient numpy view on an Apple
    background thread when a reused model changes input shape. Reuse a stable
    buffer per input shape; predictions are synchronous before buffers change.
    """
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


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def base_detect(sample, image, detector, cache):
    from copisteria.detect import imgsz_for, staff_space, measure_space
    from copisteria.vision.page.staves import find_staves
    path = cache / (sample['id'] + '.base.json')
    key = {'input_sha256': sha(ROOT / sample['input']),
           'model_manifest_sha256': sha(REPO / 'out/coreml/manifest.json'),
           'runtime_sha256': sha(REPO / 'src/copisteria/coreml_runtime.py')}
    if path.exists():
        old = json.loads(path.read_text())
        if old['key'] == key:
            return old['detections'], old['detector_size']
    ink = find_staves(image).spacing
    arr, scale = detector.prepare(image, 2048)
    dets = detector.run_array(arr, scale)
    size = imgsz_for(staff_space(ink, measure_space(dets)), max(image.size))
    if size != 2048:
        arr, scale = detector.prepare(image, size)
        dets = detector.run_array(arr, scale)
    save(path, {'key': key, 'detector_size': size, 'detections': dets})
    return dets, size


def crop_detect(sample, image, detector, base, cache, target):
    from copisteria import front
    layout = front.build(base, *image.size, image=image)
    tiles = plan_staff_tiles(layout.staves, image.size, target_spacing=target)
    path = cache / f"{sample['id']}.staff{target:g}.json"
    key = {'base_sha256': hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest(),
           'helper_sha256': sha(ROOT / 'detection_crops.py'), 'tiles': tiles}
    if path.exists():
        old = json.loads(path.read_text())
        if old['key'] == key:
            return old['detections'], old['diagnostics']
    runs = []
    for tile in tiles:
        crop = image.crop(tile['crop'])
        size = max(32, round(max(crop.size) * tile['scale']))
        arr, scale = detector.prepare(crop, size)
        runs.append({**tile, 'detections': detector.run_array(arr, scale)})
    merged, diag = merge_tile_detections(base, runs)
    diag.update(tiles=len(tiles), target_spacing=target)
    save(path, {'key': key, 'detections': merged, 'diagnostics': diag, 'tile_runs': runs})
    return merged, diag


def decode(sample, image, dets, model, folder, diagnostic, resolve_conflicts=False, auto_layout=False):
    from copisteria import write, view
    from copisteria.revise import read_revised
    start = time.perf_counter()
    readings = []
    images = [('page', image)]
    if auto_layout:
        from copisteria.front import clean_page
        images.append(('normalized', Image.fromarray(clean_page(np.asarray(image)))))
    for name, layout_image in images:
        rd = read_revised(dets, *image.size, model, attention=False, image=layout_image)
        decisions = []
        if resolve_conflicts:
            from symbol_conflicts import resolve_note_rest_conflicts
            decisions = resolve_note_rest_conflicts(rd)
        with capture_writer_trace() as emitted:
            xml = write.write(rd, image=layout_image)
        readings.append((name, rd, decisions, emitted, xml))
    from layout_selection import choose_layout
    choice, checks = choose_layout([(name, {'staves': len(rd.layout.staves),
                                            'systems': len(rd.layout.systems)}, xml)
                                   for name, rd, _, _, xml in readings])
    _, rd, decisions, emitted, xml = next(r for r in readings if r[0] == choice)
    stem = folder / sample['id']
    folder.mkdir(parents=True, exist_ok=True)
    stem.with_suffix('.musicxml').write_text(xml)
    stem.with_suffix('.html').write_text(view.page_html(rd, ROOT / sample['input'], xml, sample['id']))
    save(stem.with_suffix('.trace.json'), {'detections': dets, **serialize_reading(rd),
                                        'writer': emitted, 'symbol_conflicts': decisions})
    report = {'staves': len(rd.layout.staves), 'systems': len(rd.layout.systems),
              'parts': len(ET.fromstring(xml).findall('part')),
              'compute_units': 'CPU_ONLY', 'diagnostic': diagnostic,
              'symbol_conflicts_resolved': len(decisions),
              'layout_choice': choice, 'layout_checks': checks,
              'decode_seconds': time.perf_counter() - start}
    save(stem.with_suffix('.report.json'), report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--titles', nargs='+', default=['Plenary', 'Winter', 'Rochester', 'Monroe'])
    parser.add_argument('--targets', nargs='+', type=float, default=[16, 21.2])
    parser.add_argument('--resolve-conflicts', action='store_true', help='also test exclusive readings of overlapping note/rest glyphs')
    parser.add_argument('--out', type=Path, default=ROOT / 'experiments/reader-v1')
    args = parser.parse_args()
    torch.set_num_threads(4)
    from copisteria.coreml_runtime import CoreMLDetector, CoreMLEvidence
    detector = CoreMLDetector(REPO / 'out/coreml', units='CPU_ONLY')
    model = CoreMLEvidence(REPO / 'out/coreml', units='CPU_ONLY')
    detector.model.backbone = PinnedInputs(detector.model.backbone)
    detector.model.verifier = PinnedInputs(detector.model.verifier)
    model.native = PinnedInputs(model.native)
    manifest = json.loads((ROOT / 'manifest.json').read_text())['samples']
    samples = [s for s in manifest if s['title'] in args.titles]
    if len(samples) != len(set(args.titles)):
        raise ValueError('Title missing or ambiguous')
    baseline = {s['id']: s for s in json.loads((ROOT / 'results.json').read_text())['samples']}
    rows = []
    for sample in samples:
        print('Detecting ' + sample['title'], flush=True)
        image = Image.open(ROOT / sample['input']).convert('L')
        dets, size = base_detect(sample, image, detector, args.out / 'cache')
        ref = parse_score(ROOT / sample['reference'])
        row = {'id': sample['id'], 'title': sample['title'], 'variants': {}}
        variants = [('reproduced_default', None, False)] + [(f'staff{t:g}', t, False) for t in args.targets]
        if args.resolve_conflicts:
            variants += [('baseline_exclusive', None, True)] + [(f'staff{t:g}_exclusive', t, True) for t in args.targets]
        for variant, target, exclusive in variants:
            print('Reading ' + sample['title'] + ': ' + variant, flush=True)
            folder = args.out / variant
            if target is None:
                selected, diagnostic = dets, {'detector_size': size}
            else:
                selected, diagnostic = crop_detect(sample, image, detector, dets, args.out / 'cache', target)
            report = decode(sample, image, selected, model, folder, diagnostic, exclusive)
            path = folder / (sample['id'] + '.musicxml')
            pred = parse_score(path, line_names=[p['line'] for p in ref.summaries])
            result = compare(ref, pred)
            if target is None and not exclusive and result != baseline[sample['id']]['variants']['default']['comparison']:
                raise RuntimeError('Baseline reproduction differs: ' + sample['title'])
            row['variants'][variant] = {'comparison': result, 'report': report, 'prediction': str(path)}
        rows.append(row)
        save(args.out / 'results.json', {'samples': rows, 'source': 'manifest.json', 'reference_used_for_inference': False})
    print(json.dumps({s['title']: {k: round(v['comparison']['totals']['pitch_duration_error_rate']*100, 2)
                                 for k, v in s['variants'].items()} for s in rows}, indent=2))


if __name__ == '__main__':
    main()
