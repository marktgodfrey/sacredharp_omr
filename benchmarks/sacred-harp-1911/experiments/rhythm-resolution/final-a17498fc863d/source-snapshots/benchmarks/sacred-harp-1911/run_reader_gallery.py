"""Run one current CoreML transcription for every song and publish its gallery."""
import argparse
import json
import shutil
import time
from pathlib import Path

import torch
from PIL import Image

from compare_musicxml import parse_score, compare
from experiment_reader import base_detect, crop_detect, decode, PinnedInputs, save
from run_benchmark import ROOT, REPO, sha


def summarize(rows):
    totals = [s['comparison']['totals'] for s in rows]
    den = sum(t['pitch_duration_rate_denominator'] for t in totals)
    edits = sum(t['pitch_duration_edit_distance'] for t in totals)
    return {'songs': len(rows), 'reference_notes': sum(t['reference_notes'] for t in totals),
            'prediction_notes': sum(t['prediction_notes'] for t in totals),
            'pitch_duration_edits': edits, 'denominator': den,
            'pitch_duration_error_rate': edits / den if den else 0,
            'pitch_error_rate': sum(t['pitch_edit_distance'] for t in totals) / den if den else 0,
            'layout_count_failures': sum(s['report']['staves'] != s['expected_staves'] or
                                         s['report']['systems'] != s['expected_systems'] for s in rows),
            'part_count_failures': sum(s['report']['parts'] != len(s['reference_structure']) for s in rows),
            'failures': sum(s['failed'] for s in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    out = ROOT / 'reader-gallery'
    cache = out / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    samples = manifest['samples'][:args.limit] if args.limit else manifest['samples']
    save(out / 'manifest.json', {**manifest, 'samples': samples})
    torch.set_num_threads(4)
    from copisteria.coreml_runtime import CoreMLDetector, CoreMLEvidence
    detector = CoreMLDetector(REPO / 'out/coreml', units='CPU_ONLY')
    model = CoreMLEvidence(REPO / 'out/coreml', units='CPU_ONLY')
    detector.model.backbone = PinnedInputs(detector.model.backbone)
    detector.model.verifier = PinnedInputs(detector.model.verifier)
    model.native = PinnedInputs(model.native)
    provenance = {'model_manifest_sha256': sha(REPO / 'out/coreml/manifest.json'),
                  'source_sha256': {f: sha(ROOT / f) for f in
                   ['run_reader_gallery.py', 'experiment_reader.py', 'detection_crops.py',
                    'symbol_conflicts.py', 'layout_selection.py', 'compare_musicxml.py']},
                  'target_staff_spacing': 16, 'compute_units': 'CPU_ONLY',
                  'layout_selection': 'structural', 'note_rest_conflict_resolution': True}
    rows = []
    for i, sample in enumerate(samples, 1):
        started = time.perf_counter()
        print(f"[{i}/{len(samples)}] {sample['title']}", flush=True)
        stem = out / 'transcriptions' / sample['id']
        ready = all(stem.with_suffix(s).exists() for s in ['.musicxml', '.html', '.report.json', '.trace.json'])
        if not ready:
            # Reuse exactly matching inference caches from the already processed songs.
            for suffix in ['.base.json', '.staff16.json']:
                name = sample['id'] + suffix
                if not (cache / name).exists():
                    for folder in ['experiments/reader-v1/cache', 'experiments/reader-v1-validation/cache']:
                        if (ROOT / folder / name).exists():
                            shutil.copyfile(ROOT / folder / name, cache / name)
                            break
            image = Image.open(ROOT / sample['input']).convert('L')
            dets, size = base_detect(sample, image, detector, cache)
            selected, diagnostic = crop_detect(sample, image, detector, dets, cache, 16)
            diagnostic['page_detector_size'] = size
            decode(sample, image, selected, model, out / 'transcriptions', diagnostic,
                   resolve_conflicts=True, auto_layout=True)
        ref = parse_score(ROOT / sample['reference'])
        pred = parse_score(stem.with_suffix('.musicxml'), line_names=[p['line'] for p in ref.summaries])
        row = {**sample, 'comparison': compare(ref, pred), 'reference_structure': ref.summaries,
               'report': json.loads(stem.with_suffix('.report.json').read_text()),
               'prediction': f"transcriptions/{sample['id']}.musicxml",
               'viewer': f"transcriptions/{sample['id']}.html", 'failed': False,
               'input_sha256': sha(ROOT / sample['input']), 'reference_sha256': sha(ROOT / sample['reference'])}
        rows.append(row)
        result = {'samples': rows, 'aggregates': summarize(rows), 'provenance': provenance}
        save(out / 'results.json', result)
        print(f"  {row['comparison']['totals']['pitch_duration_error_rate']:.1%}; {time.perf_counter()-started:.1f}s", flush=True)
    from build_reader_gallery import build
    build()
    print(json.dumps(summarize(rows), indent=2), flush=True)


if __name__ == '__main__':
    main()
