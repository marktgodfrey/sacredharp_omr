"""Replay masking, local clipping recovery and note/rest evidence as ablations.

Predictions are saved for the complete selected batch before reference XML is
opened. Historical outputs are read-only. Every run is keyed by code and inputs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import time
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from bar_fitting import fit_bar_choices
from bar_recovery import capture_built, recovery_transform
from compare_musicxml import compare
from reader_policy import verify_reading, apply_stem_verification, detector_duration_options
from reader_trace import capture_writer_trace, serialize_reading
from replay_writer_trace import _reading
from run_reader_v2 import write_variant, conventional_score, observations_for, recovery_hits
from validate_frozen_policy import observations as holdout_observations

ROOT = Path(__file__).resolve().parent
FROZEN = ROOT/'experiments/reader-v2/source-snapshots/c13bea28e451f0aaf8888b8a3af6243e9241c3527b7b6ee9d534af9647ae1694'
VARIANTS = ('masking', 'bar_recovery', 'note_rest')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def load_frozen():
    files = ('reader_policy.py', 'glyph_verifier.py', 'guided_detection.py', 'run_reader_v2.py', 'bar_fitting.py')
    assert hashlib.sha256(b''.join((FROZEN/f).read_bytes() for f in files)).hexdigest() == FROZEN.name
    def load(name, file):
        spec = importlib.util.spec_from_file_location(name, FROZEN/file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    glyph = load('frozen_glyph', 'glyph_verifier.py')
    policy = load('frozen_policy', 'reader_policy.py')
    policy.verify_head = glyph.verify_head
    runner = load('frozen_runner', 'run_reader_v2.py')
    for name in ('verify_reading', 'apply_stem_verification', 'detector_duration_options', 'supported_rhythm_choices'):
        setattr(runner, name, getattr(policy, name))
    return runner


def samples():
    old = read(ROOT/'reader-gallery/results.json')['samples']
    current = {s['id']: s for s in read(ROOT/'experiments/reader-v2/replay_bar_fit/results.json')['samples']}
    held = {s['id']: s for s in read(ROOT/'experiments/bar-fitting/unused20/results.json')['samples']}
    rows = []
    for meta in old + read(ROOT/'experiments/bar-fitting/unused20/manifest.json')['samples']:
        sid = meta['id']; development = sid in current
        prior = current[sid]['variants']['verification_rhythm'] if development else held[sid]['variants']['frozen_bar_fit']
        rows.append({**meta, 'dataset': 'development100' if development else 'diagnostic20',
            'voice_count': len(meta['reference_structure']) if development else meta['voice_count'],
            'baseline_trace': ('reader-gallery/transcriptions/' if development else
                'experiments/bar-fitting/unused20/baseline/')+sid+'.trace.json',
            'old_prediction': str((Path('experiments/reader-v2')/prior['prediction']) if development else prior['prediction']),
            'old_comparison': prior['comparison'],
            'layout_choice': meta['report']['layout_choice'] if development else held[sid]['report']['layout_choice']})
    return rows


def evidence_reading(rd, image, note_rest):
    verified = verify_reading(rd, image)
    extra = []
    if note_rest:
        from note_rest_evidence import short_stem_evidence
        from reader_policy import near_head
        for s in rd.layout.syms:
            tok = rd.tok.get(s.i, {})
            if s.staff < 0 or s.bar < 0 or not tok.get('cls', {}).get('v', '').startswith('rest_'):
                continue
            if verified.get(s.i, {}).get('stem_found'):
                continue
            st = rd.layout.staves[s.staff]
            # Only existing, position-supported neural notes can replace a
            # rest reading. This stage never manufactures a pitch or duration.
            candidates = []
            for n in rd.layout.syms:
                r = rd.tok.get(n.i, {})
                if n.staff != s.staff or n.bar != s.bar or not r.get('cls', {}).get('v', '').startswith('note_'):
                    continue
                pos = round((st.mid-(n.box[1]+n.box[3])/2)*2/st.sp)
                if (near_head(s.box, n.box, st.sp) and r.get('pos', {}).get('p', 0) >= .6
                    and abs(r['pos']['v']-pos) <= 1
                    and max(r['real'].get('conflict_original_p', r['real']['p']), r['real'].get('det', 0)) >= .15):
                    candidates.append(n.i)
            if not candidates:
                continue
            result = short_stem_evidence(image, s.box, st.sp, rd.layout.bar_box(s.staff, s.bar))
            extra.append({'rest_id': s.i, 'note_ids': candidates, 'evidence': result})
            if result['found']:
                for sid in [s.i]+candidates:
                    if not verified.get(sid, {}).get('stem_found'):
                        verified[sid] = {**result, 'stem_found': True, 'stem_score': result['score']}
    actions = apply_stem_verification(rd, verified)
    return verified, actions, extra


def local_write(rd, image, obs, frozen_pass, *, note_rest=False, proposal_verifications=None,
                duration_constraints=None):
    from copisteria import write
    verified, actions, extra = evidence_reading(rd, image, note_rest)
    for sid, support in (proposal_verifications or {}).items():
        verified[sid] = {**verified.get(sid, {}), **support}
    options = {si: v for si,v in detector_duration_options(rd, obs).items() if rd.tok[si]['real']['p'] >= .5}
    # Source-supported proposals may rule out filled/open duration families.
    # Raw detector alternatives must not silently undo that image constraint.
    for si, allowed in (duration_constraints or {}).items():
        if si in options:
            options[si] = {k: v for k, v in options[si].items() if k in allowed}
            if len(options[si]) < 2:
                del options[si]
    decisions = []
    with fit_bar_choices(rd, verified, options) as search:
        meter_hook = write._page_meter
        # Selection is local: meter and global column cuts are fixed to the
        # source-derived frozen pass, including pickups/final complements.
        write._page_meter = lambda reading, build: frozen_pass['opening']
        try:
            with capture_writer_trace() as emitted:
                xml = write.write(rd, image=image,
                    bar_transform=recovery_transform(rd, frozen_pass, verified, decisions))
        finally:
            write._page_meter = meter_hook
    return xml, emitted, {'image_verifications': verified, 'verification_decisions': actions,
        'duration_options': options, 'rhythm_search_decisions': search,
        'local_bar_decisions': decisions, 'note_rest_evidence': extra,
        'fixed_column_cuts': [str(v) if v is not None else None for v in frozen_pass['cuts']],
        'fixed_opening_meter': frozen_pass['opening']}


def physical_loss(trace, emitted, layout):
    from bar_fitting import _overlap
    after = [e for e in emitted['emitted'] if e['kind'] == 'note']
    def same(a, b):
        if (a['step'],a['octave'],a['alter']) != (b['step'],b['octave'],b['alter']):
            return False
        if a['e.si'] == b['e.si']:
            return True
        if a['e.si'] < 0 or b['e.si'] < 0:
            return False
        sa, sb = layout.syms[a['e.si']], layout.syms[b['e.si']]
        cover, iou = _overlap(sa.box, sb.box)
        return (sa.staff,sa.bar) == (sb.staff,sb.bar) and abs(a['x']-b['x']) <= .35*layout.staves[sa.staff].sp and (cover >= .8 or iou >= .65)
    return [e['e.si'] for e in trace['writer']['emitted'] if e['kind'] == 'note' and not any(same(e,f) for f in after)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--titles', nargs='+')
    parser.add_argument('--variants', nargs='+', choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument('--tag', default='full')
    args = parser.parse_args()
    selected = [s for s in samples() if not args.titles or s['title'] in args.titles]
    code = [ROOT/f for f in ('run_local_recovery.py', 'bar_recovery.py', 'glyph_verifier.py', 'reader_policy.py',
        'run_reader_v2.py', 'bar_fitting.py', 'reader_trace.py', 'replay_writer_trace.py', 'compare_musicxml.py',
        'validate_frozen_policy.py')]
    if 'note_rest' in args.variants:
        code.append(ROOT/'note_rest_evidence.py')
    code += list((ROOT.parent.parent/'copisteria/src/copisteria').glob('*.py'))
    inputs = [ROOT/f for f in ('reader-gallery/results.json', 'experiments/reader-v2/replay_bar_fit/results.json',
        'experiments/bar-fitting/unused20/results.json', 'experiments/bar-fitting/unused20/manifest.json',
        'diagnostics/miss-trace/confirmed-misses.json')]
    for s in selected:
        cache = ROOT/('reader-gallery/cache' if s['dataset'] == 'development100' else 'experiments/bar-fitting/unused20/cache')
        inputs += [ROOT/s['input'], ROOT/s['baseline_trace'], ROOT/s['old_prediction'],
                   (ROOT/s['old_prediction']).with_suffix('.trace.json'),
                   cache/f"{s['id']}.base.json", cache/f"{s['id']}.staff16.json"]
    provenance = {str(p.relative_to(ROOT.parent.parent)): sha(p) for p in sorted(set(code+inputs))}
    frozen_files = {p.name: sha(p) for p in FROZEN.glob('*.py')}
    key = hashlib.sha256(json.dumps({'sha256': provenance, 'frozen_files': frozen_files,
        'variants': args.variants, 'ids': [s['id'] for s in selected]}, sort_keys=True).encode()).hexdigest()
    out = ROOT/'experiments/local-recovery'/f'{args.tag}-{key[:12]}'
    for p in code:
        snapshot = out/'source-snapshots'/p.relative_to(ROOT.parent.parent)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, snapshot)
    frozen = load_frozen()
    audit = read(ROOT/'diagnostics/miss-trace/confirmed-misses.json')['cases']
    records = []
    for i,s in enumerate(selected, 1):
        sid = s['id']; record_path = out/'records'/f'{sid}.json'
        if record_path.exists():
            row = read(record_path)
            assert row['experiment_key'] == key
            assert all(sha(ROOT/v['prediction']) == v['sha256'] for v in row['variants'].values())
            records.append(row)
            continue
        start = time.perf_counter()
        print(f'[{i}/{len(selected)}] {s["title"]}', flush=True)
        source = Image.open(ROOT/s['input']).convert('L')
        image = source
        if s['layout_choice'] == 'normalized':
            from copisteria.front import clean_page
            image = Image.fromarray(clean_page(np.asarray(source)))
        trace = read(ROOT/s['baseline_trace'])
        obs = observations_for(sid) if s['dataset'] == 'development100' else holdout_observations(
            ROOT/'experiments/bar-fitting/unused20/cache', sid)
        old_trace = read((ROOT/s['old_prediction']).with_suffix('.trace.json'))
        frozen_rd = _reading(copy.deepcopy(trace), source)
        with capture_built() as passes:
            baseline_xml, baseline_emitted, baseline_details = frozen.write_variant(
                frozen_rd, image, obs, verification=True, rhythm=True, bar_fit=True)
        fields = ('e.si','kind','step','octave','alter','dur')
        assert [tuple(e[k] for k in fields) for e in baseline_emitted['emitted']] == [
            tuple(e[k] for k in fields) for e in old_trace['writer']['emitted']], sid
        assert baseline_xml == (ROOT/s['old_prediction']).read_text(), sid+' XML replay mismatch'
        frozen_pass = next(p for p in reversed(passes) if p['xml'] == baseline_xml)
        row = {'id': sid, 'title': s['title'], 'dataset': s['dataset'], 'experiment_key': key,
            'frozen_exact_replay': True, 'frozen': {'comparison': s['old_comparison'],
                'audit_hits': recovery_hits(sid, old_trace, old_trace['writer'], audit)}, 'variants': {}}
        for variant in args.variants:
            rd = _reading(copy.deepcopy(trace), source)
            if variant == 'masking':
                xml, emitted, details = write_variant(rd, image, obs, verification=True, rhythm=True, bar_fit=True)
            else:
                xml, emitted, details = local_write(rd, image, obs, frozen_pass, note_rest=variant == 'note_rest')
                lost = physical_loss(old_trace, emitted, rd.layout)
                details['final_physical_note_loss'] = lost
                details['global_guard_fallback'] = bool(lost)
                if lost:
                    xml, emitted = baseline_xml, baseline_emitted
                    rd = frozen_rd
            path = out/variant/f'{sid}.musicxml'; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(xml)
            saved_trace = {**serialize_reading(rd), 'writer': emitted, **details}
            save(path.with_suffix('.trace.json'), saved_trace)
            row['variants'][variant] = {'prediction': str(path.relative_to(ROOT)), 'sha256': sha(path),
                'audit_hits': recovery_hits(sid, saved_trace, emitted, audit),
                'local_bars_selected': sum(d['selected'] != 'frozen' for d in details.get('local_bar_decisions', [])),
                'fallback_policy': details.get('fallback_policy'),
                'global_guard_fallback': details.get('global_guard_fallback', False)}
        row['seconds'] = time.perf_counter()-start
        save(record_path, row); records.append(row)
        print(f'  {row["seconds"]:.1f}s; selected bars '+str({v:r['local_bars_selected'] for v,r in row['variants'].items()}), flush=True)
    save(out/'predictions-complete.json', {'experiment_key': key, 'sha256': provenance, 'frozen_files': frozen_files,
        'samples': [s['id'] for s in selected], 'references_opened_during_generation': False,
        'expected_reference_sha256': {s['reference']: s['reference_sha256'] for s in selected},
        'interpretation': 'All 120 are diagnostic/development examples for these corrections.'})
    # Only now open the reference XML, after the entire selected batch is saved.
    reference_hashes = {}
    for row,s in zip(records, selected):
        reference_hashes[s['reference']] = sha(ROOT/s['reference'])
        assert reference_hashes[s['reference']] == s['reference_sha256'], s['id']
        ref = conventional_score(ROOT/s['reference'], s['voice_count'])
        for variant, value in row['variants'].items():
            path = ROOT/value['prediction']; assert sha(path) == value['sha256']
            value['comparison'] = compare(ref, conventional_score(path, s['voice_count']))
    aggregates = {}
    for dataset in sorted({r['dataset'] for r in records}):
        rows = [r for r in records if r['dataset'] == dataset]
        aggregates[dataset] = {}
        for variant in ('frozen', *args.variants):
            vals = [r['frozen'] if variant == 'frozen' else r['variants'][variant] for r in rows]
            ts = [v['comparison']['totals'] for v in vals]
            base = [r['frozen']['comparison']['totals']['pitch_duration_edit_distance'] for r in rows]
            delta = [t['pitch_duration_edit_distance']-b for t,b in zip(ts,base)]
            aggregates[dataset][variant] = {
                'songs': len(rows), 'edits': sum(t['pitch_duration_edit_distance'] for t in ts),
                'denominator': sum(t['pitch_duration_rate_denominator'] for t in ts),
                'pitch_edits': sum(t['pitch_edit_distance'] for t in ts),
                'prediction_notes': sum(t['prediction_notes'] for t in ts),
                'audit_hits': sum(len(v['audit_hits']) for v in vals),
                'better': sum(d<0 for d in delta), 'same': sum(d==0 for d in delta), 'worse': sum(d>0 for d in delta)}
    result = {'experiment_key': key, 'aggregates': aggregates, 'samples': records,
        'provenance': {**read(out/'predictions-complete.json'), 'reference_sha256_after_generation': reference_hashes}}
    save(out/'results.json', result)
    print(json.dumps(aggregates, indent=2), flush=True)
    print('Saved '+str(out), flush=True)


if __name__ == '__main__':
    main()
