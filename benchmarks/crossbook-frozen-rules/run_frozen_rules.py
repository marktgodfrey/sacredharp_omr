"""Evaluate immutable rhythm-rule snapshots on a sealed cross-book pilot.

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
    manifest=read(PILOT/'manifest.json')
    inputs={str((HISTORICAL/s[k]).relative_to(WORKSPACE)):sha(HISTORICAL/s[k])
            for s in manifest['samples'] for k in ('source','input')}
    # Never fingerprint/open reference files during generation.
    inputs[str((PILOT/'manifest.json').relative_to(WORKSPACE))]=sha(PILOT/'manifest.json')
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
    provenance={'adapter_sha256':sha(Path(__file__)),'engine_code':{e:engine_files(e) for e in ENGINES},
                'source_inputs':inputs,'models':model_hashes,'reference_opened_during_generation':False,
                'selection':'All fourteen sealed pilot crops, both layout variants; no new selection or tuning',
                'prediction_metadata_used':['id','input'],'compute_units':'CPU_ONLY'}
    save(out/'manifest.json',manifest);save(out/'provenance.json',provenance)
    save(out/'adapter-snapshot.json',{'script':Path(__file__).read_text()})
    records=[]
    for variant in VARIANTS:
        folder=out/'seeds'/variant/'predictions';folder.mkdir(parents=True)
        for i,sample in enumerate(manifest['samples'],1):
            print(f'capture {variant} {i}/{len(manifest["samples"])} {sample["id"]}',flush=True)
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
            records.append({'id':sample['id'],'variant':variant,'xml_sha256':sha(xml),
                            'trace_sha256':sha(xml.with_suffix('.trace.json')),
                            'sealed_pilot_score_xml_identical':same_score_xml(xml,old)})
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
            print(f'{engine} {variant} {i}/14 {sample["id"]}',flush=True)
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


def pooled(rows):
    edits=sum(r['totals']['pitch_duration_edit_distance'] for r in rows)
    denominator=sum(r['totals']['pitch_duration_rate_denominator'] for r in rows)
    matches=sum(r['time_aware_exact_event_multiset']['matches'] for r in rows)
    predicted=sum(r['totals']['prediction_notes'] for r in rows)
    reference=sum(r['totals']['reference_notes'] for r in rows)
    return {'pd_edits':edits,'pd_denominator':denominator,'pd_rate':edits/denominator if denominator else 0,
            'time_aware_f1':2*matches/(predicted+reference) if predicted+reference else 0,
            'matches':matches,'predicted_notes':predicted,'reference_notes':reference}


def score(out):
    for phase in ('capture','prior','current'):assert read(out/f'{phase}-complete.json')['hash_guard_passed']
    provenance=read(out/'provenance.json')
    assert provenance['adapter_sha256']==sha(Path(__file__))
    assert provenance['engine_code']=={e:engine_files(e) for e in ENGINES}
    activate('current')
    from edition_comparison import compare_edition
    manifest=read(out/'manifest.json');rows=[]
    empty=out/'empty.musicxml';empty.write_text('<score-partwise><part-list/></score-partwise>')
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
                    assert not spans[stage]
            row={'id':s['id'],'book':s['book'],'title':s['title'],'variant':variant,'scores':scores,
                 'predictions':paths,'unresolved_columns':unresolved,'event_removals':changes}
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
                    'failed_cases':sum(r['scores'][stage]['failed'] for r in subset)})
    save(out/'results.json',{'scope':'Seven matched tunes per independent printing, both layouts; fourteen source crops',
         'frozen_engines':{e:str(p.relative_to(WORKSPACE)) for e,p in ENGINES.items()},'aggregates':aggregates,'samples':rows})
    lines=['# Frozen rhythm rules: independent-printing pilot','',
           'Seven matched tunes from each of the 1870 Sacred Harp and J. L. White 1911 editions; both baseline layout variants are retained. Rules and 1911 JPK meter templates were frozen before seeing these readings. No target-data tuning was performed.','',
           '| Book | Layout | Stage | PD edits / denominator | F1 | Failed |',
           '|---|---|---|---:|---:|---:|']
    lines += [f"| {a['book']} | {a['variant']} | {a['stage']} | {a['pd_edits']}/{a['pd_denominator']} | {a['time_aware_f1']:.4f} | {a['failed_cases']} |" for a in aggregates]
    lines += ['','`prior` is the pre-dot/false-head rhythm checkpoint; `current` is the new frozen checkpoint. Both start from identical baseline events; this does not reproduce the earlier JPK missing-head-proposal stages. `baseline` is the frozen CoreML reader without rhythm-resolution. Source voice order is used only for scoring; edition-absent altos are excluded, and unexpected/missing detected source parts remain penalized.','',
              'All 28 baseline captures and 56 frozen-policy attempts finished under hash guards before reference scoring. Failed policy attempts remain in the table as empty predictions. Reference differences prevent interpreting these scores as historical-source accuracy. Repeated matched tunes and two layout variants are paired observations, not 28 independent songs.','',
              '## Current versus prior: every changed case','']
    changed=[r for r in rows if r['pd_change_current_vs_prior'] or r['f1_change_current_vs_prior']]
    lines += [f"- {r['id']} / {r['variant']}: PD {r['pd_change_current_vs_prior']:+d}; F1 {r['f1_change_current_vs_prior']:+.4f}." for r in changed] or ['No score changes.']
    lines += ['','Source adjudication of changed rules is required before treating improvements as correctness. Source reviews and checks are recorded separately. Defaults and gallery remain unchanged.','',
              '**Recommended:** inspect every changed source decision and expand independent-book coverage without tuning this held-out run.',
              '**Alternative:** keep the stage opt-in while evaluating more source-adjudicated cross-book controls.','']
    (out/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(aggregates,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('capture','replay','score'),required=True)
    parser.add_argument('--engine',choices=tuple(ENGINES))
    parser.add_argument('--tag',required=True)
    args=parser.parse_args()
    if Path(args.tag).name!=args.tag or args.tag in ('.','..'):parser.error('single-directory tag required')
    out=ROOT/'runs'/args.tag
    if args.phase=='capture':capture(out)
    elif args.phase=='replay':
        if not args.engine:parser.error('replay requires --engine')
        replay(out,args.engine)
    else:score(out)


if __name__=='__main__':main()
