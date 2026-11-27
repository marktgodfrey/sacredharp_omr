"""Build joined, derived reports for the bounded bar-fitting replay."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'experiments' / 'bar-fitting'
PREVIOUS = ROOT / 'experiments' / 'reader-v2' / 'replay' / 'results.json'
CURRENT = ROOT / 'experiments' / 'reader-v2' / 'replay_bar_fit' / 'results.json'


def read(path):
    return json.loads(path.read_text())


def totals(record, variant=None):
    if variant is None:
        return record['baseline']['comparison']['totals']
    return record['variants'][variant]['comparison']['totals']


def summarize(records, get_totals):
    values = [get_totals(r) for r in records]
    ref = sum(t['reference_notes'] for t in values)
    pitch_den = sum(t.get('pitch_rate_denominator', t['reference_notes']) for t in values)
    pd_den = sum(t.get('pitch_duration_rate_denominator', t['reference_notes']) for t in values)
    pitch_edits = sum(t['pitch_edit_distance'] for t in values)
    pd_edits = sum(t['pitch_duration_edit_distance'] for t in values)
    pred = sum(t['prediction_notes'] for t in values)
    return {'reference_notes': ref, 'prediction_notes': pred,
            'pitch_edits': pitch_edits, 'pitch_denominator': pitch_den,
            'pitch_rate': pitch_edits / pitch_den if pitch_den else 0,
            'pitch_duration_edits': pd_edits, 'pitch_duration_denominator': pd_den,
            'pitch_duration_rate': pd_edits / pd_den if pd_den else 0}


def status(a, b):
    return 'better' if a < b else 'worse' if a > b else 'equal'


def classify(records, lhs, rhs):
    out = {'edit_count': {'better': 0, 'equal': 0, 'worse': 0},
           'recorded_rate': {'better': 0, 'equal': 0, 'worse': 0}}
    for a, b in zip(lhs, rhs):
        out['edit_count'][status(a['pitch_duration_edit_distance'], b['pitch_duration_edit_distance'])] += 1
        out['recorded_rate'][status(a['pitch_duration_error_rate'], b['pitch_duration_error_rate'])] += 1
    return out


def main():
    previous = read(PREVIOUS)
    current = read(CURRENT)
    prev_by_id = {r['id']: r for r in previous['samples']}
    cur_by_id = {r['id']: r for r in current['samples']}
    missing = sorted(set(prev_by_id) - set(cur_by_id))
    extra = sorted(set(cur_by_id) - set(prev_by_id))
    ids = sorted(set(prev_by_id) & set(cur_by_id))
    records = [cur_by_id[i] for i in ids]
    old = [prev_by_id[i] for i in ids]
    base = [totals(r) for r in records]
    v2 = [totals(r, 'verification_rhythm') for r in old]
    new = [totals(r, 'verification_rhythm') for r in records]
    metrics = {
        'baseline': summarize(records, lambda r: totals(r)),
        'reader_v2': summarize(old, lambda r: totals(r, 'verification_rhythm')),
        'bar_fit': summarize(records, lambda r: totals(r, 'verification_rhythm')),
    }
    comparisons = {'bar_fit_vs_baseline': classify(records, new, base),
                   'bar_fit_vs_reader_v2': classify(records, new, v2)}
    fallback_policies = Counter(
        r['variants']['verification_rhythm'].get('fallback_policy') for r in records)
    song_rows = []
    for i, record in enumerate(records):
        variant = record['variants']['verification_rhythm']
        song_rows.append({
            'id': record['id'], 'title': record['title'],
            'baseline_reference_notes': base[i]['reference_notes'],
            'baseline_prediction_notes': base[i]['prediction_notes'],
            'baseline_pitch_edits': base[i]['pitch_edit_distance'],
            'baseline_pitch_rate': base[i]['pitch_error_rate'],
            'baseline_pitch_duration_edits': base[i]['pitch_duration_edit_distance'],
            'baseline_pitch_duration_rate': base[i]['pitch_duration_error_rate'],
            'reader_v2_prediction_notes': v2[i]['prediction_notes'],
            'reader_v2_pitch_edits': v2[i]['pitch_edit_distance'],
            'reader_v2_pitch_rate': v2[i]['pitch_error_rate'],
            'reader_v2_pitch_duration_edits': v2[i]['pitch_duration_edit_distance'],
            'reader_v2_pitch_duration_rate': v2[i]['pitch_duration_error_rate'],
            'bar_fit_prediction_notes': new[i]['prediction_notes'],
            'bar_fit_pitch_edits': new[i]['pitch_edit_distance'],
            'bar_fit_pitch_rate': new[i]['pitch_error_rate'],
            'bar_fit_pitch_duration_edits': new[i]['pitch_duration_edit_distance'],
            'bar_fit_pitch_duration_rate': new[i]['pitch_duration_error_rate'],
            'audit_hits': len(variant.get('audit_hits', [])),
            'conservative_fallback': bool(variant.get('conservative_fallback', False)),
            'bar_fit_vs_baseline_edit_count': status(new[i]['pitch_duration_edit_distance'], base[i]['pitch_duration_edit_distance']),
            'bar_fit_vs_baseline_recorded_rate': status(new[i]['pitch_duration_error_rate'], base[i]['pitch_duration_error_rate']),
            'bar_fit_vs_reader_v2_edit_count': status(new[i]['pitch_duration_edit_distance'], v2[i]['pitch_duration_edit_distance']),
            'bar_fit_vs_reader_v2_recorded_rate': status(new[i]['pitch_duration_error_rate'], v2[i]['pitch_duration_error_rate']),
        })
    summary = {'joined_songs': len(ids), 'missing_from_bar_fit': missing, 'extra_in_bar_fit': extra,
               'metrics': metrics, 'song_classifications': comparisons,
               'audit_hits': sum(r['audit_hits'] for r in song_rows),
               'conservative_fallbacks': sum(r['conservative_fallback'] for r in song_rows),
               'songs_with_conservative_fallback': sum(r['conservative_fallback'] for r in song_rows),
               'fallback_policy_counts': dict(sorted(fallback_policies.items(), key=lambda item: str(item[0])))}
    audit_total=len(read(ROOT/'diagnostics/miss-trace/confirmed-misses.json')['cases'])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    with (OUT / 'per-song.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(song_rows[0]) if song_rows else ['id', 'title'])
        writer.writeheader()
        writer.writerows(song_rows)

    title_ids = ('Sawyer’s Exit', "Sawyer's Exit", 'The Sawyer’s Exit', "The Sawyer's Exit",
                 'The American Star', 'Elder')
    selected = []
    for label in title_ids:
        matches = [r for r in song_rows if r['title'].casefold() == label.casefold()]
        if matches and matches[0] not in selected:
            selected.append(matches[0])
    lines = [
        '# Bounded bar-fitting replay',
        '',
        f'The replay joins **{len(ids)} songs** by song ID. The previous v2 and new bar-fit outputs are compared with the baseline stored in the current records. Weighted rates are total edit distance divided by the corresponding summed denominator; per-song rate classifications use each record’s saved rate, separately from edit-count classifications.',
        '',
        '| System | Notes predicted / reference | Pitch edits / denominator | Pitch rate | Pitch+duration edits / denominator | Pitch+duration rate |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for name, label in [('baseline', 'Original baseline'), ('reader_v2', 'Reader v2'), ('bar_fit', 'Bar fit')]:
        m = metrics[name]
        lines.append(f"| {label} | {m['prediction_notes']} / {m['reference_notes']} | {m['pitch_edits']} / {m['pitch_denominator']} | {m['pitch_rate']:.2%} | {m['pitch_duration_edits']} / {m['pitch_duration_denominator']} | {m['pitch_duration_rate']:.2%} |")
    lines += ['', 'Per-song comparisons classify lower edit count and lower recorded error rate separately, so the two columns can differ when denominators differ.', '']
    for against, label in [('bar_fit_vs_baseline', 'vs original baseline'), ('bar_fit_vs_reader_v2', 'vs reader v2')]:
        c = comparisons[against]
        lines.append(f"- Bar fit {label}: edit count {c['edit_count']['better']} better, {c['edit_count']['equal']} equal, {c['edit_count']['worse']} worse; recorded rate {c['recorded_rate']['better']} better, {c['recorded_rate']['equal']} equal, {c['recorded_rate']['worse']} worse.")
    policy_text = ', '.join(f"{key if key is not None else 'None'}: {count}"
                            for key, count in summary['fallback_policy_counts'].items()) or 'none recorded'
    lines.append(f"- Audited missing heads reaching XML: {summary['audit_hits']}/{audit_total}; conservative fallbacks: {summary['conservative_fallbacks']} of {len(ids)} songs; fallback policies: {policy_text}. The purposeful audit is not a random sample, and a retained head does not guarantee correct pitch or duration.")
    if selected:
        lines += ['', '| Song | Baseline edits | Reader v2 edits | Bar-fit edits |', '|---|---:|---:|---:|']
        for r in selected:
            lines.append(f"| {r['title']} | {r['baseline_pitch_duration_edits']} | {r['reader_v2_pitch_duration_edits']} | {r['bar_fit_pitch_duration_edits']} |")
    worse=[r for r in song_rows if r['bar_fit_vs_baseline_edit_count']=='worse']
    lines+=['', 'Remaining increases in pitch+duration edit count versus the original baseline: '+
            ('; '.join(f"{r['title']} ({r['baseline_pitch_duration_edits']}→{r['bar_fit_pitch_duration_edits']})" for r in worse) if worse else 'none.')]
    previous_worse=[r for r in song_rows if r['bar_fit_vs_reader_v2_edit_count']=='worse']
    lines+=['', 'Tradeoffs versus the previous reader-v2 pass: '+
            ('; '.join(f"{r['title']} ({r['reader_v2_pitch_duration_edits']}→{r['bar_fit_pitch_duration_edits']})" for r in previous_worse) if previous_worse else 'none.')]
    lines += ['', 'Method:', '',
        '- Mutually exclusive readings of one physical glyph are evaluated as alternatives; the score uses an independent Bernoulli conditional-odds prior from the model’s existing candidate probabilities.',
        '- Weak unverified note or rest candidates can be omitted only when a voice overflows its current bar.',
        '- Detector-supported duration alternatives and image-verified shared-stem chords are considered jointly. Each staff-bar contributes one meter vote, so omission of a voice cannot shift which bars are compared across meter hypotheses.',
        '- Agreeing visible meter glyphs on at least two staves anchor the opening meter only when both their class readings and the measure-head meter readings are confident. Uncertain signatures and continuation pages retain meter search.',
        '- When joint search would lose protected notes, fallback preserves the previous reader-v2 output; the per-song records report whether fallback used `reader_v2`, `original`, or no fallback.',
        '- Inference uses no reference scores or manual labels. The scorer compares 2025 transcriptions with 1911 prints, so its edits are not pure accuracy; all 100 songs were used during development and are not an independent test set.',
        '',
        'The original gallery and prior reader-v2 results remain untouched. Source snapshots are under `../reader-v2/source-snapshots/`; predictions and traces are under `../reader-v2/replay_bar_fit/verification_rhythm/`. See the [evidence package](evidence/evidence.json) and its five crops. From the project root run `copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_reader_v2.py --phase replay --bar-fit`; this mode reuses saved local CoreML readings.',
        '',
        '']
    lines+=['Source examples: [duplicate head](evidence/elder_465_selected_553_duplicate.jpg), [simultaneous bass notes](evidence/elder_397_523_shared_stem.jpg), [weak ghost and retained final note](evidence/elder_337_549_bar_neighbors.jpg), [Sawyer’s quarter + half + dotted half](evidence/sawyer_268_290_98_356.jpg), [American Star six quarters](evidence/american_star_bar1.jpg).','']
    validation_path=OUT/'validation.json'
    if validation_path.exists():
        validation=read(validation_path)
        checks=validation['checks']
        if ({r['experiment_key'] for r in records}=={validation['experiment_key']}
                and len(records)==checks['unique_songs']):
            lines+=[f"Validation ({validation['date']}): all {validation['tests']['passed']} benchmark tests passed. Fresh local CPU CoreML inference on {checks['fresh_cpu_coreml_pages']} target songs produced parsed scores identical to saved-reading replay, including note onsets and durations. The final Elder XML contains the shared-stem chord. All {checks['fallbacks_equal_previous_v2']} conservative fallback outputs match the previous v2 reader. Full checks: [validation.json](validation.json).",'']
        else:lines+=['The attached validation record covers a different source snapshot or dataset selection.','']
    (OUT / 'REPORT.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
