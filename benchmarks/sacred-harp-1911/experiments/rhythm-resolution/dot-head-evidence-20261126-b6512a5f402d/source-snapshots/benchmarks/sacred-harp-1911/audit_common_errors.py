#!/usr/bin/env python3
"""Describe saved final outputs; no inference, policy changes, or reference-fed repair."""
from __future__ import annotations

import hashlib
import json
import copy
from collections import Counter, defaultdict
from contextlib import nullcontext
from pathlib import Path

import numpy as np
from PIL import Image
from compare_musicxml import compare
from run_reader_v2 import conventional_score, near_head

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'diagnostics/common-errors'


def read(path):
    return json.loads(path.read_text())


def alignment(ref, pred):
    """One minimum pitch-edit alignment; ties prefer match, substitute, delete."""
    a, b = [e.pitch for e in ref], [e.pitch for e in pred]
    m = [list(range(len(b) + 1))] + [[i] + [0] * len(b) for i in range(1, len(a) + 1)]
    for i, x in enumerate(a, 1):
        for j, y in enumerate(b, 1):
            m[i][j] = min(m[i-1][j]+1, m[i][j-1]+1, m[i-1][j-1]+(x != y))
    pairs = []
    i, j = len(a), len(b)
    while i or j:
        if i and j and a[i-1] == b[j-1] and m[i][j] == m[i-1][j-1]:
            pairs.append(('match', i-1, j-1)); i -= 1; j -= 1
        elif i and j and m[i][j] == m[i-1][j-1]+1:
            pairs.append(('substitute', i-1, j-1)); i -= 1; j -= 1
        elif i and m[i][j] == m[i-1][j]+1:
            pairs.append(('delete', i-1, None)); i -= 1
        else:
            pairs.append(('insert', None, j-1)); j -= 1
    assert sum(k != 'match' for k, _, _ in pairs) == m[-1][-1]
    return list(reversed(pairs))


def replay_final_clipping(row, meta, trace, cases):
    """Reconstruct an already selected fallback; capture final clipping only."""
    from copisteria import write
    from reader_policy import supported_rhythm_choices
    from reader_trace import capture_writer_trace
    from replay_writer_trace import _reading, _event
    image = Image.open(ROOT/meta['input']).convert('L')
    assert meta['report']['layout_choice'] == 'page'
    rd = _reading(copy.deepcopy(trace), image)
    original_chop, original_columns = write._chop, write._column_lengths
    final = False
    chops = []

    def columns(built):
        nonlocal final
        result = original_columns(built)
        final = True
        return result

    def chop(events, cut):
        before = [_event(e) for e in events]
        result = original_chop(events, cut)
        if final:
            kept = {e.si for e in result}
            dropped = [e for e in before if e['kind'] == 'note' and e['si'] not in kept]
            if dropped:
                chops.append({'cut': str(cut), 'input': before, 'dropped': dropped,
                              'kept': [_event(e) for e in result]})
        return result

    context = nullcontext() if row['fallback'] == 'original' else supported_rhythm_choices({
        int(k): v for k, v in trace['duration_options'].items()
        if trace['image_verifications'].get(k, {}).get('stem_found')})
    write._chop, write._column_lengths = chop, columns
    try:
        with context:
            with capture_writer_trace() as emitted:
                write.write(rd, image=image)
    finally:
        write._chop, write._column_lengths = original_chop, original_columns
    fields = ('e.si', 'kind', 'step', 'octave', 'alter', 'dur')
    actual = [tuple(e[k] for k in fields) for e in emitted['emitted']]
    saved = [tuple(e[k] for k in fields) for e in trace['writer']['emitted']]
    assert actual == saved, row['id']
    dropped = {e['si'] for c in chops for e in c['dropped']}
    reviewed = [c['case_id'] for c in cases if c['id'] == row['id']
                and set(c['accepted_note_ids']) & dropped]
    return {'id': row['id'], 'title': row['title'], 'policy': row['fallback'],
            'exact_final_emission_replay': True, 'final_clipping_reviewed_heads': reviewed,
            'final_chops_with_note_loss': chops}


def mask_diagnostic(case, meta, trace):
    """Measure existing verifier row masking on three visibly filled heads."""
    sym = trace['syms'][case['anchor_sym_id']]
    sp = trace['staves'][sym['staff']]['sp']
    x0, y0, x1, y1 = sym['box']
    gray = np.asarray(Image.open(ROOT/meta['input']).convert('L'))
    xo, yo = max(0, int(np.floor(x0-4*sp))), max(0, int(np.floor(y0-4*sp)))
    gray = gray[yo:min(gray.shape[0], int(np.ceil(y1+4*sp))),
                xo:min(gray.shape[1], int(np.ceil(x1+4*sp)))]
    threshold = float(np.clip(np.percentile(gray, 90)-40, 130, 205))
    ink = gray < threshold
    a, b = int(np.floor(x0-xo)), int(np.floor(y0-yo))
    c, d = int(np.ceil(x1-xo)), int(np.ceil(y1-yo))
    head = ink[b:d, a:c].copy()
    ext = round(2*sp)
    left = ink[b:d, max(0,a-ext):max(0,a-1)]
    right = ink[b:d, min(ink.shape[1],c+1):min(ink.shape[1],c+ext+1)]
    rows = (left.sum(axis=1) >= 2) & (right.sum(axis=1) >= 2)
    raw = float(head.mean()); head[rows, :] = False
    masked = float(head.mean())
    evidence = trace['image_verifications'][str(sym['i'])]
    assert round(masked, 3) == evidence['head_ink_fraction']
    return {'case_id': case['case_id'], 'id': case['song_id'], 'symbol_id': sym['i'],
            'raw_head_ink_fraction': raw, 'masked_head_ink_fraction': masked,
            'masked_rows': int(rows.sum()), 'head_rows': len(rows), 'saved_verification': evidence}


def main():
    paths = [ROOT/'experiments/reader-v2/replay_bar_fit/results.json',
             ROOT/'experiments/bar-fitting/unused20/results.json',
             ROOT/'reader-gallery/results.json',
             ROOT/'experiments/bar-fitting/unused20/manifest.json',
             ROOT/'diagnostics/miss-trace/confirmed-misses.json']
    dev, hold, old, hm, audit = map(read, paths)
    metadata = {r['id']: r for r in old['samples'] + hm['samples']}
    sources = set(paths)
    groups = defaultdict(Counter)
    songs, duration_pairs = [], []
    traces = {}
    for dataset, rows, variant, prefix in (
        ('development100', dev['samples'], 'verification_rhythm', ROOT/'experiments/reader-v2'),
        ('previously_unused20', hold['samples'], 'frozen_bar_fit', ROOT),
    ):
        for row in rows:
            sid = row['id']; meta = metadata[sid]; record = row['variants'][variant]
            pred_path = prefix/record['prediction']; ref_path = ROOT/meta['reference']
            trace_path = pred_path.with_suffix('.trace.json')
            sources.update((pred_path, ref_path, trace_path))
            traces[sid] = trace = read(trace_path)
            voices = meta.get('voice_count', len(meta.get('reference_structure', [])))
            ref = conventional_score(ref_path, voices)
            pred = conventional_score(pred_path, voices)
            scored = compare(ref, pred)
            assert scored['totals'] == record['comparison']['totals'], sid
            counts = Counter()
            for line in scored['line_order']:
                a, b = ref.lines.get(line, []), pred.lines.get(line, [])
                for kind, i, j in alignment(a, b):
                    counts[kind] += 1
                    if kind == 'match' and a[i].duration != b[j].duration:
                        counts['same_pitch_duration_mismatch'] += 1
                        duration_pairs.append({'dataset': dataset, 'id': sid, 'title': row['title'],
                            'line': line, 'reference_index': i, 'prediction_index': j,
                            'pitch': a[i].pitch, 'reference_onset': str(a[i].onset),
                            'prediction_onset': str(b[j].onset),
                            'reference_duration': str(a[i].duration), 'prediction_duration': str(b[j].duration)})
                        counts[f'duration_{a[i].duration}_to_{b[j].duration}'] += 1
                    if kind == 'substitute':
                        counts[f'pitch_delta_{b[j].pitch-a[i].pitch:+d}'] += 1
            totals = scored['totals']
            counts.update({k: totals[k] for k in ('reference_notes', 'prediction_notes',
                                                  'pitch_edit_distance', 'pitch_duration_edit_distance')})
            deficit = totals['reference_notes'] - totals['prediction_notes']
            counts['net_note_deficit'] = deficit
            groups[dataset].update(counts)
            groups[dataset]['songs'] += 1
            groups[dataset]['songs_with_note_deficit'] += deficit > 0
            groups[dataset]['songs_with_same_pitch_duration_mismatch'] += counts['same_pitch_duration_mismatch'] > 0
            songs.append({'dataset': dataset, 'id': sid, 'title': row['title'],
                'counts': dict(counts), 'fallback': record.get('fallback_policy', row.get('fallback_policy')),
                'structure': {'reference_parts': len(ref.summaries), 'output_parts': len(pred.summaries),
                    'staves': len(trace['staves']), 'systems': len(trace['systems']),
                    'expected_staves': meta['expected_staves'], 'expected_systems': meta['expected_systems']},
                'trace': str(trace_path.relative_to(ROOT)), 'prediction': str(pred_path.relative_to(ROOT))})

    cases = []
    for case in audit['cases']:
        trace = traces[case['song_id']]
        sp = trace['staves'][case['staff']]['sp']
        nearby = [s for s in trace['syms'] if s['staff'] == case['staff']
                  and s['cls'].split('_')[0] in ('note', 'rest') and near_head(case['box'], s['box'], sp)]
        ids = {s['i'] for s in nearby}
        emitted = [e for e in trace['writer']['emitted'] if e['e.si'] in ids]
        accepted = [s['i'] for s in nearby if trace['tokens'].get(str(s['i']), {}).get('real', {}).get('p', 0) >= .5
                    and trace['tokens'][str(s['i'])]['cls']['v'].startswith('note_')]
        notes = [s['i'] for s in nearby if trace['tokens'].get(str(s['i']), {}).get('cls', {}).get('v', '').startswith('note_')]
        status = ('note_emitted' if any(e['kind'] == 'note' for e in emitted) else
                  'accepted_note_not_emitted' if accepted else
                  'note_proposal_not_admitted' if notes else 'no_note_token_at_reviewed_head')
        cases.append({'case_id': case['case_id'], 'id': case['song_id'], 'title': case['title'],
            'shape': case['shape'], 'part': case['part'], 'status': status,
            'note_token_ids': notes, 'accepted_note_ids': accepted, 'emitted': emitted,
            'emitted_rest_at_head': any(e['kind'] == 'rest' for e in emitted),
            'nearby_symbols': [{'id': s['i'], 'class': trace['tokens'].get(str(s['i']), {}).get('cls', {}).get('v'),
                'p': trace['tokens'].get(str(s['i']), {}).get('real', {}).get('p'),
                'verification': trace.get('image_verifications', {}).get(str(s['i']))} for s in nearby],
            'source_image': f"diagnostics/miss-trace/{case['evidence_image']}"})
    status = Counter(c['status'] for c in cases)
    rest = Counter(c['status'] for c in cases if c['emitted_rest_at_head'] and c['status'] != 'note_emitted')
    accepted_songs = {c['id'] for c in cases if c['status'] == 'accepted_note_not_emitted'}
    replay = [replay_final_clipping(row, metadata[row['id']], traces[row['id']], cases)
              for row in songs if row['id'] in accepted_songs]
    masks = [mask_diagnostic(c, metadata[c['song_id']], traces[c['song_id']])
             for c in audit['cases'] if c['case_id'] in ('M004', 'M011', 'M015')]
    sources.update(ROOT/metadata[sid]['input'] for sid in {c['song_id'] for c in audit['cases']})
    code = [ROOT/n for n in ('audit_common_errors.py', 'compare_musicxml.py', 'run_reader_v2.py',
        'bar_fitting.py', 'reader_policy.py', 'glyph_verifier.py', 'replay_writer_trace.py')]
    code += [ROOT.parent.parent/'copisteria/src/copisteria/write.py']
    provenance = {str(p.relative_to(ROOT.parent.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(sources | set(code))}
    output = {'method': 'Saved final XML, conventional vocal order, pitch-only minimum-edit alignment',
        'limitations': ['1911 source versus 2025 reference: disagreements include edition changes.',
            'Alignment ties can change individual categories; duration mismatches use a pitch-only alignment.',
            'Layout failures remain in aggregates.', 'The 95 reviewed heads are a purposeful five-song sample.',
            'Not emitted does not establish clipping; duplicate or alternative proposals may be intentionally suppressed.',
            'The prior independent20 are now inspected for diagnosis; future tuning requires new unused validation.'],
        'groups': dict(groups), 'songs': songs, 'duration_pairs': duration_pairs,
        'reviewed_head_status': dict(status), 'reviewed_head_emitted_rests': dict(rest),
        'exact_replays': replay, 'head_mask_diagnostics': masks,
        'reviewed_heads': cases, 'sha256': provenance}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'inventory.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({
        'groups': {k: {n: v[n] for n in ('songs', 'reference_notes', 'prediction_notes',
            'pitch_edit_distance', 'pitch_duration_edit_distance', 'same_pitch_duration_mismatch',
            'songs_with_same_pitch_duration_mismatch')} for k,v in groups.items()},
        'reviewed_head_status': dict(status), 'reviewed_head_emitted_rests': dict(rest),
        'final_clipping_reviewed_heads': {r['title']: r['final_clipping_reviewed_heads'] for r in replay},
        'part_count_discrepancies': [s['title'] for s in songs
            if s['structure']['reference_parts'] != s['structure']['output_parts']]}, indent=2))


if __name__ == '__main__':
    main()
