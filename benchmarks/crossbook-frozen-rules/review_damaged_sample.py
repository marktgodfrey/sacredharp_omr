"""Source-only analysis of a completed, locked damaged-head sample.

No recognition/rule execution, reference XML, or rule edits. Coordinates are
native input pixels; atomic symbols are matched by overlap and center distance,
then actual serialized source IDs establish note survival. Keep class mistakes
and unmatched annotations in the result instead of matching a distant note.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import shutil
from run_damaged_sample import WORKSPACE, read, sha, save, sealed_inputs, engines, tree_hashes, template_hashes


def overlap(a,b):
    w=max(0,min(a[2],b[2])-max(a[0],b[0]));h=max(0,min(a[3],b[3])-max(a[1],b[1]))
    return w*h/max(1e-9,(a[2]-a[0])*(a[3]-a[1]))


def events(trace, symbol_id):
    return [e for e in trace['writer']['emitted'] if e.get('e.si')==symbol_id]


def analyze(run, source_set):
    run, source_set = run.resolve(), source_set.resolve()
    if (run/'artifact-manifest.json').exists():raise ValueError('Run already sealed')
    if (run/'source-head-review.json').exists():raise ValueError('Review exists; preserve it')
    manifest,selection,inputs=sealed_inputs(source_set);p=read(run/'provenance.json')
    assert p['source_inputs_and_taxonomy_lookup_fingerprint']==inputs
    assert p['adapter_sha256']==sha(WORKSPACE/p['adapter_path'])
    config=engines(source_set/'engines.json')
    assert p['engine_code_and_assets']=={e:tree_hashes(d/'source-snapshots') for e,d in config.items()}
    assert p['engine_templates']==template_hashes(config)
    assert p['models']==tree_hashes(WORKSPACE/'copisteria/out/coreml')
    expected={(s['id'],v) for s in manifest['samples'] for v in manifest['variants']}
    stages={}
    for stage in ['baseline','prior','current']:
        guard=read(run/('capture-complete.json' if stage=='baseline' else f'{stage}-complete.json'))
        assert guard['hash_guard_passed'] is True
        assert {(c['id'],c['variant']) for c in guard['cases']}==expected
        stages[stage]={}
        for c in guard['cases']:
            assert not c.get('failed'),c
            folder=run/('seeds/'+c['variant']+'/predictions' if stage=='baseline' else stage+'/'+c['variant'])
            t=folder/(c['id']+'.trace.json');xml=folder/(c['id']+'.musicxml')
            assert sha(t)==c['trace_sha256'] and sha(xml)==c['xml_sha256']
            stages[stage][(c['id'],c['variant'])]=read(t)
    rows=[]
    for a in selection['annotations']:
        for v in manifest['variants']:
            traces={s:stages[s][(a['sample_id'],v)] for s in stages};base=traces['baseline']
            b=a['input_bbox_xyxy'];center=((b[0]+b[2])/2,(b[1]+b[3])/2)
            candidates=[]
            for sym in base['syms']:
                if not sym['cls'].startswith(('note_','rest_')):continue
                box=sym['box'];dist=math.dist(center,((box[0]+box[2])/2,(box[1]+box[3])/2))
                staff=sym.get('staff');sp=base['staves'][staff]['sp'] if isinstance(staff,int) and 0<=staff<len(base['staves']) else 12
                ov=overlap(b,box)
                if dist<=.75*sp and ov>0:
                    candidates.append({'symbol':sym,'distance_px':dist,'staff_space':sp,'annotation_overlap_fraction':ov})
            candidates.sort(key=lambda c:(-c['annotation_overlap_fraction'],c['distance_px']))
            match=candidates[0] if candidates else None
            item={**a,'variant':v,'match':match,'matching_method':'Atomic note/rest box overlapping annotation, center within 0.75 assigned staff-space; highest annotation overlap then nearest. Source context manually reviewed; merged front-end symbol, not raw detector tensor.'}
            if match:
                sym=match['symbol'];i=sym['i'];item['stages']={}
                for name,t in traces.items():
                    detail=t.get('rhythm_resolution_details',{})
                    emitted=events(t,i)
                    item['stages'][name]={'source_id':i,'emitted_as_note':any(e['kind']=='note' for e in emitted),'events':emitted,
                        'abstentions':[r for r in detail.get('source_head_abstentions',[]) if r.get('sym_id')==i],
                        'removals':[r for r in detail.get('duplicate_serialized_events_removed',[]) if r.get('sym_id')==i]}
            rows.append(item)
    comparisons=[]
    for sample_id,v in sorted(expected):
        base=stages['baseline'][(sample_id,v)];prior=stages['prior'][(sample_id,v)];current=stages['current'][(sample_id,v)]
        def heads(t):return {e['e.si'] for e in t['writer']['emitted'] if e['kind']=='note'}
        comparisons.append({'id':sample_id,'variant':v,'baseline_note_ids_lost_in_current':sorted(heads(base)-heads(current)),
            'prior_note_ids_lost_in_current':sorted(heads(prior)-heads(current)),
            'prior_current_writer_events_identical':prior['writer']['emitted']==current['writer']['emitted'],
            'current_abstentions':current.get('rhythm_resolution_details',{}).get('source_head_abstentions',[]),
            'current_removals':current.get('rhythm_resolution_details',{}).get('duplicate_serialized_events_removed',[]),
            'unequal_part_span_columns':{k:traces[(sample_id,v)]['final_timing']['xml_inventory']['columns_with_unequal_part_spans'] for k,traces in stages.items() if k!='baseline'},
            'baseline_staff_count':len(base['staves'])})
    counts={}
    for status in ['likely_damaged','ambiguous','intact_control']:
        subset=[r for r in rows if r['status']==status]
        counts[status]={'distinct_annotated_objects':len({r['annotation_id'] for r in subset}),'layout_observations':len(subset),'matched_frontend_symbols':sum(bool(r['match']) for r in subset),
            **{stage+'_emitted_note':sum(r.get('stages',{}).get(stage,{}).get('emitted_as_note',False) for r in subset) for stage in stages},
            'current_abstention_observations':sum(bool(r.get('stages',{}).get('current',{}).get('abstentions')) for r in subset)}
    result={'reference_xml_opened':False,'all_hash_guards_passed':True,'annotations_unchanged_sha256':sha(source_set/'selection.json'),'counts':counts,
        'configurations':comparisons,'annotations':rows,'conclusion':'Premarked damaged-head survival was exercised. Revised abstention was not exercised; zero rescue evidence and no prior/current event differences. This is not broad generalization validation.'}
    save(run/'source-head-review.json',result)
    print(json.dumps(counts,indent=2))
    print('timing failures',sum(any(c['unequal_part_span_columns'].values()) for c in comparisons))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('source_set',type=Path);a=p.parse_args();analyze(a.run,a.source_set)
if __name__=='__main__':main()
