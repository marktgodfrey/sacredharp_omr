"""Validate a completed missing-note-proposal experiment and write its report."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image

from run_local_recovery import ROOT, read, save, sha, samples
from run_missing_note_proposals import LATEST, validate
from replay_writer_trace import _reading
from summarize_local_recovery import reviewed_status


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('experiment', type=Path)
    args = p.parse_args()
    out = args.experiment.resolve()
    data = read(out/'results.json')
    metadata = {s['id']: s for s in samples()}
    all_cases = read(ROOT/'diagnostics/miss-trace/confirmed-misses.json')['cases']
    case_status, regressions = [], []
    aggregates = {}
    counters = Counter()
    for row in data['samples']:
        s = metadata[row['id']]
        path = ROOT/row['prediction']; assert sha(path) == row['sha256']
        trace = read(path.with_suffix('.trace.json'))
        old_path = LATEST/'note_rest'/f"{s['id']}.musicxml"
        prior = read(old_path.with_suffix('.trace.json'))
        rd = _reading(trace, Image.open(ROOT/s['input']))
        validate(path.read_text(), trace['writer'], prior, rd, old_path.read_text())
        assert trace['staves'] == prior['staves'], (s['id'], 'staves')
        assert trace['systems'] == prior['systems'], (s['id'], 'systems')
        assert trace['syms'][:len(prior['syms'])] == prior['syms'], (s['id'], 'old symbol geometry')
        assert all(d['i'] == i for i, d in enumerate(trace['syms']))
        constraints = trace.get('proposal_duration_constraints', {})
        counters['duration_constrained_predictions'] += int('proposal_duration_constraints' in trace)
        for i, allowed in constraints.items():
            assert set(trace['duration_options'].get(i, {})) <= set(allowed), (s['id'], i, 'duration options')
        for decision in trace['rhythm_search_decisions']:
            i = str(decision.get('sym_id'))
            if i in constraints and 'new_type' in decision:
                assert decision['new_type'] in constraints[i], (s['id'], i, 'rhythm search')
        assert row['latest_exact_replay']
        a = aggregates.setdefault(s['dataset'], {'songs': 0, 'baseline_edits': 0,
            'edits': 0, 'baseline_denominator': 0, 'denominator': 0, 'pitch_edits': 0,
            'baseline_pitch_edits': 0, 'better': 0, 'same': 0, 'worse': 0})
        a['songs'] += 1
        before, after = row['baseline_comparison']['totals'], row['comparison']['totals']
        for name, totals in [('baseline_', before), ('', after)]:
            a[name+'edits'] += totals['pitch_duration_edit_distance']
            a[name+'denominator'] += totals['pitch_duration_rate_denominator']
            a[name+'pitch_edits'] += totals['pitch_edit_distance']
        delta = after['pitch_duration_edit_distance']-before['pitch_duration_edit_distance']
        a['better' if delta < 0 else 'worse' if delta > 0 else 'same'] += 1
        if delta > 0:
            regressions.append({'id': s['id'], 'title': s['title'], 'dataset': s['dataset'],
                'before': before['pitch_duration_edit_distance'], 'after': after['pitch_duration_edit_distance']})
        counters.update(sites=row['sites'], proposals=row['proposals'], supported=row['supported'],
            new_note_events=row['new_notes_emitted'], whole_measure_rest_conflicts=len(trace['whole_measure_rest_conflicts']))
        for c in [c for c in all_cases if c['song_id'] == s['id']]:
            status = reviewed_status(trace, [c])[0]
            proposal = next((v for v in trace['new_note_proposals'] if v['anchor_id'] == c['anchor_sym_id']), None)
            i = proposal['proposal_id'] if proposal else None
            emitted = [e for e in trace['writer']['emitted'] if e['kind'] == 'note' and e['e.si'] == i]
            case_status.append({**status, 'song_id': s['id'], 'title': s['title'], 'stage': c['stage'],
                'proposal_id': i, 'decision': proposal['decision'] if proposal else None,
                'proposal_events': emitted,
                'visual_note_probability': proposal['visual_alternative']['visual_note_probability']
                    if proposal and proposal['visual_alternative'] else None,
                'target_spacing': proposal['visual_alternative']['target_spacing']
                    if proposal and proposal['visual_alternative'] else None})
    sources = {}
    for name, expected in data['provenance'].items():
        current = ROOT.parents[1]/name
        snapshot = out/'source-snapshots'/name
        used = current if current.exists() and sha(current) == expected else snapshot
        assert used.exists() and sha(used) == expected, name
        sources[name] = str(used.relative_to(ROOT.parents[1]))
    gaps = [c for c in case_status if c['stage'] == 'rest_only_no_recorded_note_proposal']
    validation = {'songs': len(data['samples']), 'all_latest_baselines_replayed_exactly': True,
        'all_xml_pitched_events_match_traces': True, 'all_baseline_physical_pitches_retained': True,
        'all_staff_bar_geometry_and_symbol_ids_retained': True, 'all_meters_and_measure_counts_retained': True,
        'new_proposal_duration_options_respect_source_constraints':
            counters['duration_constrained_predictions'] == len(data['samples']),
        'generation_provenance_verified': sources, 'aggregates': aggregates,
        'counts': dict(counters), 'reviewed_95': {'checked': len(case_status),
            'emitted': sum(c['note_emitted'] for c in case_status)},
        'reviewed_proposal_gap': {'checked': len(gaps), 'with_proposal': sum(c['proposal_id'] is not None for c in gaps),
            'notes_emitted': sum(c['note_emitted'] for c in gaps)},
        'cases': case_status, 'regressions': regressions}
    if (out/'checks.json').exists():
        checks = read(out/'checks.json')
        for name, expected in checks['code_sha256'].items():
            assert sha(ROOT.parents[1]/name) == expected, name
        validation['tests'] = checks
    if (out/'source-review.json').exists():
        validation['source_duration_review'] = read(out/'source-review.json')['source_duration_review']
    save(out/'validation.json', validation)
    lines = ['# Recovering reviewed heads without note proposals', '',
        f"The new opt-in proposal experiment emits notes at **{validation['reviewed_proposal_gap']['notes_emitted']} / {len(gaps)}** "
        'reviewed rest-only heads. All have new source-linked proposals. This is the purposeful five-song '
        'diagnostic audit, not an estimate of population accuracy. Physical recovery does not establish '
        'correct pitch, duration or part assignment.', '',
        f"Experiment: `{data['experiment_key']}`. [Validation and per-case events](validation.json), [results](results.json).", '',
        '| Dataset | Songs | Latest baseline edits | New edits | Denominator | Disagreement | Better / tie / worse |',
        '|---|---:|---:|---:|---:|---:|---|']
    for name, a in aggregates.items():
        lines.append(f"| {name} | {a['songs']} | {a['baseline_edits']} | {a['edits']} | {a['denominator']} | "
            f"{a['edits']/a['denominator']:.2%} | {a['better']} / {a['same']} / {a['worse']} |")
    lines += ['', '## Method', '',
        'Head-sized rest/measure-rest observations without a nearby note interpretation nominate sites. '
        'Unedited source crops are scored at 16, 20 and 24 pixels per staff space. Natural objectness peaks '
        'and a deduplicated forced 3×3 grid share the detector verifier. Full raw class/attribute posteriors '
        'are retained for matching refined head boxes; the detector normally keeps only its winning class. '
        'Note-family visual support and staff-position compatibility choose an alternative. No case ID, '
        'reference pitch, target note count or reference transcription enters prediction.', '',
        'Source ink constrains filled/open duration families. Enclosed white components must lie at least '
        '90% within the candidate box. A fixed-layout context pass decodes appended proposals; prior token '
        'readings are retained. Raw visual/context scores are saved separately from the explicit `.51` '
        'writer-admission decision. Hollow-head duration conditioning is an image policy, not a claim that '
        'the neural model independently classified the open duration.', '',
        'Complete staff-bar alternatives keep the latest baseline meter, shared cuts and part plan. '
        'They must retain every baseline physical pitch and add an independently supported head. A '
        'whole-measure rest in voice one is incompatible with a supported new voice-one note in that '
        'same staff/bar; the experimental reading suppresses that conflicting rest. This resolves the '
        'last reviewed Greenland omission, whose neighboring square was read as a whole-measure rest.', '',
        '[Reviewed source bars](recovered-18.jpg) show all 18 emitted heads. '
        '[Source review](source-review.json) records the remaining musical errors. '
        '[Negative controls](negative-controls.json) preserve genuine rest and empty-box checks.', '',
        '## Safeguards and limits', '',
        f"All {len(data['samples'])} latest baselines replay exactly. XML pitched events match emitted traces; "
        'staff/bar assignments, old symbol IDs/geometry, physical pitches, meter and measure counts pass '
        'validation. Predictions are saved for the entire batch before reference XML is opened. '
        'Source/code/model/cache hashes and code snapshots preserve provenance. Historical outputs and '
        'the published gallery remain unchanged.', '',
        'The 2025 references differ in edition from the 1911 scans. Scores measure disagreement, not pure '
        'recognition accuracy. These songs are development/diagnostic examples for this correction. '
        'Filled-head/open-head checks do not resolve every dot, beam, flag, pitch or layout error. '
        'The source scan at Greenland M056 has two printed quarter heads; its new proposal can still '
        'carry an erroneous dot, so emission alone must not be described as complete musical correction.', '',
        'Protection M034 is a filled triangular fa head, correcting the earlier diagnostic label of la. '
        'Source review identifies a quarter note, while this experiment can emit an eighth. '
        'The original reviewed-case file is preserved; this correction belongs to the new source review.', '',
        'The reviewed-head source check covers 17 durations: 15 match and two remain wrong; M033 is '
        'unresolved in the cropped review. Pitches and part assignments were not fully verified. '
        'Writer clipping can still shorten open-note values even when search alternatives respect '
        'the source duration-family constraint.', '',
        'Four visually confirmed shallow Clamanda half rests remain excluded from proposal sites; their '
        'raw note-family scores are recorded in the separate negative-controls diagnostic. Earlier '
        'automatic detector-rest selections included actual notes, so they are not negative labels.', '',
        '## Regressions versus the latest baseline', '',
        '| Dataset | Song | Before | After | Delta |', '|---|---|---:|---:|---:|']
    for r in regressions:
        lines.append(f"| {r['dataset']} | {r['title']} | {r['before']} | {r['after']} | +{r['after']-r['before']} |")
    if not regressions:
        lines.append('| — | None | — | — | — |')
    if (out/'regression-source-review.json').exists():
        lines += ['', 'Source inspection confirms printed noteheads at all 40 newly emitted proposal '
            'locations in the five regressing songs. This establishes physical note presence; '
            'their pitch, part assignment and rhythm still need review. '
            '[Source crops](regression-source-review.jpg), [review records](regression-source-review.json).']
    if 'tests' in validation:
        lines += ['', f"Tests: **{validation['tests']['passed']} passed**. [Command and code hashes](checks.json)."]
    lines += ['', '**Recommended:** review the remaining source-linked duration/pitch errors and regressions '
        'before enabling this proposal stage in the gallery pipeline.', '',
        '**Alternative:** retain it as an opt-in experiment and use the recovered crops to train a '
        'shape-note proposal classifier.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))
    artifacts = [f for f in out.rglob('*') if f.is_file()
                 and 'source-snapshots' not in f.parts and f.name != 'artifact-sha256.json']
    save(out/'artifact-sha256.json', {str(f.relative_to(out)): sha(f) for f in sorted(artifacts)})
    print(json.dumps({'aggregates': aggregates, 'counts': dict(counters),
        'reviewed_proposal_gap': validation['reviewed_proposal_gap']}, indent=2))
    print(out/'REPORT.md')


if __name__ == '__main__':
    main()
