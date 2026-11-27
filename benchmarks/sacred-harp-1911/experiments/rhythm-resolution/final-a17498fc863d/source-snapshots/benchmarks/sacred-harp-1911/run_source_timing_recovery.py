"""Opt-in source meter propagation and common-bar timing from saved readings.

All source-linked selected notes are reconstructed before fitting. Generation
uses no reference transcription, case IDs, target counts or song exclusions.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import shutil
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image

from run_local_recovery import ROOT,read,save,sha,samples,compare,conventional_score
from replay_writer_trace import _reading
from reader_trace import serialize_reading,_json_safe
from source_saved_events import source_saved_events
from source_bar_grid import rebuild_source_bars
from source_meter_state import source_meter_state,apply_source_meter_state
from source_meter_ink import build_meter_templates,opening_meter_from_ink
from source_duration_options import source_duration_options
from source_bar_fit import source_bar_transform
from source_timing_trace import write_timed
from source_reflow import emitted_head_ids

PARENT=ROOT/'experiments/proposal-rhythm/final-0318d4f06bb9'


def opening_event(state):
    return next((e for e in state['events'] if (e['system'],e['column'])==(0,0)),None)


def previous_opening(xml):
    values=[p.findtext('.//time/beats')+'/'+p.findtext('.//time/beat-type') for p in ET.fromstring(xml).findall('part')
            if p.find('.//time/beats') is not None]
    return Counter(values).most_common(1)[0][0] if values else '4/4'


def serial_meter(state):
    return {**state,'meter_by_staff_bar':[{'staff':k,'bar':b,'meter':v} for (k,b),v in state['meter_by_staff_bar'].items()]}


def recover(s,bank,*,rhythm_resolution=False):
    sid=s['id'];trace=read(PARENT/'predictions'/f'{sid}.trace.json')
    old_xml=(PARENT/'predictions'/f'{sid}.musicxml').read_text()
    source=Image.open(ROOT/s['input']).convert('L');rd=_reading(copy.deepcopy(trace),source)
    events,source_metadata=source_saved_events(trace,old_xml)
    duplicate_events=[]
    if rhythm_resolution:
        from source_rhythm_resolution import unique_physical_events
        events,duplicate_events=unique_physical_events(events,rd,np.asarray(source))
    before=source_meter_state(rd);before_open=opening_event(before)
    flat=[e for evs in events.values() for e in evs]
    ink=None;ink_probe=None;saved_opening=previous_opening(old_xml)
    if before_open is None:
        query_bank=bank
        if rhythm_resolution:
            query_bank={k:[e for e in es if e.get('sample_id')!=s['id']] for k,es in bank.items()}
            query_bank={k:v for k,v in query_bank.items() if v}
        ink=opening_meter_from_ink(rd,source,query_bank,events=flat)
        ink_probe=copy.deepcopy(ink)
        if rhythm_resolution and ink and ink['meter']!=saved_opening:
            required=max(2,int(np.ceil(.75*len(rd.layout.systems[0].staves))))
            if ink['consensus_staff_count']<required:
                ink_probe.update(accepted=False,abstention='insufficient_parallel_support_to_override_saved_opening',required_staff_count=required)
                ink=None
    opening=ink['meter'] if ink else before_open['meter'] if before_open else saved_opening
    grid=rebuild_source_bars(rd,source,events,old_xml)
    # Transfer trusted opening evidence independently of old measure-box IDs.
    for sid in rd.layout.systems[0].staves:
        head=rd.layout.staves[sid].bars[0]
        rd.tok[head]['time']={'v':opening,'p':1.,'source_meter_transfer':True}
    state=source_meter_state(rd)
    apply_source_meter_state(rd,state)
    # Explicit carry also covers an opening whose only evidence is the image
    # fallback; later accepted local glyph changes keep their distinct values.
    visible={(e['system'],e['column']) for e in state['events'] if any(r['source']=='raw_meter_glyph' for r in e['evidence'])}
    if ink:visible.add((0,0))
    if rhythm_resolution:
        from source_rhythm_resolution import resolved_duration_options
        choices=resolved_duration_options(rd,np.asarray(source),events)
    else:choices=source_duration_options(rd,np.asarray(source),events)
    parent_measures={int(e['source_si']):int(e['measure'])-1 for e in source_metadata if e['kind']=='event'}
    if rhythm_resolution:
        parent_measures={}
        for e in source_metadata:
            if e['kind']=='event':parent_measures.setdefault(int(e['source_si']),int(e['measure'])-1)
    first_measures=[m for p in ET.fromstring(old_xml).findall('part') for m in p.findall('measure')[:1]]
    parent_pickup=sum(m.get('implicit')=='yes' for m in first_measures)>len(first_measures)/2
    decisions=[];base=source_bar_transform(rd,events,choices,decisions,
        parent_measures=parent_measures,opening_pickup=parent_pickup,refine_timing=rhythm_resolution,
        reset_onset_ids=[d['note_kept'] for d in duplicate_events if 'note_kept' in d])
    def transform(built,meter):
        for measures in built:
            for measure in measures:
                for row in measure['staves']:
                    if row is None:continue
                    st=rd.layout.staves[row['staff']]
                    if (st.system,rd.layout.column(row['staff'],row['bar'])) in visible:row['marks']['meter']=True
        return base(built,meter)
    xml,emitted,timing,selected=write_timed(rd,image=source,opening=opening,bar_transform=transform)
    lost=sorted(emitted_head_ids(trace['writer'])-emitted_head_ids(emitted))
    non_heads={d['sym_id'] for d in duplicate_events if
               (d['reason']=='beam_stroke_misread_as_notehead' and d.get('source_geometry_evidence',{}).get('beam_region'))
               or (d['reason']=='empty_source_box_misread_as_notehead' and d.get('source_geometry_evidence',{}).get('empty_head_box'))}
    assert not set(lost)-non_heads,(s['id'],'lost physical heads',lost)
    for a,b in zip(trace['syms'],rd.layout.syms):
        if a['cls']!='measure':assert a['i']==b.i and a['box']==list(b.box) and a['staff']==b.staff
    root=ET.fromstring(xml)
    pitched=[(n.findtext('pitch/step'),int(n.findtext('pitch/octave')),int(n.findtext('pitch/alter','0')),int(n.findtext('duration','0')))
             for n in root.findall('.//note') if n.find('pitch') is not None]
    assert pitched==[(e['step'],e['octave'],e['alter'],e['dur']) for e in emitted['emitted'] if e['kind']=='note']
    saved={**trace,**serialize_reading(rd),'writer':emitted,
        'source_meter_state':serial_meter(state),'source_meter_before_resegmentation':serial_meter(before),
        'source_opening_ink_evidence':ink,'source_opening_ink_probe':ink_probe,'source_bar_grid':grid,'source_duration_options':choices,
        'source_bar_fit_decisions':decisions,'final_timing':timing,'source_selected_events':_json_safe(selected['built']),
        'saved_source_event_metadata':source_metadata,
        'rhythm_resolution_details':{'enabled':rhythm_resolution,'duplicate_serialized_events_removed':duplicate_events},
        'parent_stage':str(PARENT.relative_to(ROOT)),
        'prior_evidence_geometry_stage':'Input token/proposal evidence retained; final bar identities are in syms/staves/systems and final_timing.'}
    saved['prior_timing_metadata']={k:saved.pop(k) for k in ('fixed_column_cuts','fixed_opening_meter') if k in saved}
    return xml,saved,{'physical_heads_retained':True,'opening_meter':opening,
        'source_meter_transitions':[(e['system'],e['column'],e['meter']) for e in state['transitions']],
        'unresolved_columns':sum(not d['resolved'] for d in decisions),'columns':len(decisions),
        'duration_changes':sum(len(v.get('duration_actions',[])) for d in decisions for v in d['voice_fits'])}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--titles',nargs='+');p.add_argument('--tag',default='pilot');args=p.parse_args()
    all_samples=samples();selected=[s for s in all_samples if not args.titles or s['title'] in args.titles]
    code=list(ROOT.glob('*.py'))+list((ROOT.parents[1]/'copisteria/src/copisteria').rglob('*.py'))
    inputs=[PARENT/'results.json',PARENT/'artifact-sha256.json',ROOT/'reader-gallery/results.json',
        ROOT/'experiments/bar-fitting/unused20/manifest.json',ROOT/'experiments/bar-fitting/unused20/results.json',
        ROOT/'experiments/reader-v2/replay_bar_fit/results.json']
    for s in all_samples:inputs += [ROOT/s['input'],ROOT/s['baseline_trace']]
    for s in selected:inputs += [PARENT/'predictions'/f"{s['id']}{ext}" for ext in ('.musicxml','.trace.json')]
    provenance={str(f.relative_to(ROOT.parents[1])):sha(f) for f in sorted(set(inputs+code))}
    key=hashlib.sha256(json.dumps({'sha256':provenance,'ids':[s['id'] for s in selected]},sort_keys=True).encode()).hexdigest()
    out=ROOT/'experiments/source-timing'/f'{args.tag}-{key[:12]}'
    for f in code:
        dest=out/'source-snapshots'/f.relative_to(ROOT.parents[1]);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
    print('Building source-image meter templates',flush=True)
    bank,bank_metadata=build_meter_templates(all_samples)
    templates={};template_meta={}
    for label,rows in bank.items():
        template_meta[label]=[]
        for i,row in enumerate(rows):
            name=label.replace('/','_')+f'_{i}';templates[name]=row['template']
            template_meta[label].append({k:v for k,v in row.items() if k!='template'})
    np.savez_compressed(out/'source-meter-templates.npz',**templates)
    save(out/'source-meter-templates.json',{'build':bank_metadata,'templates':template_meta})
    results=[];parent={r['id']:r for r in read(PARENT/'results.json')['samples']}
    for j,s in enumerate(selected,1):
        sid=s['id'];dest=out/'predictions'/f'{sid}.musicxml';rec=out/'records'/f'{sid}.json'
        if rec.exists():
            row=read(rec);assert row['experiment_key']==key and sha(dest)==row['sha256'] and sha(dest.with_suffix('.trace.json'))==row['trace_sha256'];results.append(row);continue
        print(f'[{j}/{len(selected)}] {s["title"]}',flush=True);start=time.perf_counter()
        xml,trace,details=recover(s,bank)
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(xml);save(dest.with_suffix('.trace.json'),_json_safe(trace))
        row={'id':sid,'title':s['title'],'dataset':s['dataset'],'experiment_key':key,
            'prediction':str(dest.relative_to(ROOT)),'sha256':sha(dest),'trace_sha256':sha(dest.with_suffix('.trace.json')),
            'seconds':time.perf_counter()-start,**details}
        save(rec,row);results.append(row)
        print(f"  meter={row['opening_meter']} unresolved={row['unresolved_columns']}/{row['columns']} changes={row['duration_changes']} ({row['seconds']:.1f}s)",flush=True)
    save(out/'predictions-complete.json',{'experiment_key':key,'sha256':provenance,
        'source_meter_templates_sha256':sha(out/'source-meter-templates.npz'),
        'references_opened_during_generation':False,'ids':[s['id'] for s in selected]})
    for row,s in zip(results,selected):
        ref=ROOT/s['reference'];assert sha(ref)==s['reference_sha256']
        parsed_ref=conventional_score(ref,s['voice_count'])
        row['parent_archived_comparison']=parent[row['id']]['comparison']
        row['baseline_comparison']=compare(parsed_ref,conventional_score(PARENT/'predictions'/f"{s['id']}.musicxml",s['voice_count']))
        row['comparison']=compare(parsed_ref,conventional_score(ROOT/row['prediction'],s['voice_count']))
    save(out/'results.json',{'experiment_key':key,'samples':results,'provenance':provenance})
    print(out,flush=True)

if __name__=='__main__':main()
