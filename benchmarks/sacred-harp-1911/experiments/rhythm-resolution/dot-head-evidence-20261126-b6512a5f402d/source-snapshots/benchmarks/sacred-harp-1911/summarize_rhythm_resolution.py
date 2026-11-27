"""Validate and summarize a completed source rhythm resolution run."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from audit_bar_meter import xml_inventory
from run_local_recovery import ROOT, read, save, sha, samples
from run_rhythm_resolution import PREVIOUS
from run_proposal_rhythm_recovery import PROPOSALS
from source_saved_events import source_saved_events
from false_head_evidence import proven_non_head


def event_pitch_set(trace):
    return {(int(e['e.si']), e['step'], int(e['octave']), int(e['alter']))
            for e in trace['writer']['emitted'] if e['kind'] == 'note'}


def note_annotations(trace, xml):
    events, _ = source_saved_events(trace, xml)
    return {(int(e.si), e.step, int(e.octave), int(e.alter), e.accidental,
             tuple(sorted(e.marks)), bool(e.arpeggiate))
            for rows in events.values() for e in rows if e.kind == 'note'}


def unresolved_counts(trace):
    columns = trace.get('source_bar_fit_decisions', [])
    unresolved_columns = sum(not bool(c.get('resolved')) for c in columns)
    voice_decisions = sum(len(c.get('unresolved', [])) for c in columns)
    return unresolved_columns, voice_decisions, len(columns)


def selected_cut_map(trace):
    result = {}
    for bar in trace.get('final_timing', {}).get('bars', []):
        key = (int(bar['part']), str(bar['bar']))
        cut = str(Fraction(str(bar['selected_cut'])))
        if key in result:
            assert result[key] == cut, ('part-measure has conflicting selected cuts', key)
        result[key] = cut
    return result


def check_spans(xml, trace):
    inventory = xml_inventory(xml)
    timing = trace.get('final_timing', {})
    cuts = [str(Fraction(str(x))) for x in timing.get('selected_cuts', [])]
    assert cuts, 'missing common selected cuts'
    rows = inventory['measures']
    mismatches = []
    for row in rows:
        measure_no = int(row['measure'])
        key = (int(row['part']), str(measure_no))
        encoded = str(Fraction(row['encoded_span_quarters']))
        selected = cuts[measure_no-1] if 1 <= measure_no <= len(cuts) else None
        if selected is None or encoded != selected:
            mismatches.append({'part': key[0], 'measure': key[1],
                               'encoded_span': encoded, 'selected_cut': selected})
    assert not mismatches, ('encoded part-measure spans differ from selected cuts', mismatches[:10])
    # Bars with source events also carry an explicit per-bar selected cut.
    explicit = selected_cut_map(trace)
    for (part, measure), cut in explicit.items():
        if 1 <= int(measure) <= len(cuts):
            assert cut == cuts[int(measure)-1], ('bar cut differs from shared selected cut', part, measure)
    return inventory


def measure_metric(row, comparison_key):
    comp = row[comparison_key]
    totals = comp['totals']
    return {
        'pitch_duration_edit_distance': totals['pitch_duration_edit_distance'],
        'pitch_duration_rate_denominator': totals['pitch_duration_rate_denominator'],
        'time_aware': comp['time_aware_exact_event_multiset'],
    }


def aggregate(rows, keys):
    out = defaultdict(lambda: {'songs': 0, 'pd': 0, 'pd_denominator': 0,
                               'matches': 0, 'prediction_notes': 0, 'reference_notes': 0})
    for row in rows:
        dst = out[row['dataset']]
        for key, metric_key in keys.items():
            metric = measure_metric(row, key)
            dst['songs'] += 1 if key == next(iter(keys)) else 0
            dst['pd'] += metric['pitch_duration_edit_distance']
            dst['pd_denominator'] += metric['pitch_duration_rate_denominator']
            ta = metric['time_aware']
            dst['matches'] += ta['matches']
            dst['prediction_notes'] += row[key]['totals']['prediction_notes']
            dst['reference_notes'] += row[key]['totals']['reference_notes']
    for dst in out.values():
        p = dst['matches'] / dst['prediction_notes'] if dst['prediction_notes'] else 0
        r = dst['matches'] / dst['reference_notes'] if dst['reference_notes'] else 0
        dst['time_aware_precision'] = p
        dst['time_aware_recall'] = r
        dst['time_aware_f1'] = 2*p*r/(p+r) if p+r else 0
    return dict(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment', type=Path)
    args = parser.parse_args()
    out = args.experiment.resolve()
    data = read(out/'results.json')
    complete = read(out/'predictions-complete.json')
    rows = data['samples']
    expected = complete['ids']
    assert [r['id'] for r in rows] == expected
    assert len(set(expected)) == len(expected)
    assert all(r['experiment_key'] == data['experiment_key'] == complete['experiment_key'] for r in rows)
    assert complete.get('references_opened_during_generation') is False
    assert complete.get('generation_code_unchanged_through_complete_batch') is True
    assert sha(out/'source-meter-templates.npz') == complete['source_meter_templates_sha256']

    # Verify the frozen generation inputs and source code snapshot hashes.
    verified = {}
    for name, digest in data['provenance'].items():
        path = ROOT.parents[1]/name
        if name.endswith('.py'):
            path = out/'source-snapshots'/name
        assert path.exists() and sha(path) == digest, ('provenance hash', name)
        verified[name] = digest
    sample_map = {s['id']: s for s in samples()}
    metrics = []
    unresolved = []
    removed_duplicate_occurrences = 0
    removed_mixed_conflicts = 0
    removed_non_heads = []
    for row in rows:
        sid = row['id']
        prediction = ROOT/row['prediction']
        trace_path = prediction.with_suffix('.trace.json')
        assert sha(prediction) == row['sha256']
        assert sha(trace_path) == row['trace_sha256']
        trace = read(trace_path)
        previous_xml_path = PREVIOUS/'predictions'/f'{sid}.musicxml'
        previous_trace_path = previous_xml_path.with_suffix('.trace.json')
        previous_trace = read(previous_trace_path)
        previous_xml = previous_xml_path.read_text()
        current_xml = prediction.read_text()
        removed=trace.get('rhythm_resolution_details',{}).get('duplicate_serialized_events_removed',[])
        non_heads={int(x['sym_id']) for x in removed if proven_non_head(x)}
        removed_non_heads += [{'id':sid,'title':row['title'],**x} for x in removed if int(x['sym_id']) in non_heads]

        # Physical notes are compared by source ID and pitch, not serialized multiplicity.
        missing = {p for p in event_pitch_set(previous_trace) - event_pitch_set(trace) if p[0] not in non_heads}
        assert not missing, (sid, 'pitched source ID/pitch removed or changed', sorted(missing)[:20])
        old_annotations = {x for x in note_annotations(previous_trace, previous_xml) if x[0] not in non_heads}
        new_annotations = note_annotations(trace, current_xml)
        assert old_annotations <= new_annotations, (sid, 'source note mark/accidental lost',
                                                    sorted(old_annotations-new_annotations)[:20])
        old_syms = {int(x['i']): x for x in previous_trace.get('syms', []) if x.get('cls') != 'measure'}
        new_syms = {int(x['i']): x for x in trace.get('syms', []) if x.get('cls') != 'measure'}
        assert old_syms.keys() <= new_syms.keys(), (sid, 'source geometry symbols missing')
        for i, old in old_syms.items():
            new = new_syms[i]
            assert (old['box'], old['staff']) == (new['box'], new['staff']), (sid, i)

        # Parse and compare normalized XML durations with final emitted trace events.
        root = ET.fromstring(current_xml)
        emitted = [e for e in trace['writer']['emitted'] if e['kind'] in ('note', 'rest', 'mrest')]
        xml_durations = []
        divisions = 1
        for part in root.findall('part'):
            for measure in part.findall('measure'):
                for node in measure:
                    if node.tag == 'attributes':
                        divisions = int(node.findtext('divisions', str(divisions)))
                    elif node.tag == 'note' and node.get('print-object') != 'no':
                        xml_durations.append(Fraction(int(node.findtext('duration', '0')), divisions))
        trace_durations = [Fraction(str(e['e.dur'])) for e in emitted]
        # Source-linked helper also verifies event ordering/kind and duration equality.
        source_saved_events(trace, current_xml)
        assert xml_durations == trace_durations, (sid, 'normalized XML/trace durations differ')

        inventory = check_spans(current_xml, trace)
        timing_bars = trace.get('final_timing', {}).get('bars', [])
        prior_ids = {si for si, *_ in event_pitch_set(previous_trace)}
        clipped = []
        for b in timing_bars:
            removed = set(map(int, b.get('clipped_event_ids', []))) | set(map(int, b.get('dropped_head_ids', [])))
            shortened = {int(x.get('source_id', x.get('si', -1))) for x in b.get('shortened_events', [])
                         if isinstance(x, dict)}
            if (removed | shortened) & prior_ids:
                clipped.append(b)
        assert not clipped, (sid, 'clipped/dropped/shortened timing events', clipped[:3])

        columns, voices, total_columns = unresolved_counts(trace)
        unresolved.append({'id': sid, 'title': row['title'], 'columns': total_columns,
                           'unresolved_columns': columns, 'unresolved_voice_decisions': voices})
        detail = trace.get('rhythm_resolution_details', {})
        removed = detail.get('duplicate_serialized_events_removed', [])
        removed_duplicate_occurrences += sum(
            x.get('reason') == 'duplicate_serialized_occurrence_of_same_physical_head' for x in removed)
        removed_mixed_conflicts += sum(
            x.get('reason') == 'same_physical_head_already_emitted_as_note' for x in removed)
        # This run carries both prior stages explicitly for apples-to-apples comparison.
        metric = {'id': sid, 'title': row['title'], 'dataset': row['dataset']}
        for key, label in (('baseline_comparison', 'previous'),
                           ('proposal_comparison', 'proposal_baseline'),
                           ('comparison', 'current')):
            metric[label] = measure_metric(row, key)
        metrics.append(metric)

    # Preserve the established 18 physical-head / 17 source-duration checks.
    source_review = read(PROPOSALS/'source-review.json')['cases']
    reviewed = []
    by_id = {r['id']: r for r in rows}
    for case in source_review:
        sid = case['song_id']
        if sid not in by_id:
            continue
        trace = read((ROOT/by_id[sid]['prediction']).with_suffix('.trace.json'))
        events = [e for e in trace['writer']['emitted']
                  if e['kind'] == 'note' and int(e['e.si']) == int(case['proposal_id'])]
        assert events, (sid, case['case_id'], 'source-reviewed physical note missing')
        expected = case.get('source_expected_duration_quarters')
        matches = (all(Fraction(str(e['e.dur'])) == Fraction(str(expected)) for e in events)
                   if expected is not None else None)
        reviewed.append({'case_id': case['case_id'], 'song_id': sid,
                         'proposal_id': case['proposal_id'], 'events': events,
                         'emitted_duration_matches_source': matches})
    checked = sum(x['emitted_duration_matches_source'] is not None for x in reviewed)
    matched = sum(x['emitted_duration_matches_source'] is True for x in reviewed)
    assert len(reviewed) == 18, ('source review physical heads', len(reviewed))
    assert checked == 17 and matched == 17, ('source review duration checks', checked, matched)

    aggregates = {label: aggregate(rows, {key: label}) for key, label in (
        ('baseline_comparison', 'previous'), ('proposal_comparison', 'proposal_baseline'),
        ('comparison', 'current'))}
    regressions = []
    for metric in metrics:
        cur = metric['current']
        for baseline_name in ('previous', 'proposal_baseline'):
            old = metric[baseline_name]
            if (cur['pitch_duration_edit_distance'] > old['pitch_duration_edit_distance'] or
                    cur['time_aware']['f1'] < old['time_aware']['f1']):
                regressions.append({'id': metric['id'], 'title': metric['title'],
                                    'baseline': baseline_name,
                                    'pd_change': cur['pitch_duration_edit_distance']-old['pitch_duration_edit_distance'],
                                    'time_aware_f1_change': cur['time_aware']['f1']-old['time_aware']['f1']})

    validation = {
        'experiment_key': data['experiment_key'], 'songs': len(rows),
        'checks': {'complete_ids_and_hashes': True, 'source_code_and_input_provenance': True,
                   'generation_code_unchanged_through_complete_batch': True,
                   'source_meter_template_hash': True, 'prior_note_id_pitch_sets_retained_except_proven_non_heads': True,
                   'source_geometry_and_staff_stable': True, 'xml_normalized_durations_match_trace': True,
                   'source_note_annotations_retained_ignoring_multiplicity': True,
                   'all_part_measure_spans_equal_selected_cuts': True,
                   'no_clipped_dropped_or_shortened_events': True},
        'verified_provenance': verified, 'aggregates': aggregates,
        'per_song': metrics, 'regressions_vs_previous_or_proposal_baseline': regressions,
        'unresolved_columns_and_voice_decisions': unresolved,
        'removed_serialized_duplicate_occurrences': removed_duplicate_occurrences,
        'removed_mixed_note_rest_same_head_conflicts': removed_mixed_conflicts,
        'source_non_head_notes_removed':removed_non_heads,
        'source_review_18_heads_17_durations': {'heads': len(reviewed), 'duration_checks': checked,
                                                'duration_matches': matched, 'cases': reviewed},
    }
    save(out/'validation.json', validation)

    lines = ['# Rhythm resolution validation', '',
             f"Validated **{len(rows)} songs**. Prior note IDs and pitches are retained except {len(removed_non_heads)} source-supported non-head removals. Source geometry/staff, normalized durations, retained note annotations, and selected part-measure spans passed. No retained physical notes were clipped or dropped.", '',
             '| Dataset | Stage | Songs | PD edit distance | Time aware F1 |',
             '|---|---|---:|---:|---:|']
    for dataset in sorted(aggregates['current']):
        for stage in ('previous', 'proposal_baseline', 'current'):
            a = aggregates[stage][dataset]
            lines.append(f"| {dataset} | {stage} | {a['songs']} | {a['pd']} | {a['time_aware_f1']:.3f} |")
    lines += ['', 'PD is pitch-duration edit distance; lower is better. Time aware F1 uses the exact event multiset. Per-song regressions against either comparison stage are listed in `validation.json`.', '',
              f"Unresolved timing is reported separately: **{sum(x['unresolved_columns'] for x in unresolved)} shared columns** and **{sum(x['unresolved_voice_decisions'] for x in unresolved)} voice decisions**. Removed serialized duplicate occurrences: **{removed_duplicate_occurrences}**; removed mixed note/rest same-head conflicts: **{removed_mixed_conflicts}**.", '',
              f"The established source review retains **{len(reviewed)} of 18 physical notes** and matches **{matched} of 17 checkable source durations**.", '',
              '## Regressions', '']
    if regressions:
        for item in regressions:
            lines.append(f"- {item['title']} (`{item['id']}`) vs {item['baseline']}: PD {item['pd_change']:+d}; time-aware F1 {item['time_aware_f1_change']:+.3f}.")
    else:
        lines.append('No per-song PD or time-aware F1 regression against either comparison stage.')
    lines += ['',
              'All 120 songs are development/diagnostic examples. Scores measure disagreement with a different edition, rather than recognition accuracy. This stage remains opt-in; defaults and gallery are unchanged.', '',
              '**Recommended:** inspect the per-song regressions and unresolved voice decisions before expanding the run.',
              '**Alternative:** retain this as a bounded opt-in stage and collect additional source-reviewed cases.', '',
              '[Validation details](validation.json); [run results](results.json).', '']
    (out/'REPORT.md').write_text('\n'.join(lines))
    artifact_hashes = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*'))
                       if p.is_file() and p.name != 'artifact-sha256.json'
                       and 'source-snapshots' not in p.parts}
    save(out/'artifact-sha256.json', artifact_hashes)
    print(json.dumps({'songs': len(rows), 'unresolved_columns': sum(x['unresolved_columns'] for x in unresolved),
                      'unresolved_voice_decisions': sum(x['unresolved_voice_decisions'] for x in unresolved),
                      'regressions': len(regressions), 'duplicate_occurrences_removed': removed_duplicate_occurrences,
                      'mixed_conflicts_removed': removed_mixed_conflicts}, indent=2))


if __name__ == '__main__':
    main()
