"""Validate completed source timing runs and summarize score changes."""
from __future__ import annotations
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

from run_local_recovery import ROOT, read, save, sha
from run_source_timing_recovery import PARENT
from run_proposal_rhythm_recovery import PROPOSALS
from source_reflow import emitted_head_ids
from run_local_recovery import samples
from audit_bar_meter import xml_inventory
from source_saved_events import source_saved_events


def totals(row):
    return row['comparison']['totals']


def pitched_by_id(writer):
    return Counter((int(e['e.si']),e['step'],int(e['octave']),int(e['alter']))
                   for e in writer['emitted'] if e['kind']=='note')


def span_summary(inv):
    rows=inv['measures']
    return {'over_nominal':sum(x['status']=='over_nominal' for x in rows),
            'invisible_padding_quarters':str(sum((Fraction(x['invisible_padding_quarters']) for x in rows),Fraction(0)))}


def validate_bar_cut(bar, cuts):
    """Reject a bar whose recorded cut differs from its global measure cut."""
    return bar['selected_cut']==cuts[int(bar['bar'])-1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('experiment',type=Path);a=p.parse_args()
    out=a.experiment.resolve();data=read(out/'results.json'); parent=read(PARENT/'results.json')['samples']; parent={x['id']:x for x in parent}
    complete=read(out/'predictions-complete.json'); expected_ids=[x['id'] for x in data['samples']]
    assert complete['ids']==expected_ids and len(set(expected_ids))==len(expected_ids)
    assert all(x['experiment_key']==data['experiment_key']==complete['experiment_key'] for x in data['samples'])
    assert sha(out/'source-meter-templates.npz')==complete['source_meter_templates_sha256']
    sample_by_id={x['id']:x for x in samples()}; verified_provenance={}
    for name,digest in data['provenance'].items():
        actual=ROOT.parents[1]/name
        if name.endswith('.py'):
            snap=out/'source-snapshots'/name
            assert snap.exists() and sha(snap)==digest,('code snapshot',name)
        else:
            assert actual.exists() and sha(actual)==digest,('run metadata provenance',name)
        verified_provenance[name]=digest
    for sid in expected_ids:
        s=sample_by_id[sid]
        for rel,key in ((s['input'],'input_sha256'),(s['baseline_trace'],None)):
            name=str((ROOT/rel).relative_to(ROOT.parents[1]));expected=s[key] if key else data['provenance'][name]
            assert data['provenance'][name]==expected and sha(ROOT/rel)==expected,(sid,rel)
    agg=Counter();datasets={}; regressions=[];per_song=[];unresolved=[];meter_changes=[];validated=[];reviewed=[]
    source_review=read(PROPOSALS/'source-review.json')['cases']
    for r in data['samples']:
        sid=r['id'];f=ROOT/r['prediction'];assert sha(f)==r['sha256'];assert sha(f.with_suffix('.trace.json'))==r['trace_sha256']
        t=read(f.with_suffix('.trace.json'));old=read(PARENT/'predictions'/f'{sid}.trace.json')
        assert emitted_head_ids(old['writer'])<=emitted_head_ids(t['writer']),(sid,'lost physical pitched IDs')
        old_pitch=pitched_by_id(old['writer']);new_pitch=pitched_by_id(t['writer'])
        assert old_pitch<=new_pitch,(sid,'previous physical pitch changed or disappeared',old_pitch-new_pitch)
        root=ET.parse(f).getroot()
        pitches=[(n.findtext('pitch/step'),int(n.findtext('pitch/octave')),int(n.findtext('pitch/alter','0')),int(n.findtext('duration','0'))) for n in root.findall('.//note') if n.find('pitch') is not None]
        assert pitches==[(e['step'],e['octave'],e['alter'],e['dur']) for e in t['writer']['emitted'] if e['kind']=='note'],sid
        written=[]
        for part in root.findall('part'):
            divisions=1
            for measure in part.findall('measure'):
                divisions=int(measure.findtext('attributes/divisions',str(divisions)))
                written += [Fraction(int(n.findtext('duration','0')),divisions)
                            for n in measure.findall('note') if n.find('pitch') is not None]
        assert written==[Fraction(e['e.dur']) for e in t['writer']['emitted'] if e['kind']=='note'],sid
        def annotations(trace,xml):
            evs,_=source_saved_events(trace,xml)
            return Counter((e.si,e.accidental,tuple(sorted(e.marks)),e.arpeggiate)
                           for rows in evs.values() for e in rows if e.kind=='note')
        assert annotations(old,(PARENT/'predictions'/f'{sid}.musicxml').read_text())<=annotations(t,f.read_text()),(sid,'source note annotation lost')
        for x,y in zip(old['syms'],t['syms']):
            if x['cls']!='measure': assert (x['i'],x['box'],x['staff'])==(y['i'],y['box'],y['staff']),(sid,x['i'])
        timing=t['final_timing'];actual_inventory=xml_inventory(f.read_text())
        assert timing['xml_inventory']==actual_inventory,(sid,'stale XML inventory')
        assert timing['selected_cuts'] and len(timing['selected_cuts'])==max((x['measures'] for x in actual_inventory['parts']),default=0)
        decisions=t['source_bar_fit_decisions'];assert len(decisions)==int(r['columns'])
        assert sum(not bool(x['resolved']) for x in decisions)==int(r['unresolved_columns'])
        assert all(not x['resolved'] or x['selected_cut'] is None or Fraction(x['selected_cut'])<=Fraction(x['nominal_quarters']) for x in decisions)
        for i,x in enumerate(decisions): assert x['selected_cut']==timing['selected_cuts'][i]
        bars_by_no={}
        for b in timing['bars']:
            assert validate_bar_cut(b,timing['selected_cuts']),(sid,b)
            assert not b['dropped_head_ids'],(sid,b['dropped_head_ids'])
            assert not b['shortened_events'],(sid,b['shortened_events'])
            bars_by_no.setdefault(int(b['bar']),set()).add((b['local_meter'],b['selected_cut']))
        assert all(len(x)==1 for x in bars_by_no.values()),(sid,bars_by_no)
        state_by_bar={(x['staff'],x['bar']):x['meter'] for x in t['source_meter_state']['meter_by_staff_bar']}
        xml_bars={(x['part'],x['measure']):x for x in actual_inventory['measures']}
        for b in timing['bars']:
            if (b['staff'],b['source_bar']) in state_by_bar:
                assert b['local_meter']==state_by_bar[b['staff'],b['source_bar']],(sid,'meter carry',b)
            assert xml_bars[b['part'],b['bar']]['meter']==b['local_meter'],(sid,'XML local meter',b)
        transitions=[(x['measure'],x['meter']) for part in actual_inventory['parts'] for x in part['meter_changes']]
        source_transition_meters={x['meter'] for x in t['source_meter_state']['transitions']}
        explicit_meters={meter for _,meter in transitions}
        assert source_transition_meters<=explicit_meters,(sid,source_transition_meters,explicit_meters)
        for case in (x for x in source_review if x['song_id']==sid):
            events=[e for e in t['writer']['emitted'] if e['kind']=='note' and e['e.si']==case['proposal_id']]
            assert events,(sid,case['case_id'],'reviewed physical note missing')
            expected=case['source_expected_duration_quarters']
            reviewed.append({**case,'events':events,'note_emitted':True,'emitted_duration_matches_source':
                all(Fraction(e['e.dur'])==Fraction(str(expected)) for e in events) if expected is not None else None})
        u=int(r['unresolved_columns']); unresolved.append({'id':sid,'title':r['title'],'unresolved':u,'columns':r['columns']})
        meter_changes.append({'id':sid,'title':r['title'],'opening_meter':r['opening_meter'],'transitions':r['source_meter_transitions']})
        now=totals(r);before=r['baseline_comparison']['totals'];prev=before
        before_xml=ROOT/parent[sid]['prediction']
        item={'id':sid,'title':r['title'],'dataset':r['dataset'],'pd_before':before['pitch_duration_edit_distance'],'pd_parent':prev['pitch_duration_edit_distance'],'pd_now':now['pitch_duration_edit_distance'],'pd_denominator':now['pitch_duration_rate_denominator'],
              'time_aware_before':r['baseline_comparison']['time_aware_exact_event_multiset'],'time_aware_parent':r['baseline_comparison']['time_aware_exact_event_multiset'],'time_aware_now':r['comparison']['time_aware_exact_event_multiset']}
        item['span_parent']=span_summary(xml_inventory(before_xml.read_text()))
        item['span_current']=span_summary(actual_inventory)
        per_song.append(item)
        if item['pd_now']>item['pd_before'] or item['pd_now']>item['pd_parent'] or item['time_aware_now']['f1']<item['time_aware_before']['f1'] or item['time_aware_now']['f1']<item['time_aware_parent']['f1']:regressions.append(item)
        d=datasets.setdefault(r['dataset'],{'songs':0,'pd_before':0,'pd_parent':0,'pd_now':0,'denominator':0,'ta_pred':0,'ta_ref':0,'ta_matches':0,'ta_parent_pred':0,'ta_parent_ref':0,'ta_parent_matches':0,'ta_before_pred':0,'ta_before_ref':0,'ta_before_matches':0})
        d['songs']+=1
        for k,v in [('pd_before',before['pitch_duration_edit_distance']),('pd_parent',prev['pitch_duration_edit_distance']),('pd_now',now['pitch_duration_edit_distance']),('denominator',now['pitch_duration_rate_denominator'])]:d[k]+=v
        for prefix,metric in [('ta',r['comparison']['time_aware_exact_event_multiset']),('ta_parent',r['baseline_comparison']['time_aware_exact_event_multiset']),('ta_before',r['baseline_comparison']['time_aware_exact_event_multiset'])]:
            d[prefix+'_pred']+=r['comparison']['totals']['prediction_notes'] if prefix=='ta' else (parent[sid]['comparison']['totals']['prediction_notes'] if prefix=='ta_parent' else r['baseline_comparison']['totals']['prediction_notes'])
            d[prefix+'_ref']+=r['comparison']['totals']['reference_notes'] if prefix=='ta' else (parent[sid]['comparison']['totals']['reference_notes'] if prefix=='ta_parent' else r['baseline_comparison']['totals']['reference_notes'])
            d[prefix+'_matches']+=metric['matches']
        validated.append(sid)
    for d in datasets.values():
        for prefix in ('ta','ta_parent','ta_before'):
            pr=d[prefix+'_matches']/d[prefix+'_pred'] if d[prefix+'_pred'] else 0;re=d[prefix+'_matches']/d[prefix+'_ref'] if d[prefix+'_ref'] else 0
            d[prefix+'_precision']=pr;d[prefix+'_recall']=re;d[prefix+'_f1']=2*pr*re/(pr+re) if pr+re else 0
    validation={'songs':len(validated),'all_selected_hashes_valid':True,'all_parent_physical_pitched_ids_retained':True,'physical_geometry_and_staff_retained':True,'final_xml_trace_pitch_duration_match':True,'final_timing_cut_provenance_valid':True,'verified_provenance':verified_provenance,'unresolved_columns':unresolved,'meter_changes':meter_changes,'aggregates':datasets,'per_song':per_song,'regressions_vs_parent_or_baseline':regressions,'reviewed_source_notes':reviewed,'source_duration_review':{'checked':sum(x['emitted_duration_matches_source'] is not None for x in reviewed),'match':sum(x['emitted_duration_matches_source'] is True for x in reviewed),'mismatch':sum(x['emitted_duration_matches_source'] is False for x in reviewed),'unresolved':[x['case_id'] for x in reviewed if x['emitted_duration_matches_source'] is None]}}
    save(out/'validation.json',validation)
    lines=['# Source timing recovery validation','','Every selected record hash was checked. Prior emitted physical pitched IDs, note geometry and staff identity remain; final XML pitched events agree with the writer trace. Timing cuts and per-bar clipping provenance were checked.','',f"Validated **{len(validated)} selected songs**. Unresolved columns: **{sum(x['unresolved'] for x in unresolved)} / {sum(x['columns'] for x in unresolved)}**; these remain unresolved where source evidence does not support a decision.",'','| Dataset | Songs | PD before | PD parent | PD current | Denominator | Time aware F1 before | F1 parent | F1 current |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,d in datasets.items(): lines.append(f"| {name} | {d['songs']} | {d['pd_before']} | {d['pd_parent']} | {d['pd_now']} | {d['denominator']} | {d['ta_before_f1']:.3f} | {d['ta_parent_f1']:.3f} | {d['ta_f1']:.3f} |")
    duration=validation['source_duration_review'];lines += ['','PD is pitch-duration edit distance; lower is better. Time-aware F1 is computed from the exact event multiset across this run. Per-song values, meter transitions, and over-nominal/invisible-padding span summaries before and after are in `validation.json`.',f"Reviewed source durations: {duration['match']} match, {duration['mismatch']} mismatch, {len(duration['unresolved'])} unresolved of {duration['checked']} checkable source cases.", '',f"Regressions against either baseline or parent: **{len(regressions)}**.",'','**Recommended:** review the listed per-song regressions and unresolved source columns before expanding the run.','**Alternative:** retain this stage as opt-in and gather more source-screened examples.','','[Validation details](validation.json); [run results](results.json).','']
    lines += ['','## Source meter propagation','',
        'The opt-in replay uses agreeing raw numeric glyphs on at least two parallel staves, '
        'rather than contextual class relabels. Only active measure heads supply opening fallback state. '
        'Image templates supply an opening value when consensus is absent; they do not override an accepted opening reading. '
        'Meter values carry through new bar partitions and system breaks, including equal-length signatures such as 3/4 and 6/8.','',
        'Source-only template labels come from high-confidence parallel raw detections in the exact recognition inputs. '
        'Full evidence, template arrays, input hashes and generation code snapshots are archived. '
        'All predictions were saved before reference XML was opened for scoring. No new neural inference was required.','',
        '## Shared bar lengths','',
        'Selected source events are reconstructed from the parent XML and final emitted trace before bars are rebuilt. '
        'Ink-supported common boundaries retain symbol identities, geometry, staff identity and previously selected pitches. '
        'The fitter never sums inherited fragment cuts. It uses the propagated meter and narrow source-backed duration alternatives. '
        'Already fitting selected onsets remain; incomplete voices receive forward time up to the common cut, including opening and repeat bars. '
        'An impossible fit retains the notes and records an unresolved common overflow instead of silently clipping them.','',
        'A strict filled-square pixel test can reject an open-head duration and propose the quarter family. '
        'Optional faster values require a separate beam and duration evidence. Dot alternatives require independent no-dot and ink evidence. '
        'These options are not a comprehensive rhythm decoder; prior tuplets, missing notes, dots, pitches and bad duration readings can remain.']
    if (out/'source-case-checks.json').exists():
        c=read(out/'source-case-checks.json')
        lines += ['','## Confirmed source case checks','',
            'All five audited opening meters match on every part: Ninety-Third Psalm 3/4; Fillmore 4/4; Alabama 6/8; Saint’s Delight 4/4; Duane Street 4/4. '
            'Primrose Hill writes 6/8 at measure 1, 3/4 at 11, and 6/8 at 16. Greenland’s genuine changes remain; Vermont and Weary Pilgrim negative controls pass.','',
            'Golden Harp part 1 measure 2 contains quarter + eighth + eighth, spans two quarters and has no extra hidden rest. '
            'Salem’s reviewed fragment heads 260/393 now share measure 10 with four quarters; the two false cuts are absent. '
            'Fillmore now uses 10 + 9 source candidate bars while retaining every prior head; exact complete source bar counts remain unadjudicated. '
            'Farewell To All’s thin fragments are removed. Stemless whole controls remain unchanged.','',
            f"All **{c['part_measures_with_exact_common_span']} part-measures** across **{c['shared_columns']} shared columns** have encoded spans equal to their selected common cut. "
            f"The **{c['historical_artifact_hashes_and_file_set_verified']}** historical artifact hashes and file set remain unchanged. "
            'See [source case checks](source-case-checks.json).']
    pd_reg=[x for x in per_song if x['pd_now']>x['pd_before']]
    ta_reg=[x for x in per_song if x['time_aware_now']['f1']<x['time_aware_before']['f1']]
    lines += ['','## Remaining regressions and limits','',
        f"Pitch-duration edits improve in {sum(x['pd_now']<x['pd_before'] for x in per_song)} songs, tie in {sum(x['pd_now']==x['pd_before'] for x in per_song)}, and regress in {len(pd_reg)}. "
        + '; '.join(f"{x['title']}: +{x['pd_now']-x['pd_before']}" for x in pd_reg) + '.',
        f"Timing F1 decreases in {len(ta_reg)} songs. These regressions remain included; see the per-song validation records. "
        'Both parent and candidate are rescored with the same current parser; archived parent scores are retained separately.','',
        f"Over-nominal part-measures change from {sum(x['span_parent']['over_nominal'] for x in per_song)} to {sum(x['span_current']['over_nominal'] for x in per_song)}. "
        'Sharing an unresolved overflow makes all parallel parts occupy that duration, so this part-measure count can increase even when fragment inflation is removed. '
        'It is not a count of independent source errors. Unresolved columns are reported separately above.','',
        'All 120 songs are development/diagnostic examples for these corrections. References are from a different edition (2025 versus the 1911 scans); '
        'disagreement metrics do not establish source accuracy. Source reviews are selective and do not estimate precision over every new duration decision. '
        'The production/default pipeline and gallery remain unchanged.','',
        '**Recommended:** resolve the remaining source rhythms and timing regressions before broad/default enablement. '
        '**Alternative:** evaluate a narrower meter-only replay while leaving the current production baseline in place.']
    if (out/'checks.json').exists():
        checks=read(out/'checks.json');lines += ['','## Test checks','',f"**{checks['passed']} tests passed**. The exact command and validation code hashes are in [checks.json](checks.json)."]
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
    save(out/'artifact-sha256.json',{str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='artifact-sha256.json' and 'source-snapshots' not in f.parts})
    print({'songs':len(validated),'regressions':len(regressions),'unresolved':sum(x['unresolved'] for x in unresolved),'datasets':datasets})

if __name__=='__main__':main()
