"""Capture/replay unchanged frozen rules on a source-first multi-book damage set.

Inference and replay only: this adapter never reads reference annotations or
scores predictions. Selection annotations are sealed as source-only ground
truth and are never passed to either inference or recovery.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
VARIANTS = ('default', 'clean_layout')


def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def expected_case_keys(samples):
    return {(sample['id'], variant) for variant in VARIANTS for sample in samples}


def validate_case_keys(records, samples, label):
    expected = expected_case_keys(samples)
    keys = [(record.get('id'), record.get('variant')) for record in records]
    actual = set(keys)
    if len(keys) != len(actual) or actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(f'{label} case set mismatch: missing={missing}, unexpected={unexpected}, duplicates={len(keys)-len(actual)}')


def source_paths(source_set):
    source_set = source_set.resolve()
    if WORKSPACE.resolve() not in source_set.parents:
        raise ValueError('--source-set must resolve inside the workspace')
    manifest_path = source_set / 'manifest.json'
    selection_path = source_set / 'selection.json'
    protocol_path = source_set / 'PROTOCOL.md'
    engine_path = source_set / 'engines.json'
    for p in (manifest_path, selection_path, protocol_path, engine_path):
        if not p.is_file(): raise FileNotFoundError(p)
    return manifest_path, selection_path, protocol_path, engine_path


def engines(engine_config):
    config = read(engine_config)
    result = {}
    for name in ('prior', 'current'):
        rel = config[name]
        if isinstance(rel, dict): rel = rel['directory']
        path = (WORKSPACE / rel).resolve()
        if WORKSPACE.resolve() not in path.parents:
            raise ValueError(f'{name} engine directory must be workspace-relative')
        for artifact in ('source-snapshots', 'source-meter-templates.json', 'source-meter-templates.npz'):
            if not (path / artifact).exists(): raise FileNotFoundError(f'{name} engine missing {artifact}: {path}')
        result[name] = path
    return result


def tree_hashes(root):
    return {str(p.relative_to(WORKSPACE)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def template_hashes(config):
    return {e: {name: sha(p / name) for name in ('source-meter-templates.json', 'source-meter-templates.npz')}
            for e, p in config.items()}


def activate(engine, config):
    snapshot = config[engine] / 'source-snapshots'
    sys.path.insert(0, str(snapshot / 'copisteria/src'))
    sys.path.insert(0, str(snapshot / 'benchmarks/sacred-harp-1911'))
    import copisteria.paths as resources
    # Frozen archive omits taxonomy; runtime vocabulary lookup uses workspace assets.
    resources.REPO = WORKSPACE / 'copisteria'
    return snapshot


def sealed_inputs(source_set):
    manifest_path, selection_path, protocol_path, engine_path = source_paths(source_set)
    manifest, selection = read(manifest_path), read(selection_path)
    samples = manifest.get('samples')
    if not isinstance(samples, list) or not samples:
        raise ValueError('Source manifest must contain a nonempty samples array')
    ids = [s.get('id') for s in samples]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError('Every source sample needs a unique id')
    books = {s.get('book') for s in samples}
    if None in books or '' in books:
        raise ValueError('Every damage-coverage sample must declare a book')
    if any(not all(k in s for k in ('id', 'book', 'source', 'input')) for s in samples):
        raise ValueError('Each sample needs id, book, source, and input')
    if selection.get('status') != 'locked_before_inference':
        raise ValueError('Selection must have status locked_before_inference')
    annotations = selection.get('annotations')
    if not isinstance(annotations, list) or not annotations:
        raise ValueError('Selection annotations must be a nonempty array')
    annotated = {a.get('sample_id') for a in annotations if isinstance(a, dict)}
    if not annotated or not annotated.issubset(set(ids)):
        raise ValueError('Every annotation sample_id must be present in the source manifest')
    inputs = {}
    for sample in samples:
        for key in ('source', 'input'):
            rel = Path(sample[key])
            if rel.is_absolute(): raise ValueError(f'{key} must be workspace-relative: {rel}')
            path = (WORKSPACE / rel).resolve()
            if WORKSPACE.resolve() not in path.parents: raise ValueError(f'{key} escapes workspace: {rel}')
            if not path.is_file(): raise FileNotFoundError(path)
            inputs[str(path.relative_to(WORKSPACE))] = sha(path)
    for p in (manifest_path, selection_path, protocol_path):
        inputs[str(p.relative_to(WORKSPACE))] = sha(p)
    # This source-first lock also binds the original PDF and preselection plan.
    lock_path = source_set / 'selection-lock.json'
    lock = read(lock_path)
    if lock.get('predictions_started') is not False or not lock.get('sha256'):
        raise ValueError('A pre-inference source selection lock is required')
    for rel, expected in lock['sha256'].items():
        path = (WORKSPACE / rel).resolve()
        if WORKSPACE.resolve() not in path.parents or sha(path) != expected:
            raise ValueError(f'Selection lock mismatch: {rel}')
        inputs[str(path.relative_to(WORKSPACE))] = expected
    inputs[str(lock_path.relative_to(WORKSPACE))] = sha(lock_path)
    taxonomy = WORKSPACE / 'copisteria/models/yolo_v7_taxonomy.json'
    inputs[str(taxonomy.relative_to(WORKSPACE))] = sha(taxonomy)
    return manifest, selection, inputs


def capture(out, source_set):
    if out.exists(): raise FileExistsError('Use a new tag; run already exists')
    manifest_path, selection_path, protocol_path, engine_path = source_paths(source_set)
    config = engines(engine_path)
    activate('current', config)
    from copisteria import write
    from copisteria.coreml_runtime import run
    from reader_trace import capture_writer_trace, serialize_reading
    from source_saved_events import source_saved_events
    manifest, selection, inputs = sealed_inputs(source_set)
    count = len(manifest['samples'])
    models = WORKSPACE / 'copisteria/out/coreml'
    model_hashes = tree_hashes(models)
    provenance = {
        'adapter_path': str(Path(__file__).relative_to(WORKSPACE)), 'adapter_sha256': sha(Path(__file__)),
        'source_manifest_sha256': sha(manifest_path), 'selection_sha256': sha(selection_path),
        'protocol_sha256': sha(protocol_path), 'engine_config_sha256': sha(engine_path),
        'frozen_engines': {e: str(p.relative_to(WORKSPACE)) for e, p in config.items()},
        'engine_code_and_assets': {e: tree_hashes(p / 'source-snapshots') for e, p in config.items()},
        'engine_templates': template_hashes(config), 'source_inputs_and_taxonomy_lookup_fingerprint': inputs,
        'models': model_hashes, 'reference_opened_during_generation': False,
        'selection': f'All {count} locked source samples, both layout variants; no new selection or tuning',
        'selection_annotations_used_for_prediction': False,
        'prediction_metadata_used': ['id', 'input'], 'compute_units': 'CPU_ONLY'}
    save(out / 'manifest.json', manifest)
    save(out / 'provenance.json', provenance)
    save(out / 'adapter-snapshot.json', {'script': Path(__file__).read_text()})
    save(out / 'selection.json', selection)
    (out / 'PROTOCOL.md').write_bytes(protocol_path.read_bytes())
    records = []
    for variant in VARIANTS:
        folder = out / 'seeds' / variant / 'predictions'
        folder.mkdir(parents=True)
        for index, sample in enumerate(manifest['samples'], 1):
            print(f'capture {variant} {index}/{count} {sample["id"]}', flush=True)
            captured, original = [], write.write
            def traced(reading, *args, **kwargs):
                with capture_writer_trace() as trace: xml = original(reading, *args, **kwargs)
                captured.append({**serialize_reading(reading), 'writer': trace})
                return xml
            write.write = traced
            case = {'id': sample['id'], 'variant': variant}
            try:
                run(WORKSPACE / sample['input'], models, folder, units='CPU_ONLY',
                    clean_layout=variant == 'clean_layout', four_staff=False)
                if len(captured) != 1:
                    raise RuntimeError(f'Expected one traced writer call for {sample["id"]}; observed {len(captured)}')
                xml = folder / f'{sample["id"]}.musicxml'
                if not xml.is_file(): raise FileNotFoundError(f'Writer produced no XML: {xml}')
                trace = captured[0]
                source_saved_events(trace, xml.read_text())
                trace_path = xml.with_suffix('.trace.json')
                save(trace_path, trace)
                case.update({'failed': False, 'xml_sha256': sha(xml), 'trace_sha256': sha(trace_path)})
            except Exception:
                case.update({'failed': True, 'traceback': traceback.format_exc(),
                             'xml_present': (folder / f'{sample["id"]}.musicxml').is_file(),
                             'references_opened': False})
                print(case['traceback'], flush=True)
            finally: write.write = original
            records.append(case)
    validate_case_keys(records, manifest['samples'], 'Capture')
    hash_errors = []
    if inputs != sealed_inputs(source_set)[2] or provenance['adapter_sha256'] != sha(Path(__file__)):
        hash_errors.append('Input or adapter hash guard changed during capture')
    if provenance['engine_code_and_assets'] != {e: tree_hashes(p / 'source-snapshots') for e, p in config.items()}:
        hash_errors.append('Frozen engine source or asset hash changed during capture')
    if model_hashes != tree_hashes(models): hash_errors.append('Model hash changed during capture')
    if provenance['engine_config_sha256'] != sha(engine_path) or provenance['engine_templates'] != template_hashes(config):
        hash_errors.append('Engine mapping or meter templates changed during capture')
    expected = count * len(VARIANTS)
    guard = {'cases': records, 'hash_guard_passed': not hash_errors, 'hash_guard_errors': hash_errors,
             'references_opened': False, 'expected_cases': expected, 'all_cases_complete': len(records) == expected,
             'all_cases_succeeded': all(not record.get('failed', False) for record in records)}
    save(out / 'allcases.json', guard); save(out / 'capture-complete.json', guard)
    if hash_errors: raise RuntimeError('; '.join(hash_errors))


def template_bank(engine, config):
    import numpy as np
    parent = config[engine]; metadata = read(parent / 'source-meter-templates.json')['templates']
    with np.load(parent / 'source-meter-templates.npz') as arrays:
        return {label: [{**row, 'template': arrays[label.replace('/', '_') + f'_{i}'].copy()}
                        for i, row in enumerate(rows)] for label, rows in metadata.items()}


def replay(out, engine, source_set):
    manifest_path, selection_path, protocol_path, engine_path = source_paths(source_set)
    manifest, selection, inputs = sealed_inputs(source_set)
    count = len(manifest['samples']); expected = count * len(VARIANTS)
    guard = read(out / 'allcases.json')
    validate_case_keys(guard.get('cases', []), manifest['samples'], 'Baseline capture')
    if (not guard['hash_guard_passed'] or not guard['all_cases_complete'] or
            len(guard['cases']) != expected or guard.get('expected_cases') != expected):
        raise ValueError(f'All {expected} guarded baseline captures are required before replay')
    config = engines(engine_path); provenance = read(out / 'provenance.json')
    if provenance['engine_code_and_assets'] != {e: tree_hashes(p / 'source-snapshots') for e, p in config.items()}:
        raise ValueError('Frozen engine source or asset hash guard failed')
    if provenance['source_inputs_and_taxonomy_lookup_fingerprint'] != inputs:
        raise ValueError('Source, selection, protocol, or taxonomy hash guard failed')
    if provenance['adapter_sha256'] != sha(Path(__file__)) or provenance['engine_config_sha256'] != sha(engine_path):
        raise ValueError('Adapter or engine mapping hash guard failed')
    if provenance['engine_templates'] != template_hashes(config): raise ValueError('Frozen meter template hash guard failed')
    baseline = {(case['id'], case['variant']): case for case in guard['cases']}
    for (sample_id, variant), case in baseline.items():
        if case.get('failed'): continue
        xml = out / 'seeds' / variant / 'predictions' / f'{sample_id}.musicxml'
        trace = xml.with_suffix('.trace.json')
        if not xml.is_file() or not trace.is_file():
            raise ValueError(f'Baseline output missing before replay: {sample_id} / {variant}')
        if sha(xml) != case.get('xml_sha256') or sha(trace) != case.get('trace_sha256'):
            raise ValueError(f'Baseline XML/trace hash mismatch before replay: {sample_id} / {variant}')
    activate(engine, config)
    import run_source_timing_recovery as runner
    from reader_trace import _json_safe
    runner.ROOT = WORKSPACE; bank = template_bank(engine, config); folder = out / engine
    if folder.exists(): raise FileExistsError('Engine output exists; preserve this attempt')
    records = []
    for variant in VARIANTS:
        runner.PARENT = out / 'seeds' / variant
        for index, sample in enumerate(manifest['samples'], 1):
            print(f'{engine} {variant} {index}/{count} {sample["id"]}', flush=True)
            dest = folder / variant / f'{sample["id"]}.musicxml'; started = time.perf_counter()
            base = baseline[(sample['id'], variant)]
            if base.get('failed'):
                failed = {'id': sample['id'], 'variant': variant, 'failed': True,
                          'baseline_failed': True, 'baseline_traceback': base.get('traceback', '')}
                dest.parent.mkdir(parents=True, exist_ok=True)
                save(dest.with_suffix('.failure.json'), failed)
                records.append(failed)
                continue
            try:
                # Only id/input are supplied; selection annotations never enter recover().
                xml, trace, details = runner.recover({'id': sample['id'],
                    'input': sample['input']}, bank, rhythm_resolution=True)
                dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(xml)
                save(dest.with_suffix('.trace.json'), _json_safe(trace))
                records.append({'id': sample['id'], 'variant': variant, 'failed': False,
                    'seconds': time.perf_counter() - started, 'xml_sha256': sha(dest),
                    'trace_sha256': sha(dest.with_suffix('.trace.json')), **details})
            except Exception:
                failed = {'id': sample['id'], 'variant': variant, 'failed': True, 'traceback': traceback.format_exc()}
                save(dest.with_suffix('.failure.json'), failed); records.append(failed)
                print(failed['traceback'], flush=True)
    validate_case_keys(records, manifest['samples'], f'{engine} replay')
    if provenance['engine_code_and_assets'] != {e: tree_hashes(p / 'source-snapshots') for e, p in config.items()}:
        raise RuntimeError('Frozen engine hash changed during replay')
    if provenance['source_inputs_and_taxonomy_lookup_fingerprint'] != sealed_inputs(source_set)[2]:
        raise RuntimeError('Source, selection, protocol, or taxonomy hash changed during replay')
    if provenance['adapter_sha256'] != sha(Path(__file__)) or provenance['engine_config_sha256'] != sha(engine_path):
        raise RuntimeError('Adapter or engine mapping changed during replay')
    if provenance['engine_templates'] != template_hashes(config): raise RuntimeError('Frozen meter templates changed during replay')
    save(out / f'{engine}-complete.json', {'cases': records, 'hash_guard_passed': True,
         'references_opened': False, 'expected_cases': expected, 'all_cases_complete': len(records) == expected,
         'all_cases_succeeded': all(not record.get('failed', False) for record in records),
         'frozen_template_sha256': sha(config[engine] / 'source-meter-templates.npz')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('capture', 'replay'), required=True)
    parser.add_argument('--engine', choices=('prior', 'current'))
    parser.add_argument('--source-set', required=True, help='Workspace-relative source-set directory')
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if Path(args.tag).name != args.tag or args.tag in ('.', '..'): parser.error('single-directory tag required')
    rel = Path(args.source_set)
    if rel.is_absolute(): parser.error('--source-set must be workspace-relative')
    source_set = (WORKSPACE / rel).resolve()
    if args.phase == 'capture': capture(ROOT / 'runs' / args.tag, source_set)
    elif not args.engine: parser.error('replay requires --engine')
    else: replay(ROOT / 'runs' / args.tag, args.engine, source_set)


if __name__ == '__main__': main()
