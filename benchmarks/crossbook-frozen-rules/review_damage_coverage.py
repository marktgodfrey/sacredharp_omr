"""Analyze all guarded cases of a source-first frozen damage run, including failures.

Annotations never enter recognition. Matching follows the earlier damage audit:
atomic note/rest box overlap, center within 0.75 staff spaces, best overlap first.
Unmatched/classified-as-rest/unserialized heads remain explicit failures.
"""
from __future__ import annotations
import argparse
from collections import Counter
import math
from pathlib import Path
from run_damage_coverage import (WORKSPACE, read, save, sha, sealed_inputs, engines,
                                 tree_hashes, template_hashes, validate_case_keys)


def overlap(a, b):
    return max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1])) / max(1e-9, (a[2]-a[0])*(a[3]-a[1]))


def emitted(t, i):
    return [e for e in t['writer']['emitted'] if e.get('e.si') == i]


def note_ids(t):
    return {e['e.si'] for e in t['writer']['emitted'] if e['kind'] == 'note'}


def analyze(run, source_set):
    if (run/'artifact-manifest.json').exists() or (run/'source-head-review.json').exists():
        raise ValueError('Preserve existing sealed run/review')
    manifest, selection, inputs = sealed_inputs(source_set)
    p = read(run/'provenance.json'); config = engines(source_set/'engines.json')
    assert p['source_inputs_and_taxonomy_lookup_fingerprint'] == inputs
    assert p['adapter_sha256'] == sha(WORKSPACE/p['adapter_path'])
    assert p['engine_code_and_assets'] == {e: tree_hashes(d/'source-snapshots') for e, d in config.items()}
    assert p['engine_templates'] == template_hashes(config)
    assert p['models'] == tree_hashes(WORKSPACE/'copisteria/out/coreml')
    expected = {(s['id'], v) for s in manifest['samples'] for v in manifest['variants']}
    traces = {}; failures = []; cases = {}
    for stage in ('baseline', 'prior', 'current'):
        g = read(run/('capture-complete.json' if stage == 'baseline' else f'{stage}-complete.json'))
        assert g['hash_guard_passed'] and g['all_cases_complete']
        validate_case_keys(g['cases'], manifest['samples'], stage)
        cases[stage] = {(c['id'], c['variant']): c for c in g['cases']}
        traces[stage] = {}
        for key, c in cases[stage].items():
            if c.get('failed'):
                failures.append({'stage': stage, **c}); continue
            folder = run/('seeds/'+c['variant']+'/predictions' if stage == 'baseline' else stage+'/'+c['variant'])
            tp = folder/(c['id']+'.trace.json'); xp = folder/(c['id']+'.musicxml')
            assert sha(tp) == c['trace_sha256'] and sha(xp) == c['xml_sha256']
            traces[stage][key] = read(tp)
    rows = []
    for a in selection['annotations']:
        for v in manifest['variants']:
            key = (a['sample_id'], v); base = traces['baseline'].get(key)
            row = {**a, 'variant': v, 'match': None, 'stages': {}}
            if base is None:
                row['coverage_failure'] = 'baseline_capture_failed'; rows.append(row); continue
            b = a['input_bbox_xyxy']; center = ((b[0]+b[2])/2, (b[1]+b[3])/2)
            candidates = []
            for sym in base['syms']:
                if not sym['cls'].startswith(('note_', 'rest_')): continue
                box = sym['box']; dist = math.dist(center, ((box[0]+box[2])/2, (box[1]+box[3])/2))
                staff = sym.get('staff')
                sp = base['staves'][staff]['sp'] if isinstance(staff, int) and 0 <= staff < len(base['staves']) else 12
                ov = overlap(b, box)
                if dist <= .75*sp and ov > 0:
                    candidates.append({'symbol': sym, 'distance_px': dist, 'staff_space': sp, 'annotation_overlap_fraction': ov})
            candidates.sort(key=lambda c: (-c['annotation_overlap_fraction'], c['distance_px']))
            row['matching_candidates'] = candidates
            if not candidates:
                row['coverage_failure'] = 'no_matching_frontend_note_or_rest'
            else:
                row['match'] = candidates[0]; i = candidates[0]['symbol']['i']
                for stage in traces:
                    t = traces[stage].get(key)
                    if t is None:
                        row['stages'][stage] = {'failed': True}; continue
                    es = emitted(t, i); d = t.get('rhythm_resolution_details', {})
                    row['stages'][stage] = {'source_id': i, 'emitted_as_note': any(e['kind'] == 'note' for e in es),
                        'events': es,
                        'abstentions': [r for r in d.get('source_head_abstentions', []) if r.get('sym_id') == i],
                        'removals': [r for r in d.get('duplicate_serialized_events_removed', []) if r.get('sym_id') == i]}
                if not row['stages'].get('baseline', {}).get('emitted_as_note'):
                    row['coverage_failure'] = 'frontend_rest_or_not_serialized_as_note'
            rows.append(row)
    comparisons = []
    for key in sorted(expected):
        ts = {s: traces[s].get(key) for s in traces}
        item = {'id': key[0], 'variant': key[1], 'failed_stages': [s for s, t in ts.items() if t is None]}
        for s, t in ts.items():
            if t is None: continue
            d = t.get('rhythm_resolution_details', {})
            item[s] = {'staff_count': len(t['staves']), 'abstentions': d.get('source_head_abstentions', []),
                'removals': d.get('duplicate_serialized_events_removed', []),
                'unequal_part_span_columns': t.get('final_timing', {}).get('xml_inventory', {}).get('columns_with_unequal_part_spans')}
        if all(ts.values()):
            item.update({'baseline_note_ids_lost_in_current': sorted(note_ids(ts['baseline'])-note_ids(ts['current'])),
                'prior_note_ids_lost_in_current': sorted(note_ids(ts['prior'])-note_ids(ts['current'])),
                'prior_current_writer_events_identical': ts['prior']['writer']['emitted'] == ts['current']['writer']['emitted'],
                'prior_current_xml_identical': cases['prior'][key]['xml_sha256'] == cases['current'][key]['xml_sha256']})
        comparisons.append(item)
    def counts(sub):
        return {'distinct_objects': len({r['annotation_id'] for r in sub}), 'layout_observations': len(sub),
            'matched_frontend_symbols': sum(bool(r['match']) for r in sub),
            'matched_frontend_note_classes': sum(bool(r['match']) and r['match']['symbol']['cls'].startswith('note_') for r in sub),
            **{s+'_emitted_note': sum(r['stages'].get(s, {}).get('emitted_as_note', False) for r in sub) for s in traces},
            'current_abstention_observations': sum(bool(r['stages'].get('current', {}).get('abstentions')) for r in sub),
            'coverage_failures': dict(Counter(r['coverage_failure'] for r in sub if r.get('coverage_failure')))}
    groups = []
    for status in ('likely_damaged', 'ambiguous', 'intact_control'):
        for severity in ('severe', 'moderate', 'uncertain', 'intact'):
            for shape in ('triangle', 'oval', 'square', 'diamond'):
                sub = [r for r in rows if r['status'] == status and r['severity'] == severity and r['shape'] == shape]
                groups.append({'status': status, 'severity': severity, 'shape': shape, **counts(sub)})
    result = {'reference_xml_opened': False, 'all_hash_guards_passed': True,
        'matching_method': 'Merged front-end atomic note/rest overlap; center within 0.75 assigned staff space; highest annotation overlap then nearest. Not raw detector recall. All candidates retained for manual audit.',
        'annotations_unchanged_sha256': sha(source_set/'selection.json'),
        'counts': {status: counts([r for r in rows if r['status'] == status]) for status in ('likely_damaged', 'ambiguous', 'intact_control')},
        'shape_severity_coverage': groups, 'stage_failures': failures, 'configurations': comparisons, 'annotations': rows}
    save(run/'source-head-review.json', result)
    print(result['counts']); print('stage failures', len(failures))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('run', type=Path); ap.add_argument('source_set', type=Path)
    args = ap.parse_args(); analyze(args.run.resolve(), args.source_set.resolve())
