"""Replay saved proposals with source rhythm constraints and system reflow.

No neural inference. Generate the complete selected batch before reading any
reference XML; keep prior artifacts immutable and record source-only choices.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image

from run_missing_note_proposals import baseline, LATEST
from run_local_recovery import (ROOT, read, save, sha, samples, load_frozen, local_write,
    conventional_score, compare)
from replay_writer_trace import _reading
from reader_trace import serialize_reading, capture_writer_trace
from bar_recovery import capture_built
from proposal_rhythm_policy import constrain_proposal_rhythms, restore_lossy_rhythm_bars
from source_systems import group_source_systems
from source_reflow import (collapsed_bar_evidence, segment_source_bars, source_meter,
                           reflow_transform, emitted_head_ids)

PROPOSALS = ROOT/'experiments/missing-proposals/final-d190393b6a83'


def replay(rd, trace, image, obs, prior_pass, constraints):
    support = {int(k): v for k, v in trace['image_verifications'].items()
               if v.get('note_proposal_supported')}
    with capture_built() as passes:
        xml, emitted, details = local_write(rd, image, obs, prior_pass, note_rest=True,
            proposal_verifications=support, duration_constraints=constraints)
    return xml, emitted, details, next(p for p in reversed(passes) if p['xml'] == xml)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--titles', nargs='+')
    p.add_argument('--tag', default='pilot')
    args = p.parse_args()
    selected = [s for s in samples() if not args.titles or s['title'] in args.titles]
    code = list(ROOT.glob('*.py')) + list((ROOT.parents[1]/'copisteria/src/copisteria').rglob('*.py'))
    inputs = [PROPOSALS/'results.json', PROPOSALS/'predictions-complete.json', LATEST/'results.json']
    for s in selected:
        inputs += [ROOT/s['input'], ROOT/s['baseline_trace'], ROOT/s['old_prediction'],
                   (ROOT/s['old_prediction']).with_suffix('.trace.json')]
        inputs += [PROPOSALS/'predictions'/f"{s['id']}{suffix}" for suffix in ('.musicxml','.trace.json')]
        inputs += [LATEST/'note_rest'/f"{s['id']}{suffix}" for suffix in ('.musicxml','.trace.json')]
        cache = ROOT/('reader-gallery/cache' if s['dataset']=='development100' else 'experiments/bar-fitting/unused20/cache')
        inputs += [cache/f"{s['id']}.{v}.json" for v in ('base','staff16')]
    provenance = {str(f.relative_to(ROOT.parents[1])): sha(f) for f in sorted(set(code+inputs))}
    key = hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    out = ROOT/'experiments/proposal-rhythm'/f'{args.tag}-{key[:12]}'
    for f in code:
        dest = out/'source-snapshots'/f.relative_to(ROOT.parents[1])
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
    frozen = load_frozen();results=[]
    old_results = {r['id']:r for r in read(PROPOSALS/'results.json')['samples']}
    for j,s in enumerate(selected,1):
        sid=s['id'];dest=out/'predictions'/f'{sid}.musicxml';record=out/'records'/f'{sid}.json'
        if record.exists():
            r=read(record);assert r['experiment_key']==key and sha(dest)==r['sha256'];results.append(r);continue
        start=time.perf_counter();print(f'[{j}/{len(selected)}] {s["title"]}',flush=True)
        source=Image.open(ROOT/s['input']).convert('L');image=source
        if s['layout_choice']=='normalized':
            from copisteria.front import clean_page
            image=Image.fromarray(clean_page(np.asarray(source)))
        _,obs,prior_pass,_=baseline(s,source,image,frozen)
        t=read(PROPOSALS/'predictions'/f'{sid}.trace.json')
        for a in t['new_note_proposals']:
            if a['decision']=='visual_context_supported':
                v=a['visual_alternative']['record']
                obs += [{'cls':k,'xyxy':a['box'],'conf':v['objectness_probability']*p}
                        for k,p in v['class_probabilities'].items() if k.startswith('note_')]
        constraints={int(k):set(v) for k,v in t['proposal_duration_constraints'].items()}
        rd=_reading(copy.deepcopy(t),source)
        xml,emitted,details,selected_pass=replay(rd,t,image,obs,prior_pass,constraints)
        assert xml==(PROPOSALS/'predictions'/f'{sid}.musicxml').read_text(), sid+' proposal replay'
        assert emitted==t['writer'],sid+' emitted replay'
        before_rhythm=copy.deepcopy(rd);prior_constraints=copy.deepcopy(constraints)
        unchanged=(xml,emitted,details,selected_pass)
        rhythm=constrain_proposal_rhythms(rd,t['new_note_proposals'],image,constraints)
        if any(d['action'] in ('direct_visual_duration','reject_unsupported_context_dot') for d in rhythm):
            xml,emitted,details,selected_pass=replay(rd,t,image,obs,prior_pass,constraints)
            while emitted_head_ids(t['writer'])-emitted_head_ids(emitted):
                lost=sorted(emitted_head_ids(t['writer'])-emitted_head_ids(emitted))
                assert restore_lossy_rhythm_bars(rd,before_rhythm,constraints,prior_constraints,rhythm,lost)
                if all(d.get('rejected') or d['action']=='check_context_dot' for d in rhythm):
                    rd=before_rhythm;xml,emitted,details,selected_pass=unchanged
                    break
                xml,emitted,details,selected_pass=replay(rd,t,image,obs,prior_pass,constraints)
        original_layout=copy.deepcopy(rd.layout)
        grouping=group_source_systems(rd.layout)
        source_details={'grouping':asdict(grouping),'rhythm_decisions':rhythm,'pitch_reflow':[]}
        if grouping.changed:
            from copisteria import write
            collapsed=collapsed_bar_evidence(rd);source_details['collapsed_bar_evidence']=collapsed
            segmented=False
            if collapsed:
                candidate=copy.deepcopy(rd)
                segmentation=segment_source_bars(candidate,image)
                hook=write._page_meter;meter=source_meter(candidate,selected_pass['opening'])
                write._page_meter=lambda *a:meter
                try:
                    with capture_writer_trace() as trial:
                        candidate_xml=write.write(candidate,image=image)
                finally:write._page_meter=hook
                lost=sorted(emitted_head_ids(emitted)-emitted_head_ids(trial))
                segmentation.update(missing_previous_heads=lost,source_meter=meter,accepted=not lost)
                source_details['segmentation']=segmentation
                if not lost:
                    rd,xml,emitted=candidate,candidate_xml,trial;segmented=True
            if not segmented:
                transform=reflow_transform(rd,selected_pass,original_layout,source_details['pitch_reflow'])
                hook=write._page_meter;write._page_meter=lambda *a:selected_pass['opening']
                try:
                    with capture_writer_trace() as emitted:
                        xml=write.write(rd,image=image,bar_transform=transform)
                finally:write._page_meter=hook
        lost=sorted(emitted_head_ids(t['writer'])-emitted_head_ids(emitted))
        assert not lost,(sid,'physical head loss',lost)
        root=ET.fromstring(xml)
        pitched=[(n.findtext('pitch/step'),int(n.findtext('pitch/octave')),int(n.findtext('pitch/alter','0')),int(n.findtext('duration','0')))
                 for n in root.findall('.//note') if n.find('pitch') is not None]
        assert pitched==[(e['step'],e['octave'],e['alter'],e['dur']) for e in emitted['emitted'] if e['kind']=='note']
        # Noteheads keep geometry/staff identity even where bars are resegmented.
        for old,new in zip(t['syms'],rd.layout.syms):
            if old['cls']!='measure':
                assert old['box']==list(new.box) and old['staff']==new.staff and old['i']==new.i
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(xml)
        trace={**t,**serialize_reading(rd),'writer':emitted,'rhythm_recovery_details':source_details,
               'rhythm_recovery_local_details':details,
               'rhythm_recovery_duration_constraints':{str(k):sorted(v) for k,v in constraints.items()}}
        save(dest.with_suffix('.trace.json'),trace)
        row={'id':sid,'title':s['title'],'dataset':s['dataset'],'experiment_key':key,
             'prediction':str(dest.relative_to(ROOT)),'sha256':sha(dest),'proposal_exact_replay':True,
             'physical_heads_retained':True,'system_repaired':grouping.changed,
             'source_segmentation_accepted':source_details.get('segmentation',{}).get('accepted',False),
             'rhythm_actions':len(rhythm),'seconds':time.perf_counter()-start}
        save(record,row);results.append(row)
        print(f'  grouped={grouping.changed} segmented={row["source_segmentation_accepted"]} rhythm={len(rhythm)} ({row["seconds"]:.1f}s)',flush=True)
    save(out/'predictions-complete.json',{'experiment_key':key,'sha256':provenance,
        'references_opened_during_generation':False,'ids':[s['id'] for s in selected]})
    for row,s in zip(results,selected):
        reference=ROOT/s['reference'];assert sha(reference)==s['reference_sha256']
        row['proposal_comparison']=old_results[row['id']]['comparison']
        row['baseline_comparison']=old_results[row['id']]['baseline_comparison']
        row['comparison']=compare(conventional_score(reference,s['voice_count']),
                                  conventional_score(ROOT/row['prediction'],s['voice_count']))
    save(out/'results.json',{'experiment_key':key,'samples':results,'provenance':provenance})
    print(out,flush=True)

if __name__=='__main__':main()
