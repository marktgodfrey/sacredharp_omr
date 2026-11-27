"""Compare a completed frozen batch with the prior rhythm-resolution checkpoint.

Uses already scored results; never opens reference XML or changes predictions.
The source case IDs below are validation assertions, never prediction inputs.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
from run_local_recovery import ROOT,read,save,sha
from summarize_rhythm_resolution import aggregate,unresolved_counts

PREVIOUS=ROOT/'experiments/rhythm-resolution/final-a17498fc863d'
AUDIT=ROOT/'diagnostics/timing-regression-audit-2026-11-26/audit.json'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('experiment',type=Path)
    out=parser.parse_args().experiment.resolve()
    complete=read(out/'predictions-complete.json')
    assert complete['generation_code_unchanged_through_complete_batch']
    assert complete['references_opened_during_generation'] is False
    old_data=read(PREVIOUS/'results.json');new_data=read(out/'results.json')
    old={r['id']:r for r in old_data['samples']};new={r['id']:r for r in new_data['samples']}
    assert set(old)==set(new) and len(new)==120
    rows=[];queue=[];traces={};current_unresolved=previous_unresolved=0
    changed_cuts=0
    for sid,r in new.items():
        prior=old[sid]
        current=read((ROOT/r['prediction']).with_suffix('.trace.json'))
        previous=read((ROOT/prior['prediction']).with_suffix('.trace.json'));traces[sid]=current
        pd=r['comparison']['totals']['pitch_duration_edit_distance']-prior['comparison']['totals']['pitch_duration_edit_distance']
        f1=r['comparison']['time_aware_exact_event_multiset']['f1']-prior['comparison']['time_aware_exact_event_multiset']['f1']
        cuts=[{'column':i,'previous_cut':a,'current_cut':b} for i,(a,b) in enumerate(zip(
            previous['final_timing']['selected_cuts'],current['final_timing']['selected_cuts'])) if Fraction(a)!=Fraction(b)]
        assert len(previous['final_timing']['selected_cuts'])==len(current['final_timing']['selected_cuts'])
        changed_cuts+=len(cuts)
        current_unresolved+=unresolved_counts(current)[0];previous_unresolved+=unresolved_counts(previous)[0]
        row={'song_id':sid,'title':r['title'],'dataset':r['dataset'],'pd_change':pd,
             'time_aware_f1_change':f1,'changed_common_cuts':cuts,
             'previous_comparison':prior['comparison'],'comparison':r['comparison']}
        rows.append(row)
        if pd>0 or f1<0:
            changed={d['column'] for d in cuts}
            queue.append({k:v for k,v in row.items() if k not in ('previous_comparison','comparison')} | {
                'review_status':'unadjudicated',
                'source_fit_decisions_at_changed_cuts':[d for d in current['source_bar_fit_decisions'] if d['column'] in changed],
                'notes':'Source review required; edition disagreement is not pure accuracy. Keep all songs included.'})
    checks=[]
    for case in read(AUDIT)['cases']:
        trace=traces[case['song_id']];decisions=case['source_review']['decisions']
        emitted=[e for e in trace['writer']['emitted'] if e['kind']=='note']
        for si,expected in decisions.items():
            events=[e for e in emitted if int(e['e.si'])==int(si)]
            if expected=='reject_non_head':assert not events,(case['song_id'],si,'false head retained')
            elif expected is None:assert events,(case['song_id'],si,'ambiguous physical head lost')
            else:assert events and all(Fraction(e['e.dur'])==Fraction(expected) for e in events),(case['song_id'],si,events,expected)
        column=case['column_zero_based'];cut=trace['final_timing']['selected_cuts'][column]
        expected=case['reviewed_voice_duration_quarters']
        if expected is not None:assert Fraction(cut)==Fraction(expected),(case['song_id'],column,cut,expected)
        else:
            d=next(d for d in trace['source_bar_fit_decisions'] if d['column']==column)
            assert not d['resolved'] and Fraction(cut)==7
            assert any(e['e.si']==361 and e['dots']==1 for e in emitted)
        checks.append({'song_id':case['song_id'],'column':column,'selected_cut':cut,
                       'source_review_status':case['source_review']['status'],'passed':True})
    aggregates={stage:aggregate(rows,{key:stage}) for key,stage in
                (('previous_comparison','previous'),('comparison','current'))}
    counts={'pd_better':sum(r['pd_change']<0 for r in rows),'pd_tied':sum(r['pd_change']==0 for r in rows),
            'pd_worse':sum(r['pd_change']>0 for r in rows),'timing_better':sum(r['time_aware_f1_change']>0 for r in rows),
            'timing_tied':sum(r['time_aware_f1_change']==0 for r in rows),'timing_worse':sum(r['time_aware_f1_change']<0 for r in rows)}
    queue.sort(key=lambda r:(r['time_aware_f1_change'],-r['pd_change']))
    save(out/'regression-audit-queue.json',{'comparison_parent':str(PREVIOUS.relative_to(ROOT)),
         'songs':len(queue),'pd_regressions':counts['pd_worse'],'timing_regressions':counts['timing_worse'],'cases':queue})
    summary={'comparison_parent':str(PREVIOUS.relative_to(ROOT)),'comparison_parent_results_sha256':sha(PREVIOUS/'results.json'),
             'songs':len(rows),'counts':counts,'aggregates':aggregates,'previous_unresolved_columns':previous_unresolved,
             'current_unresolved_columns':current_unresolved,'changed_common_cuts':changed_cuts,'source_audit_case_checks':checks,
             'per_song':[{k:v for k,v in r.items() if k not in ('previous_comparison','comparison')} for r in rows]}
    save(out/'comparison-to-prior-rhythm.json',summary)
    lines=['# Dot and false-head evidence: frozen batch comparison','',
           'Compared with `final-a17498fc863d` on all 120 songs. Predictions completed under the code hash guard before reference scoring. Defaults and gallery remain unchanged.','',
           '| Dataset | Stage | PD edits | Time-aware F1 |','|---|---|---:|---:|']
    for dataset in sorted(aggregates['current']):
        for stage in ('previous','current'):
            a=aggregates[stage][dataset];lines.append(f"| {dataset} | {stage} | {a['pd']} | {a['time_aware_f1']:.4f} |")
    lines += ['',f"PD better / tied / worse: {counts['pd_better']} / {counts['pd_tied']} / {counts['pd_worse']}. Timing better / tied / worse: {counts['timing_better']} / {counts['timing_tied']} / {counts['timing_worse']}.",
              f'Unresolved shared columns: {previous_unresolved} → {current_unresolved}. Changed common cuts: {changed_cuts}.','',
              '## Audited source bars','', '| Song ID | Column (zero-based) | Selected quarters | Status |','|---|---:|---:|---|']
    lines += [f"| {c['song_id']} | {c['column']} | {c['selected_cut']} | {c['source_review_status']} |" for c in checks]
    lines += ['','The five locally adjudicated bars pass their source-value/false-head checks. Elder column 8 retains its visible stemless head, real dot, and flagged seven-quarter overflow. These checks do not adjudicate every event in the five songs.','',
              '## Regressions against the prior checkpoint','']
    lines += [f"- {r['title']} (`{r['song_id']}`): PD {r['pd_change']:+d}; F1 {r['time_aware_f1_change']:+.4f}." for r in queue] or ['None.']
    lines += ['','All songs are development/diagnostic material from one book. Reference editions differ; these metrics do not establish cross-book accuracy. Holy Manna remains included without a layout-specific repair.','',
              '**Recommended:** source-review remaining regressions and evaluate a frozen cross-book holdout before broader enablement.',
              '**Alternative:** keep the stage quarantined while collecting more source-reviewed controls.','']
    (out/'COMPARISON.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in summary.items() if k!='per_song'},indent=2))


if __name__=='__main__':main()
