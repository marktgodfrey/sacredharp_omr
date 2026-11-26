"""Source-constrained repair of rhythm failures, retaining physical heads."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path
import numpy as np
from run_local_recovery import ROOT,read,save,sha,samples,compare,conventional_score
from run_source_timing_recovery import recover,PARENT
from source_meter_ink import build_meter_templates
from reader_trace import _json_safe

PREVIOUS=ROOT/'experiments/source-timing/final-0eaa4b28dd55'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--titles',nargs='+');p.add_argument('--tag',default='pilot');a=p.parse_args()
    all_samples=samples();selected=[s for s in all_samples if not a.titles or s['title'] in a.titles]
    code=list(ROOT.glob('*.py'))+list((ROOT.parents[1]/'copisteria/src/copisteria').rglob('*.py'))
    inputs=[d/f for d in (PARENT,PREVIOUS) for f in ('results.json','artifact-sha256.json')]
    inputs += [ROOT/'reader-gallery/results.json',ROOT/'experiments/bar-fitting/unused20/manifest.json',
        ROOT/'experiments/bar-fitting/unused20/results.json',ROOT/'experiments/reader-v2/replay_bar_fit/results.json']
    for s in all_samples:inputs += [ROOT/s['input'],ROOT/s['baseline_trace']]
    for s in selected:inputs += [d/'predictions'/f"{s['id']}{ext}" for d in (PARENT,PREVIOUS) for ext in ('.musicxml','.trace.json')]
    provenance={str(f.relative_to(ROOT.parents[1])):sha(f) for f in sorted(set(inputs+code))}
    key=hashlib.sha256(json.dumps({'sha256':provenance,'ids':[s['id'] for s in selected]},sort_keys=True).encode()).hexdigest()
    out=ROOT/'experiments/rhythm-resolution'/f'{a.tag}-{key[:12]}'
    for f in code:
        dest=out/'source-snapshots'/f.relative_to(ROOT.parents[1]);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
    print('Building source-only meter templates',flush=True);bank,metadata=build_meter_templates(all_samples)
    arrays={};bank_rows={}
    for label,entries in bank.items():
        bank_rows[label]=[]
        for i,e in enumerate(entries):
            arrays[label.replace('/','_')+f'_{i}']=e['template'];bank_rows[label].append({k:v for k,v in e.items() if k!='template'})
    np.savez_compressed(out/'source-meter-templates.npz',**arrays)
    save(out/'source-meter-templates.json',{'build':metadata,'templates':bank_rows})
    results=[]
    for i,s in enumerate(selected,1):
        dest=out/'predictions'/f"{s['id']}.musicxml";rec=out/'records'/f"{s['id']}.json"
        if rec.exists():
            r=read(rec);assert r['experiment_key']==key and sha(dest)==r['sha256'] and sha(dest.with_suffix('.trace.json'))==r['trace_sha256'];results.append(r);continue
        print(f'[{i}/{len(selected)}] {s["title"]}',flush=True);start=time.perf_counter()
        xml,trace,details=recover(s,bank,rhythm_resolution=True)
        dest.parent.mkdir(exist_ok=True,parents=True);dest.write_text(xml);save(dest.with_suffix('.trace.json'),_json_safe(trace))
        r={'id':s['id'],'title':s['title'],'dataset':s['dataset'],'experiment_key':key,'seconds':time.perf_counter()-start,
           'prediction':str(dest.relative_to(ROOT)),'sha256':sha(dest),'trace_sha256':sha(dest.with_suffix('.trace.json')),**details}
        save(rec,r);results.append(r);print(f"  unresolved={r['unresolved_columns']}/{r['columns']} changes={r['duration_changes']} ({r['seconds']:.1f}s)",flush=True)
    changed=[str(f) for f in code if sha(f)!=provenance[str(f.relative_to(ROOT.parents[1]))]]
    assert not changed,('generation code changed during the batch; preserve as diagnostic and rerun',changed)
    save(out/'predictions-complete.json',{'experiment_key':key,'sha256':provenance,'ids':[s['id'] for s in selected],
        'source_meter_templates_sha256':sha(out/'source-meter-templates.npz'),'references_opened_during_generation':False,
        'generation_code_unchanged_through_complete_batch':True})
    for r,s in zip(results,selected):
        ref=ROOT/s['reference'];assert sha(ref)==s['reference_sha256'];parsed=conventional_score(ref,s['voice_count'])
        r['baseline_comparison']=compare(parsed,conventional_score(PREVIOUS/'predictions'/f"{s['id']}.musicxml",s['voice_count']))
        r['proposal_comparison']=compare(parsed,conventional_score(PARENT/'predictions'/f"{s['id']}.musicxml",s['voice_count']))
        r['comparison']=compare(parsed,conventional_score(ROOT/r['prediction'],s['voice_count']))
    save(out/'results.json',{'experiment_key':key,'samples':results,'provenance':provenance,'previous_stage':str(PREVIOUS.relative_to(ROOT))})
    print(out,flush=True)

if __name__=='__main__':main()
