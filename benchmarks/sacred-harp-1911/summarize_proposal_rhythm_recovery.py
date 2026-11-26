"""Validate source rhythm/system reflow and report all retained songs."""
from __future__ import annotations
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

from run_local_recovery import ROOT, read, save, sha, samples
from run_proposal_rhythm_recovery import PROPOSALS
from source_reflow import emitted_head_ids


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('experiment',type=Path);args=p.parse_args()
    out=args.experiment.resolve();data=read(out/'results.json');meta={s['id']:s for s in samples()}
    aggregates={};regressions=[];proposal_regressions=[];groupings=[];actions=[];pitch_changes=[]
    total=Counter();cases=[]
    review=read(PROPOSALS/'source-review.json')['cases']
    for r in data['samples']:
        sid=r['id'];f=ROOT/r['prediction'];assert sha(f)==r['sha256']
        t=read(f.with_suffix('.trace.json'));old=read(PROPOSALS/'predictions'/f'{sid}.trace.json')
        assert emitted_head_ids(old['writer'])<=emitted_head_ids(t['writer']),(sid,'lost head')
        assert r['proposal_exact_replay'] and r['physical_heads_retained']
        root=ET.parse(f).getroot()
        pitched=[(n.findtext('pitch/step'),int(n.findtext('pitch/octave')),int(n.findtext('pitch/alter','0')),int(n.findtext('duration','0')))
                 for n in root.findall('.//note') if n.find('pitch') is not None]
        assert pitched==[(e['step'],e['octave'],e['alter'],e['dur']) for e in t['writer']['emitted'] if e['kind']=='note']
        written=[]
        for part in root.findall('part'):
            divisions=1
            for measure in part.findall('measure'):
                divisions=int(measure.findtext('attributes/divisions',str(divisions)))
                written += [Fraction(int(n.findtext('duration','0')),divisions) for n in measure.findall('note')
                            if n.find('pitch') is not None]
        assert written==[Fraction(e['e.dur']) for e in t['writer']['emitted'] if e['kind']=='note'],sid
        for a,b in zip(old['syms'],t['syms']):
            if a['cls']!='measure':
                assert (a['i'],a['box'],a['staff'])==(b['i'],b['box'],b['staff']),(sid,a['i'])
        details=t['rhythm_recovery_details'];g=details['grouping']
        constraints=t['rhythm_recovery_duration_constraints']
        local=t['rhythm_recovery_local_details']
        for i,allowed in constraints.items():
            assert set(local['duration_options'].get(i,{}))<=set(allowed),(sid,i,'duration options')
        def check_actions(value):
            if isinstance(value,dict):
                i=str(value.get('sym_id'))
                if value.get('action')=='duration' and i in constraints:
                    assert value['new_type'] in constraints[i],(sid,i,'duration search')
                for child in value.values():check_actions(child)
            elif isinstance(value,list):
                for child in value:check_actions(child)
        check_actions(local['rhythm_search_decisions'])
        if g['changed']:
            assert g['status']=='grouped_four_part_cadence'
            assert all(g['cadence'][i:i+4]==['clef_G2']*3+['clef_F4'] for i in range(0,len(g['cadence']),4))
            groupings.append({'id':sid,'title':r['title'],**details})
        else:
            assert t['systems']==old['systems'] and t['staves']==old['staves']
        if details.get('segmentation',{}).get('accepted'):
            assert not details['segmentation']['missing_previous_heads']
            total['ink_segmented_songs']+=1
        for d in details['rhythm_decisions']:actions.append({'id':sid,'title':r['title'],**d})
        pitch_changes += [{'id':sid,'title':r['title'],**d} for d in details['pitch_reflow']]
        a=aggregates.setdefault(r['dataset'],{'songs':0,'baseline_edits':0,'proposal_edits':0,'edits':0,
            'denominator':0,'better':0,'same':0,'worse':0,'proposal_better':0,'proposal_same':0,'proposal_worse':0})
        before=r['baseline_comparison']['totals']['pitch_duration_edit_distance']
        previous=r['proposal_comparison']['totals']['pitch_duration_edit_distance']
        after=r['comparison']['totals']['pitch_duration_edit_distance']
        a['songs']+=1;a['baseline_edits']+=before;a['proposal_edits']+=previous;a['edits']+=after
        a['denominator']+=r['comparison']['totals']['pitch_duration_rate_denominator']
        a['better' if after<before else 'worse' if after>before else 'same']+=1
        a['proposal_better' if after<previous else 'proposal_worse' if after>previous else 'proposal_same']+=1
        item={'id':sid,'title':r['title'],'baseline':before,'previous_proposal':previous,'now':after}
        if after>before:regressions.append(item)
        if after>previous:proposal_regressions.append(item)
        for c in [c for c in review if c['song_id']==sid]:
            events=[e for e in t['writer']['emitted'] if e['kind']=='note' and e['e.si']==c['proposal_id']]
            assert events,(sid,c['case_id'])
            expected=c['source_expected_duration_quarters']
            case={**c,'events':events,'note_emitted':True,'emitted_duration_matches_source':
                all(e['e.dur']==expected for e in events) if expected is not None else None}
            if 'remaining_error' in case and case['emitted_duration_matches_source']:
                case['previous_error']=case.pop('remaining_error')
            cases.append(case)
    verified={}
    for name,expected in data['provenance'].items():
        f=ROOT.parents[1]/name;snapshot=out/'source-snapshots'/name
        used=f if f.exists() and sha(f)==expected else snapshot
        assert used.exists() and sha(used)==expected,name
        verified[name]=str(used.relative_to(ROOT.parents[1]))
    # Selection metadata is transitively bound by the immutable parent result
    # hash in this experiment. Verify the actual files used by samples() too.
    parent=read(PROPOSALS/'results.json')['provenance']
    metadata_hashes={}
    for relative in ('reader-gallery/results.json','experiments/bar-fitting/unused20/manifest.json',
                     'experiments/bar-fitting/unused20/results.json',
                     'experiments/reader-v2/replay_bar_fit/results.json'):
        name=str((ROOT/relative).relative_to(ROOT.parents[1]))
        assert sha(ROOT/relative)==parent[name],name
        metadata_hashes[name]=parent[name]
    checks=read(out/'checks.json') if (out/'checks.json').exists() else None
    if checks:
        for name,expected in checks['code_sha256'].items():assert sha(ROOT.parents[1]/name)==expected,name
    validation={'songs':len(data['samples']),'all_previous_proposals_replayed_exactly':True,
        'all_previous_physical_noteheads_retained':True,'all_notehead_ids_boxes_and_staff_identity_retained':True,
        'all_xml_pitched_events_match_traces':True,'source_layout_changes':groupings,
        'all_proposal_duration_options_and_search_actions_respect_constraints':True,
        'source_pitch_changes':pitch_changes,'rhythm_decisions':actions,'aggregates':aggregates,
        'regressions_vs_note_rest':regressions,'regressions_vs_previous_proposals':proposal_regressions,
        'reviewed_18':cases,'source_duration_review':{'checked':sum(c['emitted_duration_matches_source'] is not None for c in cases),
            'match':sum(c['emitted_duration_matches_source'] is True for c in cases),
            'mismatch':sum(c['emitted_duration_matches_source'] is False for c in cases),
            'unresolved':[c['case_id'] for c in cases if c['emitted_duration_matches_source'] is None]},
        'counts':{'source_grouped_songs':len(groupings),**total,
            'rhythm_changes':sum(a['action']!='check_context_dot' and not a.get('rejected') for a in actions),
            'rejected_lossy_rhythm_changes':sum(bool(a.get('rejected')) for a in actions)},
        'generation_provenance_verified':verified,'parent_bound_selection_metadata_verified':metadata_hashes,
        'tests':checks}
    save(out/'validation.json',validation)
    lines=['# Source rhythm and regression recovery','',
        'Protection M034 now emits an undotted quarter, and Greenland M056 an undotted quarter. '
        'All 18 previously recovered heads still emit notes. Of the 17 source-reviewed durations, '
        f"{validation['source_duration_review']['match']} match; Protection M033 remains unresolved. "
        'Pitch and part assignment of every reviewed note have not been fully audited.','',
        '[Validation and decisions](validation.json), [per-song results](results.json), [checks](checks.json).','',
        '| Dataset | Songs | Before proposals | Previous proposals | Current | Denominator | Disagreement |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name,a in aggregates.items():
        lines.append(f"| {name} | {a['songs']} | {a['baseline_edits']} | {a['proposal_edits']} | {a['edits']} | {a['denominator']} | {a['edits']/a['denominator']:.2%} |")
    lines += ['','## Five reviewed regressions','',
        '| Song | Before proposals | Previous proposals | Current |','|---|---:|---:|---:|']
    target={'Clamanda','The Golden Harp','Monroe','Farewell To All','Salem'}
    for r in data['samples']:
        if r['title'] in target:
            lines.append(f"| {r['title']} | {r['baseline_comparison']['totals']['pitch_duration_edit_distance']} | {r['proposal_comparison']['totals']['pitch_duration_edit_distance']} | {r['comparison']['totals']['pitch_duration_edit_distance']} |")
    lines += ['','## Source-based changes','',
        'The symbolic context model had overridden a strong direct visual quarter reading in Protection. '
        'The opt-in policy now restores a filled quarter from a faster reading when its direct visual '
        'conditional probability is at least .85 and context confidence is below .9. It leaves open-head '
        'duration changes and faster-note changes to separate stem/flag evidence. It removes a contextual dot only when context is below .9, '
        'the direct visual no-dot posterior is at least .9, and a source-image check finds no compact '
        'detached dot. Raw context/visual readings and decisions remain saved. A conditional duration '
        'probability is not a calibrated probability that a note exists. Genuine Greenland M055 dot '
        'and M057 eighth controls are retained. Rhythm edits that would remove a previously emitted '
        'physical head are rolled back in the affected source bar; rejected attempts remain logged.','',
        'The regressions were primarily layout errors: parallel printed staves had been serialized into '
        'incorrect systems/parts. An opt-in rule groups only complete source opening clef sequences '
        'G2/G2/G2/F4, with confident glyphs near the staff opening. It preserves three-part and ambiguous '
        'layouts. The rule changes every eligible song, rather than selecting titles or score gains. '
        f"{len(groupings)} songs are reflowed; all remain in the aggregates. Existing staff-bar voices, "
        'durations and inherited cuts move with their physical staff, preventing a layout correction '
        'from silently discarding old heads. Pitches can be refreshed under the actual source staff '
        'clef/key; each change is logged.','',
        'Collapsed bars with separate confident beat-zero readings additionally try the existing '
        'front-end ink segmentation. A segmentation candidate is rejected if it loses any previously '
        'emitted physical head. Source meter glyph agreement supplies the meter for accepted segmentation. '
        'This resolves Clamanda’s wide collapsed bars and artificial tuplet. Other segmentation errors '
        'and inherited irregular bar lengths can remain; reflow does not claim to solve every rhythm.','',
        '## Validation and limits','',
        f"All {len(data['samples'])} previous proposal XML/event streams replay exactly. Every previously "
        'emitted physical head remains; notehead IDs, boxes and staff identity remain. Every final XML '
        'pitched event matches its trace. Part counts, bar assignments, meter and measure counts can '
        'change where source layout evidence requires it; they are not frozen invariants in this stage. '
        'No new neural inference is needed. The complete batch is saved before reference scoring, '
        'with code/input hashes and source snapshots. Historical outputs and hosted gallery are untouched.','',
        'All 120 songs are development/diagnostic examples. Scores compare 1911 scans with the 2025 '
        'edition and measure disagreement, not pure recognition accuracy. Source grouping uses the '
        'normal four-part Sacred Harp clef cadence and abstains outside that scope. Further unused '
        'source-screened validation is needed before broad enablement.','',
        f"Regressions versus before proposals: {len(regressions)}. Versus previous proposals: {len(proposal_regressions)}."]
    if regressions or proposal_regressions:
        lines += ['',f'Included regressions: `{regressions or proposal_regressions}`.']
    if checks:lines += ['',f"Tests: **{checks['passed']} passed**."]
    if (out/'source-layout-review.json').exists():
        lines += ['', '[Source layout review](source-layout-review.json).']
    if (out/'rhythm-changes.json').exists():
        lines += ['', '[Source rhythm changes](rhythm-changes.json); '
                  '[source crops](rhythm-changes-contact-01.jpg).']
    if (out/'rejected-open-duration-review.json').exists():
        lines += ['', '[Rejected open-head duration trial](rejected-open-duration-review.json): '
                  'source inspection rejected unsupported whole-to-half overrides.']
    lines += ['','**Recommended:** validate on further unused source-screened songs before enabling broadly.',
        '**Alternative:** keep this stage opt-in and audit the remaining bar boundaries and inherited irregular bar lengths.','']
    (out/'REPORT.md').write_text('\n'.join(lines))
    save(out/'artifact-sha256.json',{str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*'))
        if f.is_file() and 'source-snapshots' not in f.parts and f.name!='artifact-sha256.json'})
    print({'aggregates':aggregates,'duration_review':validation['source_duration_review'],
           'regressions':regressions,'proposal_regressions':proposal_regressions,'counts':validation['counts']})
    print(out/'REPORT.md')

if __name__=='__main__':main()
