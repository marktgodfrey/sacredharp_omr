"""Prospective validation of the frozen bar policy on a disjoint song set.

Inference and scoring are separate commands. Inference never opens a reference;
all predictions must exist before scoring starts. No policy is fitted here.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from experiment_reader import PinnedInputs, base_detect, crop_detect, decode, save
from replay_writer_trace import _reading
from reader_trace import serialize_reading
from run_benchmark import ROOT, REPO, sha
from run_reader_v2 import conventional_score, write_variant
from compare_musicxml import compare

POLICY_FILES = ['reader_policy.py', 'glyph_verifier.py', 'guided_detection.py',
                'run_reader_v2.py', 'bar_fitting.py']
FROZEN_KEY = 'c13bea28e451f0aaf8888b8a3af6243e9241c3527b7b6ee9d534af9647ae1694'
OUT = ROOT / 'experiments/bar-fitting/unused20'


def policy_key():
    key = hashlib.sha256(b''.join((ROOT / p).read_bytes() for p in POLICY_FILES)).hexdigest()
    if key != FROZEN_KEY:
        raise RuntimeError('Frozen policy changed; this validation must not tune it')
    return key


def observations(cache, sid):
    rows = list(json.loads((cache / f'{sid}.base.json').read_text())['detections'])
    for run in json.loads((cache / f'{sid}.staff16.json').read_text())['tile_runs']:
        x, y = run['crop'][:2]
        for item in run['detections']:
            if item['cls'].startswith('note_'):
                d = dict(item)
                a, b, c, e = d['xyxy']
                d['xyxy'] = [a+x, b+y, c+x, e+y]
                rows.append(d)
    return rows


def check_plan():
    plan = json.loads((OUT / 'manifest.json').read_text())
    old = json.loads((ROOT / 'reader-gallery/manifest.json').read_text())['samples']
    samples = plan['samples']
    if len(samples) != 20 or len({s['id'] for s in samples}) != 20:
        raise RuntimeError('Exactly twenty unique preregistered songs required')
    for field in ['id', 'reference_source']:
        if {s[field] for s in samples} & {s[field] for s in old}:
            raise RuntimeError('Development/validation overlap: ' + field)
    from expand_dataset import normalize
    if {normalize(s['title']) for s in samples} & {normalize(s['title']) for s in old}:
        raise RuntimeError('Development/validation title overlap')
    for s in samples:
        if sha(ROOT / s['input']) != s['input_sha256']:
            raise RuntimeError('Preregistered input changed: ' + s['id'])
    policy_key()
    return plan


def infer(plan):
    import torch
    from copisteria.coreml_runtime import CoreMLDetector, CoreMLEvidence
    from copisteria.front import clean_page
    torch.set_num_threads(4)
    detector = CoreMLDetector(REPO / 'out/coreml', units='CPU_ONLY')
    model = CoreMLEvidence(REPO / 'out/coreml', units='CPU_ONLY')
    detector.model.backbone = PinnedInputs(detector.model.backbone)
    detector.model.verifier = PinnedInputs(detector.model.verifier)
    model.native = PinnedInputs(model.native)
    cache = OUT / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    for n, sample in enumerate(plan['samples'], 1):
        sid = sample['id']
        record = OUT / 'records' / f'{sid}.json'
        if record.exists():
            continue
        started = time.perf_counter()
        print(f'[{n}/20] {sample["title"]}', flush=True)
        source = Image.open(ROOT / sample['input']).convert('L')
        base, size = base_detect(sample, source, detector, cache)
        dets, diag = crop_detect(sample, source, detector, base, cache, 16)
        diag['page_detector_size'] = size
        stem = OUT / 'baseline' / sid
        if not stem.with_suffix('.trace.json').exists():
            decode(sample, source, dets, model, stem.parent, diag,
                   resolve_conflicts=True, auto_layout=True)
        report = json.loads(stem.with_suffix('.report.json').read_text())
        trace = json.loads(stem.with_suffix('.trace.json').read_text())
        image = Image.fromarray(clean_page(np.asarray(source))) if report['layout_choice'] == 'normalized' else source
        obs = observations(cache, sid)
        outputs = {}
        for name, bar_fit in [('verification_rhythm', False), ('frozen_bar_fit', True)]:
            rd = _reading(copy.deepcopy(trace), source)
            xml, emitted, details = write_variant(rd, image, obs, verification=True,
                                                  rhythm=True, bar_fit=bar_fit)
            path = OUT / name / f'{sid}.musicxml'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(xml)
            save(path.with_suffix('.trace.json'), {**serialize_reading(rd), 'writer': emitted, **details})
            outputs[name] = {'prediction_sha256': sha(path), 'fallback_policy': details['fallback_policy']}
        save(record, {'id': sid, 'policy_key': policy_key(), 'input_sha256': sample['input_sha256'],
                      'baseline_sha256': sha(stem.with_suffix('.musicxml')), 'outputs': outputs,
                      'report': report, 'seconds': time.perf_counter()-started,
                      'references_opened_during_inference': False})
        print(f'  completed in {time.perf_counter()-started:.1f}s', flush=True)
    save(OUT / 'inference-complete.json', {'policy_key': policy_key(), 'manifest_sha256': sha(OUT / 'manifest.json'),
          'songs': 20, 'model_manifest_sha256': sha(REPO / 'out/coreml/manifest.json'),
          'compute_units': 'CPU_ONLY', 'references_opened_during_inference': False,
          'runner_sha256': sha(Path(__file__))})


def score(plan):
    completion = json.loads((OUT / 'inference-complete.json').read_text())
    assert completion['manifest_sha256'] == sha(OUT / 'manifest.json')
    rows = []
    names = ['baseline', 'verification_rhythm', 'frozen_bar_fit']
    for s in plan['samples']:
        record = json.loads((OUT / 'records' / f'{s["id"]}.json').read_text())
        # Reference integrity is checked only after the entire inference batch.
        assert sha(ROOT / s['reference']) == s['reference_sha256']
        ref = conventional_score(ROOT / s['reference'], s['voice_count'])
        row = {'id': s['id'], 'title': s['title'], 'variants': {}, 'report': record['report']}
        for name in names:
            path = OUT / name / f'{s["id"]}.musicxml'
            expected = record['baseline_sha256'] if name == 'baseline' else record['outputs'][name]['prediction_sha256']
            assert sha(path) == expected
            row['variants'][name] = {'comparison': compare(ref, conventional_score(path, s['voice_count'])),
                                    'prediction': str(path.relative_to(ROOT))}
        row['fallback_policy'] = record['outputs']['frozen_bar_fit']['fallback_policy']
        rows.append(row)
    totals = {}
    for name in names:
        ts = [r['variants'][name]['comparison']['totals'] for r in rows]
        ed = sum(t['pitch_duration_edit_distance'] for t in ts)
        den = sum(t['pitch_duration_rate_denominator'] for t in ts)
        totals[name] = {'songs': 20, 'edits': ed, 'denominator': den, 'rate': ed/den,
                       'pitch_edits': sum(t['pitch_edit_distance'] for t in ts),
                       'reference_notes': sum(t['reference_notes'] for t in ts),
                       'prediction_notes': sum(t['prediction_notes'] for t in ts)}
    changes = {}
    for before in names[:2]:
        delta = [r['variants']['frozen_bar_fit']['comparison']['totals']['pitch_duration_edit_distance'] -
                 r['variants'][before]['comparison']['totals']['pitch_duration_edit_distance'] for r in rows]
        changes[before] = {'better': sum(d < 0 for d in delta), 'same': sum(d == 0 for d in delta),
                           'worse': sum(d > 0 for d in delta), 'edit_delta': sum(delta)}
    result = {'samples': rows, 'aggregates': totals, 'changes_by_edit_count': changes,
              'provenance': completion, 'selection': plan['selection'], 'policy_tuned_on_validation': False}
    save(OUT / 'results.json', result)
    labels = {'baseline': 'Reader baseline', 'verification_rhythm': 'Verification + rhythm',
              'frozen_bar_fit': 'Frozen bar fitting'}
    lines = ['# Frozen policy: 20 unused songs', '',
             'These songs are disjoint from the 100-song development benchmark by title and reference file. '
             'Selection used source completeness, normal vocal layout and edition compatibility, before recognition results. '
             'This is a source-screened convenience sample, not a random sample of the book.', '',
             'All 20 predictions were saved before the scoring phase opened any reference MusicXML. '
             'The frozen policy was not modified or fitted on these results. The 2025 edition is a comparison reference; '
             'edition differences can also cause disagreement.', '',
             f'Policy SHA-256: `{FROZEN_KEY}`', '',
             f'Manifest SHA-256: `{completion["manifest_sha256"]}`', '',
             'Inference: local Apple CoreML, CPU_ONLY; full-page detection plus the same staff-16 crop detection and '
             'structural layout selection used for the development benchmark. The same saved reading feeds both policies. '
             'The independent variable is bar fitting; no new detector training or normalization is introduced.', '',
             '| Output | Pitch + duration edits | Positions | Disagreement |',
             '|---|---:|---:|---:|']
    for name in names:
        t = totals[name]
        lines.append(f'| {labels[name]} | {t["edits"]} | {t["denominator"]} | {t["rate"]:.2%} |')
    lines += ['', 'Rates are weighted by total sequence positions, not averaged over songs.', '']
    for name, c in changes.items():
        lines.append(f'Compared with {labels[name].lower()}: {c["better"]} songs have fewer edits, '
                     f'{c["same"]} tie and {c["worse"]} have more; net change {c["edit_delta"]:+d} edits.')
    lines += ['', '| Song | Baseline edits | Verification + rhythm edits | Frozen edits | Frozen − previous | Fallback |',
              '|---|---:|---:|---:|---:|---|']
    csv_rows = []
    for row in rows:
        counts = [row['variants'][n]['comparison']['totals']['pitch_duration_edit_distance'] for n in names]
        lines.append(f'| {row["title"]} | {counts[0]} | {counts[1]} | {counts[2]} | {counts[2]-counts[1]:+d} | {row["fallback_policy"] or "none"} |')
        csv_rows.append({'id': row['id'], 'title': row['title'], 'baseline_edits': counts[0],
                         'verification_rhythm_edits': counts[1], 'frozen_edits': counts[2],
                         'delta_vs_previous': counts[2]-counts[1], 'fallback_policy': row['fallback_policy'] or 'none'})
    (OUT / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    with (OUT / 'per-song.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    print(json.dumps({'aggregates': totals, 'changes': changes}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=['infer', 'score'])
    args = parser.parse_args()
    plan = check_plan()
    (infer if args.phase == 'infer' else score)(plan)
