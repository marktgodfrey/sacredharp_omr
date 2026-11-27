"""Capture and replay frozen abstention snapshots on the untouched 1860 set.

This adapter performs inference and replay only. It never opens references or
scores predictions. All 38 baseline captures must pass their hash guard before
any downstream reference scoring is permitted.
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
HISTORICAL = WORKSPACE / 'benchmarks/historical-sacred-harp'
SOURCE_SET = ROOT / 'source-sets/1860-abstention-holdout-20261126'
SOURCE_MANIFEST = SOURCE_SET / 'manifest.json'
ENGINE_CONFIG = SOURCE_SET / 'engines.json'
VARIANTS = ('default', 'clean_layout')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def engines():
    if not ENGINE_CONFIG.is_file():
        raise FileNotFoundError(f'Engine mapping is not frozen yet: {ENGINE_CONFIG}')
    config = read(ENGINE_CONFIG)
    result = {}
    for name in ('prior', 'current'):
        rel = config[name]
        if isinstance(rel, dict):
            rel = rel['directory']
        path = (WORKSPACE / rel).resolve()
        if WORKSPACE.resolve() not in path.parents:
            raise ValueError(f'{name} engine directory must be workspace-relative')
        for artifact in ('source-snapshots', 'source-meter-templates.json', 'source-meter-templates.npz'):
            if not (path / artifact).exists():
                raise FileNotFoundError(f'{name} engine missing {artifact}: {path}')
        result[name] = path
    return result


def tree_hashes(root):
    return {str(p.relative_to(WORKSPACE)): sha(p)
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}


def template_hashes(config):
    return {e:{name:sha(p/name) for name in ('source-meter-templates.json','source-meter-templates.npz')}
            for e,p in config.items()}


def activate(engine, config):
    snapshot = config[engine] / 'source-snapshots'
    sys.path.insert(0, str(snapshot / 'copisteria/src'))
    sys.path.insert(0, str(snapshot / 'benchmarks/sacred-harp-1911'))
    import copisteria.paths as resources
    resources.REPO = WORKSPACE / 'copisteria'
    return snapshot


def sealed_inputs():
    manifest = read(SOURCE_MANIFEST)
    if len(manifest['samples']) != 19 or any(s['book'] != '1860-Sacred-IMSLP' for s in manifest['samples']):
        raise ValueError('Frozen source manifest is not the 19-entry 1860 holdout')
    inputs = {}
    for sample in manifest['samples']:
        for key in ('source', 'input'):
            path = HISTORICAL / sample[key]
            if not path.is_file():
                raise FileNotFoundError(path)
            inputs[str(path.relative_to(WORKSPACE))] = sha(path)
    inputs[str(SOURCE_MANIFEST.relative_to(WORKSPACE))] = sha(SOURCE_MANIFEST)
    protocol=SOURCE_SET/'PROTOCOL.md'
    if protocol.exists():inputs[str(protocol.relative_to(WORKSPACE))]=sha(protocol)
    taxonomy = WORKSPACE / 'copisteria/models/yolo_v7_taxonomy.json'
    inputs[str(taxonomy.relative_to(WORKSPACE))] = sha(taxonomy)
    return manifest, inputs


def capture(out):
    if out.exists():
        raise FileExistsError('Use a new tag; run already exists')
    config = engines()
    activate('current', config)
    from copisteria import write
    from copisteria.coreml_runtime import run
    from reader_trace import capture_writer_trace, serialize_reading
    from source_saved_events import source_saved_events
    manifest, inputs = sealed_inputs()
    models = WORKSPACE / 'copisteria/out/coreml'
    model_hashes = tree_hashes(models)
    provenance = {
        'adapter_path': str(Path(__file__).relative_to(WORKSPACE)),
        'adapter_sha256': sha(Path(__file__)),
        'source_manifest_sha256': sha(SOURCE_MANIFEST),
        'engine_config_sha256': sha(ENGINE_CONFIG),
        'frozen_engines': {e:str(p.relative_to(WORKSPACE)) for e,p in config.items()},
        'stage_descriptions': {'prior':'Frozen pre-abstention dot/false-head checkpoint',
                               'current':'Frozen conservative damaged-head abstention revision'},
        'engine_code_and_assets': {e: tree_hashes(p / 'source-snapshots') for e, p in config.items()},
        'engine_templates': template_hashes(config),
        'source_inputs_and_taxonomy_lookup_fingerprint': inputs,
        'models': model_hashes,
        'reference_opened_during_generation': False,
        'selection': 'All 19 immutable 1860 source samples, both layout variants; no new selection or tuning',
        'prediction_metadata_used': ['id', 'input'],
        'compute_units': 'CPU_ONLY',
    }
    save(out / 'manifest.json', manifest)
    save(out / 'provenance.json', provenance)
    save(out / 'adapter-snapshot.json', {'script': Path(__file__).read_text()})
    records = []
    for variant in VARIANTS:
        folder = out / 'seeds' / variant / 'predictions'
        folder.mkdir(parents=True)
        for index, sample in enumerate(manifest['samples'], 1):
            print(f'capture {variant} {index}/19 {sample["id"]}', flush=True)
            captured = []
            original = write.write

            def traced(reading, *args, **kwargs):
                with capture_writer_trace() as trace:
                    xml = original(reading, *args, **kwargs)
                captured.append({**serialize_reading(reading), 'writer': trace})
                return xml

            write.write = traced
            try:
                run(HISTORICAL / sample['input'], models, folder, units='CPU_ONLY',
                    clean_layout=variant == 'clean_layout', four_staff=False)
            except Exception:
                save(out / 'capture-failure.json', {'sample': sample['id'], 'variant': variant,
                     'traceback': traceback.format_exc(), 'references_opened': False})
                raise
            finally:
                write.write = original
            if len(captured) != 1:
                raise RuntimeError(f'Expected one traced writer call for {sample["id"]}')
            xml = folder / f'{sample["id"]}.musicxml'
            trace = captured[0]
            source_saved_events(trace, xml.read_text())
            save(xml.with_suffix('.trace.json'), trace)
            records.append({'id': sample['id'], 'variant': variant,
                            'xml_sha256': sha(xml), 'trace_sha256': sha(xml.with_suffix('.trace.json'))})
    if inputs != sealed_inputs()[1] or provenance['adapter_sha256'] != sha(Path(__file__)):
        raise RuntimeError('Input or adapter hash guard changed during capture')
    if provenance['engine_code_and_assets'] != {e: tree_hashes(p / 'source-snapshots') for e, p in config.items()}:
        raise RuntimeError('Frozen engine source or asset hash changed during capture')
    if model_hashes != tree_hashes(models):
        raise RuntimeError('Model hash changed during capture')
    if provenance['engine_config_sha256']!=sha(ENGINE_CONFIG) or provenance['engine_templates']!=template_hashes(config):
        raise RuntimeError('Engine mapping or meter templates changed during capture')
    if len(records) != 38:
        raise RuntimeError(f'Expected 38 captures; got {len(records)}')
    guard = {'cases': records, 'hash_guard_passed': True, 'references_opened': False,
             'expected_cases': 38, 'all_cases_complete': True}
    save(out / 'allcases.json', guard)
    save(out / 'capture-complete.json', guard)


def template_bank(engine, config):
    import numpy as np
    parent = config[engine]
    metadata = read(parent / 'source-meter-templates.json')['templates']
    with np.load(parent / 'source-meter-templates.npz') as arrays:
        return {label: [{**row, 'template': arrays[label.replace('/', '_') + f'_{i}'].copy()}
                        for i, row in enumerate(rows)] for label, rows in metadata.items()}


def replay(out, engine):
    guard = read(out / 'allcases.json')
    if not guard['hash_guard_passed'] or not guard['all_cases_complete'] or len(guard['cases']) != 38:
        raise ValueError('All 38 guarded baseline captures are required before replay')
    config = engines()
    provenance = read(out / 'provenance.json')
    if provenance['engine_code_and_assets'] != {e: tree_hashes(p / 'source-snapshots') for e, p in config.items()}:
        raise ValueError('Frozen engine source or asset hash guard failed')
    if provenance['source_inputs_and_taxonomy_lookup_fingerprint'] != sealed_inputs()[1]:
        raise ValueError('Source or taxonomy hash guard failed')
    if provenance['adapter_sha256'] != sha(Path(__file__)) or provenance['engine_config_sha256'] != sha(ENGINE_CONFIG):
        raise ValueError('Adapter or engine mapping hash guard failed')
    if provenance['engine_templates']!=template_hashes(config):
        raise ValueError('Frozen meter template hash guard failed')
    activate(engine, config)
    import run_source_timing_recovery as runner
    from reader_trace import _json_safe
    runner.ROOT = WORKSPACE
    bank = template_bank(engine, config)
    folder = out / engine
    if folder.exists():
        raise FileExistsError('Engine output exists; preserve this attempt')
    manifest = read(out / 'manifest.json')
    records = []
    for variant in VARIANTS:
        runner.PARENT = out / 'seeds' / variant
        for index, sample in enumerate(manifest['samples'], 1):
            print(f'{engine} {variant} {index}/19 {sample["id"]}', flush=True)
            dest = folder / variant / f'{sample["id"]}.musicxml'
            started = time.perf_counter()
            try:
                xml, trace, details = runner.recover({'id': sample['id'],
                    'input': str((HISTORICAL / sample['input']).relative_to(WORKSPACE))}, bank,
                    rhythm_resolution=True)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(xml)
                save(dest.with_suffix('.trace.json'), _json_safe(trace))
                records.append({'id': sample['id'], 'variant': variant, 'failed': False,
                    'seconds': time.perf_counter() - started, 'xml_sha256': sha(dest),
                    'trace_sha256': sha(dest.with_suffix('.trace.json')), **details})
            except Exception:
                failed = {'id': sample['id'], 'variant': variant, 'failed': True,
                          'traceback': traceback.format_exc()}
                save(dest.with_suffix('.failure.json'), failed)
                records.append(failed)
                print(failed['traceback'], flush=True)
    if provenance['engine_code_and_assets'] != {e: tree_hashes(p / 'source-snapshots') for e, p in config.items()}:
        raise RuntimeError('Frozen engine hash guard changed during replay')
    if provenance['source_inputs_and_taxonomy_lookup_fingerprint'] != sealed_inputs()[1]:
        raise RuntimeError('Source or taxonomy hash changed during replay')
    if provenance['adapter_sha256']!=sha(Path(__file__)) or provenance['engine_config_sha256']!=sha(ENGINE_CONFIG):
        raise RuntimeError('Adapter or engine mapping changed during replay')
    if provenance['engine_templates']!=template_hashes(config):
        raise RuntimeError('Frozen meter templates changed during replay')
    save(out / f'{engine}-complete.json', {'cases': records, 'hash_guard_passed': True,
         'references_opened': False, 'frozen_template_sha256': sha(config[engine] / 'source-meter-templates.npz')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('capture', 'replay'), required=True)
    parser.add_argument('--engine', choices=('prior', 'current'))
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if Path(args.tag).name != args.tag or args.tag in ('.', '..'):
        parser.error('single-directory tag required')
    out = ROOT / 'runs' / args.tag
    if args.phase == 'capture':
        capture(out)
    elif not args.engine:
        parser.error('replay requires --engine')
    else:
        replay(out, args.engine)


if __name__ == '__main__':
    main()
