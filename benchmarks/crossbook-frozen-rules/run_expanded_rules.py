"""Capture and replay immutable rhythm-rule snapshots on an expanded cross-book set.

Only the adapter is new. Model, writer, rhythm rules, and meter templates come
from frozen checkpoints. All predictions precede reference scoring. No target
title, voice count, reference, or manually reviewed meter enters prediction.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import traceback
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parents[1]
HISTORICAL=WORKSPACE/'benchmarks/historical-sacred-harp'
PILOT=HISTORICAL/'runs/pilot-coreml-2026-11-26'
EXPERIMENTS=WORKSPACE/'benchmarks/sacred-harp-1911/experiments/rhythm-resolution'
ENGINES={'prior':EXPERIMENTS/'final-a17498fc863d',
         'current':EXPERIMENTS/'dot-head-evidence-20261126-b6512a5f402d'}
VARIANTS=('default','clean_layout')
SOURCE_MANIFEST=ROOT/'source-sets/two-books-expanded-20261126/manifest.json'
CACHE=ROOT/'runs/pilot14-frozen-dot-head-20261126'


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def engine_files(engine):
    root=ENGINES[engine]/'source-snapshots'
    return {str(p.relative_to(WORKSPACE)):sha(p) for p in sorted(root.rglob('*.py'))}


def activate(engine):
    snapshot=ENGINES[engine]/'source-snapshots'
    sys.path.insert(0,str(snapshot/'copisteria/src'))
    sys.path.insert(0,str(snapshot/'benchmarks/sacred-harp-1911'))
    # The Python-only archive omits non-code taxonomy assets. Redirect that
    # resource lookup without editing the archived vocabulary or rule bodies.
    import copisteria.paths as resources
    resources.REPO=WORKSPACE/'copisteria'
    return snapshot


def sealed_inputs():
    manifest=read(SOURCE_MANIFEST)
    inputs={str((HISTORICAL/s[k]).relative_to(WORKSPACE)):sha(HISTORICAL/s[k])
            for s in manifest['samples'] for k in ('source','input')}
    inputs[str(SOURCE_MANIFEST.relative_to(WORKSPACE))]=sha(SOURCE_MANIFEST)
    taxonomy=WORKSPACE/'copisteria/models/yolo_v7_taxonomy.json'
    inputs[str(taxonomy.relative_to(WORKSPACE))]=sha(taxonomy)
    return manifest,inputs


def same_score_xml(left,right):
    def normalized(path):
        root=ET.parse(path).getroot()
        for enc in root.findall('.//encoding'):
            for date in enc.findall('encoding-date'):enc.remove(date)
        return ET.canonicalize(ET.tostring(root,encoding='unicode'),strip_text=True)
    return normalized(left)==normalized(right)


def capture(out):
    if out.exists():raise FileExistsError('Use a new tag; run already exists')
    activate('current')
    from copisteria import write
    from copisteria.coreml_runtime import run
    from reader_trace import capture_writer_trace,serialize_reading
    from source_saved_events import source_saved_events
    manifest,inputs=sealed_inputs();models=WORKSPACE/'copisteria/out/coreml'
    model_hashes={str(p.relative_to(models)):sha(p) for p in sorted(models.rglob('*')) if p.is_file()}
    provenance={'adapter_path':str(Path(__file__).relative_to(WORKSPACE)),
                'adapter_sha256':sha(Path(__file__)),'source_manifest_sha256':sha(SOURCE_MANIFEST),
                'engine_code':{e:engine_files(e) for e in ENGINES},
                'source_inputs':inputs,'models':model_hashes,'reference_opened_during_generation':False,
                'selection':f'All {len(manifest["samples"])} immutable expanded source samples, both layout variants; no new selection or tuning',
                'prediction_metadata_used':['id','input'],'compute_units':'CPU_ONLY'}
    save(out/'manifest.json',manifest);save(out/'provenance.json',provenance)
    save(out/'adapter-snapshot.json',{'script':Path(__file__).read_text()})
    records=[]
    cache_manifest=read(CACHE/'manifest.json');cache_prov=read(CACHE/'provenance.json')
    cache_complete=read(CACHE/'capture-complete.json')
    cache_records={(r['id'],r['variant']):r for r in cache_complete['cases']}
    taxonomy_key='copisteria/models/yolo_v7_taxonomy.json'
    cache_ok=(cache_complete['hash_guard_passed'] and not cache_complete['references_opened']
              and cache_prov['engine_code']==provenance['engine_code'] and cache_prov['models']==model_hashes
              and inputs[taxonomy_key]==cache_prov['source_inputs'][taxonomy_key])
    cache_samples={s['id']:s for s in cache_manifest['samples']}
    for variant in VARIANTS:
        folder=out/'seeds'/variant/'predictions';folder.mkdir(parents=True)
        for i,sample in enumerate(manifest['samples'],1):
            print(f'capture {variant} {i}/{len(manifest["samples"])} {sample["id"]}',flush=True)
            cached=cache_records.get((sample['id'],variant)) if cache_ok and sample['id'] in cache_samples else None
            cache_keys=[str((HISTORICAL/cache_samples[sample['id']][k]).relative_to(WORKSPACE)) for k in ('source','input')] if sample['id'] in cache_samples else []
            if cached and all(inputs.get(k)==cache_prov['source_inputs'].get(k) for k in cache_keys):
                cxml=CACHE/'seeds'/variant/'predictions'/f'{sample["id"]}.musicxml';ctrace=cxml.with_suffix('.trace.json')
                if sha(cxml)==cached['xml_sha256'] and sha(ctrace)==cached['trace_sha256']:
                    shutil.copy2(cxml,folder/cxml.name);shutil.copy2(ctrace,folder/ctrace.name)
                    report=cxml.with_suffix('.report.json')
                    if report.exists():shutil.copy2(report,folder/report.name)
                    old=PILOT/variant/cxml.name
                    records.append({'id':sample['id'],'variant':variant,'xml_sha256':sha(folder/cxml.name),
                        'trace_sha256':sha(folder/ctrace.name),
                        'sealed_pilot_score_xml_identical':same_score_xml(folder/cxml.name,old) if sample['id'] in {s['id'] for s in read(PILOT/'manifest.json')['samples']} else None,
                        'cache_origin':str(cxml.relative_to(WORKSPACE))})
                    continue
            captured=[];original=write.write
            def traced(rd,*args,**kwargs):
                with capture_writer_trace() as trace:xml=original(rd,*args,**kwargs)
                captured.append({**serialize_reading(rd),'writer':trace})
                return xml
            write.write=traced
            try:
                run(HISTORICAL/sample['input'],models,folder,units='CPU_ONLY',
                    clean_layout=variant=='clean_layout',four_staff=False)
            except Exception:
                save(out/'capture-failure.json',{'sample':sample['id'],'variant':variant,'traceback':traceback.format_exc()})
                raise
            finally:write.write=original
            assert len(captured)==1
            xml=folder/f'{sample["id"]}.musicxml';trace=captured[0]
            source_saved_events(trace,xml.read_text())
            save(xml.with_suffix('.trace.json'),trace)
            old=PILOT/variant/xml.name
            baseline_ids={s['id'] for s in read(PILOT/'manifest.json')['samples']}
            records.append({'id':sample['id'],'variant':variant,'xml_sha256':sha(xml),
                            'trace_sha256':sha(xml.with_suffix('.trace.json')),
                            'sealed_pilot_score_xml_identical':same_score_xml(xml,old) if sample['id'] in baseline_ids else None})
    assert inputs==sealed_inputs()[1]
    assert provenance['engine_code']=={e:engine_files(e) for e in ENGINES}
    assert provenance['adapter_sha256']==sha(Path(__file__))
    assert model_hashes=={str(p.relative_to(models)):sha(p) for p in sorted(models.rglob('*')) if p.is_file()}
    save(out/'capture-complete.json',{'cases':records,'hash_guard_passed':True,'references_opened':False})


def template_bank(engine):
    import numpy as np
    parent=ENGINES[engine];metadata=read(parent/'source-meter-templates.json')['templates']
    with np.load(parent/'source-meter-templates.npz') as arrays:
        return {label:[{**row,'template':arrays[label.replace('/','_')+f'_{i}'].copy()}
                       for i,row in enumerate(rows)] for label,rows in metadata.items()}


def replay(out,engine):
    assert read(out/'capture-complete.json')['hash_guard_passed']
    provenance=read(out/'provenance.json');assert provenance['engine_code'][engine]==engine_files(engine)
    assert provenance['source_inputs']==sealed_inputs()[1]
    assert provenance['adapter_sha256']==sha(Path(__file__))
    activate(engine)
    import run_source_timing_recovery as runner
    from reader_trace import _json_safe
    # Data-source adapter only: use the identical captured baseline event pool.
    # No frozen function body or policy parameter is changed.
    runner.ROOT=WORKSPACE
    bank=template_bank(engine);records=[]
    folder=out/engine
    if folder.exists():raise FileExistsError('Engine output exists; preserve this attempt')
    for variant in VARIANTS:
        runner.PARENT=out/'seeds'/variant
        for i,sample in enumerate(read(out/'manifest.json')['samples'],1):
            print(f'{engine} {variant} {i}/{len(read(out/"manifest.json")["samples"])} {sample["id"]}',flush=True)
            dest=folder/variant/f'{sample["id"]}.musicxml';started=time.perf_counter()
            try:
                xml,trace,details=runner.recover({'id':sample['id'],
                    'input':str((HISTORICAL/sample['input']).relative_to(WORKSPACE))},bank,rhythm_resolution=True)
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(xml)
                save(dest.with_suffix('.trace.json'),_json_safe(trace))
                records.append({'id':sample['id'],'variant':variant,'failed':False,'seconds':time.perf_counter()-started,
                                'xml_sha256':sha(dest),'trace_sha256':sha(dest.with_suffix('.trace.json')),**details})
            except Exception:
                failure={'id':sample['id'],'variant':variant,'failed':True,'traceback':traceback.format_exc()}
                save(dest.with_suffix('.failure.json'),failure);records.append(failure)
                print(failure['traceback'],flush=True)
    assert provenance['engine_code'][engine]==engine_files(engine)
    assert provenance['source_inputs']==sealed_inputs()[1]
    assert provenance['adapter_sha256']==sha(Path(__file__))
    save(out/f'{engine}-complete.json',{'cases':records,'hash_guard_passed':True,'references_opened':False,
                                       'frozen_template_sha256':sha(ENGINES[engine]/'source-meter-templates.npz')})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('capture','replay'),required=True)
    parser.add_argument('--engine',choices=tuple(ENGINES))
    parser.add_argument('--tag',required=True)
    args=parser.parse_args()
    if Path(args.tag).name!=args.tag or args.tag in ('.','..'):parser.error('single-directory tag required')
    out=ROOT/'runs'/args.tag
    if args.phase=='capture':capture(out)
    else:
        if not args.engine:parser.error('replay requires --engine')
        replay(out,args.engine)


if __name__=='__main__':main()
