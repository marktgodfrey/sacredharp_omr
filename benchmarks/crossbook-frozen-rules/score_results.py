"""Score completed frozen outputs, retaining timing invariant failures as results.

This replaces the first adapter scorer's overstrict equal-span assertion.
No generation code or frozen policy is modified. Existing unequal-span outputs
are explicitly flagged and scored, never repaired or removed from the sample.
"""
from pathlib import Path
import argparse
import json
from run_frozen_rules import (ROOT,WORKSPACE,HISTORICAL,ENGINES,VARIANTS,read,save,sha,
                              engine_files,activate,pooled)


def change_counts(rows):
    return {'pd_better':sum(r['pd_change_current_vs_prior']<0 for r in rows),
            'pd_tied':sum(r['pd_change_current_vs_prior']==0 for r in rows),
            'pd_worse':sum(r['pd_change_current_vs_prior']>0 for r in rows),
            'f1_better':sum(r['f1_change_current_vs_prior']>0 for r in rows),
            'f1_tied':sum(r['f1_change_current_vs_prior']==0 for r in rows),
            'f1_worse':sum(r['f1_change_current_vs_prior']<0 for r in rows)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path)
    out=parser.parse_args().run.resolve()
    for phase in ('capture','prior','current'):assert read(out/f'{phase}-complete.json')['hash_guard_passed']
    provenance=read(out/'provenance.json')
    adapter=WORKSPACE/provenance.get('adapter_path','benchmarks/crossbook-frozen-rules/run_frozen_rules.py')
    assert provenance['adapter_sha256']==sha(adapter)
    if 'frozen_engines' in provenance:
        ENGINES.clear();ENGINES.update({e:WORKSPACE/path for e,path in provenance['frozen_engines'].items()})
    expected_code=provenance.get('engine_code',provenance.get('engine_code_and_assets'))
    assert expected_code=={e:engine_files(e) for e in ENGINES}
    activate('current')
    from edition_comparison import compare_edition
    manifest=read(out/'manifest.json');rows=[]
    empty=out/'empty.musicxml'
    if not empty.exists():empty.write_text('<score-partwise><part-list/></score-partwise>')
    for s in manifest['samples']:
        for variant in VARIANTS:
            scores={};paths={};changes={};unresolved={};spans={}
            for stage in ('baseline','prior','current'):
                pred=out/'seeds'/variant/'predictions'/f'{s["id"]}.musicxml' if stage=='baseline' else out/stage/variant/f'{s["id"]}.musicxml'
                failed=not pred.exists();path=empty if failed else pred
                scores[stage]={'failed':failed,**compare_edition(HISTORICAL/s['reference'],path,
                                       s['source_voice_order'],s['reference_voice_order'])}
                paths[stage]=str(pred.relative_to(out))
                if stage!='baseline' and not failed:
                    t=read(pred.with_suffix('.trace.json'))
                    unresolved[stage]=sum(not d['resolved'] for d in t['source_bar_fit_decisions'])
                    changes[stage]=t['rhythm_resolution_details']['duplicate_serialized_events_removed']
                    spans[stage]=t['final_timing']['xml_inventory']['columns_with_unequal_part_spans']
            row={'id':s['id'],'book':s['book'],'title':s['title'],'cohort':s.get('cohort','pilot'),'variant':variant,'scores':scores,
                 'predictions':paths,'unresolved_columns':unresolved,'event_removals':changes,
                 'unequal_part_span_columns':spans,'timing_invariants_passed':not any(spans.values())}
            a=scores['prior']['comparison'];b=scores['current']['comparison']
            row['pd_change_current_vs_prior']=b['totals']['pitch_duration_edit_distance']-a['totals']['pitch_duration_edit_distance']
            row['f1_change_current_vs_prior']=b['time_aware_exact_event_multiset']['f1']-a['time_aware_exact_event_multiset']['f1']
            rows.append(row)
    aggregates=[]
    for book in sorted({s['book'] for s in manifest['samples']}):
        for variant in VARIANTS:
            subset=[r for r in rows if r['book']==book and r['variant']==variant]
            for stage in ('baseline','prior','current'):
                aggregates.append({'book':book,'variant':variant,'stage':stage,
                    **pooled([r['scores'][stage]['comparison'] for r in subset]),
                    'failed_cases':sum(r['scores'][stage]['failed'] for r in subset),
                    'timing_invariant_failure_cases':sum(bool(r['unequal_part_span_columns'].get(stage)) for r in subset)})
    counts=change_counts(rows);added=[r for r in rows if r['cohort']!='pilot']
    added_counts=change_counts(added);added_aggregates=[]
    for book in sorted({r['book'] for r in added}):
        for variant in VARIANTS:
            subset=[r for r in added if r['book']==book and r['variant']==variant]
            for stage in ('baseline','prior','current'):
                added_aggregates.append({'book':book,'variant':variant,'stage':stage,
                                        **pooled([r['scores'][stage]['comparison'] for r in subset])})
    captures=read(out/'capture-complete.json')['cases']
    parity_true=sum(r.get('sealed_pilot_score_xml_identical') is True for r in captures)
    parity_false=sum(r.get('sealed_pilot_score_xml_identical') is False for r in captures)
    parity_missing=sum(r.get('sealed_pilot_score_xml_identical') is None for r in captures)
    save(out/'results.json',{'scope':f"{len(manifest['samples'])} source crops across independent printings, both layouts",
         'frozen_engines':{e:str(p.relative_to(WORKSPACE)) for e,p in ENGINES.items()},
         'analysis_code_sha256':sha(Path(__file__)),'current_vs_prior_counts':counts,'aggregates':aggregates,
         'added_cohort_counts':added_counts,'added_cohort_configurations':len(added),'added_cohort_aggregates':added_aggregates,
         'baseline_parity_true':parity_true,'baseline_parity_false':parity_false,
         'baseline_parity_unavailable':parity_missing,'samples':rows})
    descriptions=provenance.get('stage_descriptions',{'prior':'pre-dot/false-head rhythm checkpoint',
                                                     'current':'new dot/false-head checkpoint'})
    lines=['# Frozen rhythm rules: independent-printing evaluation','',
           f"All {len(manifest['samples'])} selected source crops ({len(rows)} layout configurations) are retained. Rules and 1911 JPK meter templates were frozen before seeing these readings. No target-data tuning was performed.",'',
           '| Book | Layout | Stage | PD edits / denominator | F1 | Failed predictions | Timing failures |',
           '|---|---|---|---:|---:|---:|---:|']
    lines += [f"| {a['book']} | {a['variant']} | {a['stage']} | {a['pd_edits']}/{a['pd_denominator']} | {a['time_aware_f1']:.4f} | {a['failed_cases']} | {a['timing_invariant_failure_cases']} |" for a in aggregates]
    lines += ['',f'Current versus prior across {len(rows)} paired configurations: **{counts}**.',
              f'Added cohort only ({len(added)} configurations): **{added_counts}**.','',
              f"`prior`: {descriptions['prior']}. `current`: {descriptions['current']}. Both start from identical baseline events; this does not reproduce the earlier JPK missing-head-proposal stages. `baseline` is the frozen CoreML reader without rhythm-resolution. Source voice order is used only for scoring; edition-absent altos are excluded, and unexpected/missing detected source parts remain penalized.",'',
              f"All {len(rows)} baseline captures and {2*len(rows)} frozen-policy outputs completed under hash guards before reference scoring. Baseline parity comparators: {parity_true} match, {parity_false} differ, {parity_missing} unavailable for new captures. Timing failures remain data rather than exclusions. Neither rule snapshot was changed during generation.",'',
              '## Timing invariant failures','']
    lines += [f"- {r['id']} / {r['variant']}: {r['unequal_part_span_columns']}." for r in rows if not r['timing_invariants_passed']] or ['None.']
    lines += ['','## Current versus prior: every changed score','']
    changed=[r for r in rows if r['pd_change_current_vs_prior'] or r['f1_change_current_vs_prior']]
    lines += [f"- {r['id']} / {r['variant']}: PD {r['pd_change_current_vs_prior']:+d}; F1 {r['f1_change_current_vs_prior']:+.4f}." for r in changed] or ['No score changes.']
    lines += ['','These editions differ from the 2025 XML references, including absent altos and Bethel key signatures. Scores measure disagreement, not historical-source accuracy. Repeated matched tunes and two layout variants are paired observations, not independent songs. This is a printing-domain test, not proof that the model never trained on these tunes or editions.','',
              'Source adjudication of changed decisions is recorded separately. Defaults and gallery remain unchanged.','',
              '**Recommended:** inspect changed source decisions and the full-stage timing failures before broader enablement.',
              '**Alternative:** expand independent-book coverage with the same frozen rules and no tuning on this run.','']
    (out/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps({'counts':counts,'aggregates':aggregates},indent=2))


if __name__=='__main__':main()
