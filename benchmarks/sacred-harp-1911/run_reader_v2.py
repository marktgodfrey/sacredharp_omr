"""Evaluate image verification, supported rhythm choices and guided CoreML recovery."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

from compare_musicxml import parse_score, compare
from reader_trace import capture_writer_trace, serialize_reading
from replay_writer_trace import _reading
from reader_policy import verify_reading, apply_stem_verification, detector_duration_options, supported_rhythm_choices, near_head
from experiment_reader import PinnedInputs
from guided_detection import plan_recovery_tiles, merge_recovery_detections

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'experiments/reader-v2'


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2)+'\n')


def conventional_score(path, voice_count):
    """Use printed vocal order, avoiding accidental instrument names in reference XML.

    The source files and the original benchmark scorer/results are untouched.
    Both baseline and new output are rescored identically for this experiment.
    """
    root=ET.parse(path).getroot()
    for i,part in enumerate(root.findall('part-list/score-part'),1):
        part.find('part-name').text=f'Part {i}'
    names=['treble','alto','tenor','bass'] if voice_count==4 else ['treble','tenor','bass']
    with tempfile.NamedTemporaryFile(suffix='.musicxml') as f:
        ET.ElementTree(root).write(f.name)
        return parse_score(Path(f.name),line_names=names)


def observations_for(sid):
    cache=ROOT/'reader-gallery/cache'
    base=json.loads((cache/f'{sid}.base.json').read_text())['detections']
    crop=json.loads((cache/f'{sid}.staff16.json').read_text())
    rows=list(base)
    for run in crop['tile_runs']:
        x,y=run['crop'][:2]
        for item in run['detections']:
            if item['cls'].startswith('note_'):
                d=dict(item);a,b,c,e=d['xyxy'];d['xyxy']=[a+x,b+y,c+x,e+y];rows.append(d)
    return rows


def write_variant(rd,image,observations,*,verification,rhythm,bar_fit=False):
    from copisteria import write
    verified=verify_reading(rd,image)
    baseline_rd=copy.deepcopy(rd) if verification else None
    baseline_xml=baseline_emitted=None
    if verification:
        with capture_writer_trace() as baseline_emitted:
            baseline_xml=write.write(baseline_rd,image=image)
    policy=apply_stem_verification(rd,verified) if verification else []
    options=detector_duration_options(rd,observations) if rhythm else {}
    if bar_fit:
        # The fitter considers duration choices for accepted note symbols, without
        # requiring a separate stem verification.
        options={si:o for si,o in options.items() if rd.tok[si]['real']['p']>=.5}
        from bar_fitting import fit_bar_choices
        choice_context=fit_bar_choices(rd,verified,options)
    else:
        # Existing v2 policy remains limited to physically verified noteheads.
        options={si:o for si,o in options.items() if verified.get(si,{}).get('stem_found')}
        choice_context=supported_rhythm_choices(options)
    with choice_context as choices:
        with capture_writer_trace() as emitted:
            xml=write.write(rd,image=image)
    lost=[];fallback_policy=None
    if verification:
        current_ids={e['e.si'] for e in emitted['emitted'] if e['kind']=='note'}
        protected={e['e.si'] for e in baseline_emitted['emitted'] if e['kind']=='note' and e['e.si']>=0
                   and baseline_rd.tok[e['e.si']]['real']['p']>=.99
                   and verified.get(e['e.si'],{}).get('stem_found')}
        lost=sorted(protected-current_ids)
        if lost:
            # Do not trade away independently stem-verified, near-certain existing
            # notes when a feasible supported rhythm has not been found.
            if bar_fit:
                # Preserve the previous verified reader's recoveries when the
                # new joint search is unsafe; do not fall all the way back to
                # the original reading and discard already validated repairs.
                fallback_rd=copy.deepcopy(baseline_rd)
                xml,emitted,fallback_details=write_variant(fallback_rd,image,observations,
                    verification=True,rhythm=rhythm,bar_fit=False)
                rd.layout,rd.tok=fallback_rd.layout,fallback_rd.tok
                fallback_policy='original' if fallback_details['conservative_fallback'] else 'reader_v2'
            else:
                xml,emitted=baseline_xml,baseline_emitted
                rd.layout,rd.tok=baseline_rd.layout,baseline_rd.tok
                fallback_policy='original'
    return xml,emitted,{'bar_fit':bar_fit,'image_verifications':verified,'verification_decisions':policy,
                        'duration_options':options,'rhythm_search_decisions':choices,
                        'conservative_fallback':bool(lost),'fallback_policy':fallback_policy,
                        'protected_note_loss_in_rejected_path':lost}


def recovery_hits(sid,trace,emitted,audit):
    hit=[]
    for case in audit:
        if case['song_id']!=sid:continue
        # Exact coordinates of visually reviewed source glyphs; not fed into inference.
        sp=trace['staves'][case['staff']]['sp'] if case['staff']<len(trace['staves']) else 30.
        for event in emitted['emitted']:
            if event['kind']=='note' and event['e.si']>=0:
                sym=trace['syms'][event['e.si']]
                if near_head(case['box'],sym['box'],sp):
                    hit.append(case['case_id']);break
    return hit


def aggregate(rows):
    out={}
    for variant in ['baseline']+sorted({v for r in rows for v in r['variants']}):
        values=[r['baseline'] if variant=='baseline' else r['variants'].get(variant) for r in rows]
        values=[v for v in values if v]
        totals=[v['comparison']['totals'] for v in values]
        edits=sum(t['pitch_duration_edit_distance'] for t in totals)
        den=sum(t['pitch_duration_rate_denominator'] for t in totals)
        out[variant]={'songs':len(values),'edits':edits,'denominator':den,'rate':edits/den if den else 0,
                      'audited_glyphs_recovered':sum(len(v.get('audit_hits',[])) for v in values)}
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=['replay','infer'],required=True)
    p.add_argument('--titles',nargs='+')
    p.add_argument('--limit',type=int)
    p.add_argument('--normalize-heads',action='store_true',help='Also test ovalized, stem-verified heads on detector-only crop copies')
    p.add_argument('--bar-fit',action='store_true',help='Use bounded bar fitting for detector-supported duration choices')
    args=p.parse_args()
    if args.normalize_heads and args.phase!='infer':p.error('--normalize-heads requires --phase infer')
    if args.bar_fit and args.normalize_heads:p.error('--bar-fit cannot be combined with --normalize-heads')
    policy_files=['reader_policy.py','glyph_verifier.py','guided_detection.py','run_reader_v2.py']
    if args.normalize_heads:policy_files.append('notehead_normalization.py')
    if args.bar_fit:policy_files.append('bar_fitting.py')
    experiment_key=hashlib.sha256(b''.join((ROOT/f).read_bytes() for f in policy_files)).hexdigest()
    snapshot=OUT/'source-snapshots'/experiment_key
    snapshot.mkdir(parents=True,exist_ok=True)
    for name in policy_files:(snapshot/name).write_bytes((ROOT/name).read_bytes())
    original=json.loads((ROOT/'reader-gallery/results.json').read_text())
    samples=[s for s in original['samples'] if not args.titles or s['title'] in args.titles]
    if args.limit:samples=samples[:args.limit]
    audit=json.loads((ROOT/'diagnostics/miss-trace/confirmed-misses.json').read_text())['cases']
    phase_dir=OUT/(f'{args.phase}_bar_fit' if args.bar_fit else ('infer_normalized' if args.normalize_heads else args.phase))
    detector=model=None
    if args.phase=='infer':
        import torch
        from copisteria.coreml_runtime import CoreMLDetector,CoreMLEvidence
        torch.set_num_threads(4)
        model_dir=ROOT.parent.parent/'copisteria/out/coreml'
        detector=CoreMLDetector(model_dir,units='CPU_ONLY');model=CoreMLEvidence(model_dir,units='CPU_ONLY')
        detector.model.backbone=PinnedInputs(detector.model.backbone)
        detector.model.verifier=PinnedInputs(detector.model.verifier)
        model.native=PinnedInputs(model.native)
    rows=[]
    for idx,sample in enumerate(samples,1):
        started=time.perf_counter();sid=sample['id']
        record_path=phase_dir/'records'/f'{sid}.json'
        if record_path.exists():
            cached_record=json.loads(record_path.read_text())
            if cached_record.get('experiment_key')==experiment_key:
                rows.append(cached_record);continue
        print(f'[{idx}/{len(samples)}] {sample["title"]}',flush=True)
        source=Image.open(ROOT/sample['input']).convert('L')
        old_trace=json.loads((ROOT/'reader-gallery/transcriptions'/f'{sid}.trace.json').read_text())
        old_report=sample['report']
        image=source
        if old_report['layout_choice']=='normalized':
            from copisteria.front import clean_page
            image=Image.fromarray(clean_page(np.asarray(source)))
        voice_count=len(sample['reference_structure'])
        ref=conventional_score(ROOT/sample['reference'],voice_count)
        baseline=compare(ref,conventional_score(ROOT/'reader-gallery'/sample['prediction'],voice_count))
        row={'id':sid,'title':sample['title'],'experiment_key':experiment_key,'bar_fit':args.bar_fit,
             'baseline':{'comparison':baseline},'variants':{}}
        observations=observations_for(sid)
        if args.phase=='replay':
            # Validate reconstruction before attributing any gain to the policy.
            xml,emitted,_=write_variant(_reading(copy.deepcopy(old_trace),source),image,[],verification=False,rhythm=False,bar_fit=False)
            fields=('e.si','step','octave','alter','dur')
            current=[tuple(e[k] for k in fields) for e in emitted['emitted'] if e['kind']=='note']
            saved=[tuple(e[k] for k in fields) for e in old_trace['writer']['emitted'] if e['kind']=='note']
            if current!=saved:raise RuntimeError('Baseline replay mismatch: '+sid)
            readings=[('verification',_reading(copy.deepcopy(old_trace),source),False),
                      ('verification_rhythm',_reading(copy.deepcopy(old_trace),source),True)]
        else:
            from copisteria.revise import read_revised
            from symbol_conflicts import resolve_note_rest_conflicts
            rd=_reading(copy.deepcopy(old_trace),source)
            verifications=verify_reading(rd,source)
            tiles=plan_recovery_tiles(rd,source.size,verifications)
            cache_path=phase_dir/'cache'/f'{sid}.json'
            cache_key={'tiles':tiles,'input_sha256':sample['input_sha256'],
                       'model_manifest_sha256':original['provenance']['model_manifest_sha256']}
            if args.normalize_heads:
                cache_key['normalization_sha256']=hashlib.sha256((ROOT/'notehead_normalization.py').read_bytes()).hexdigest()
            cached=json.loads(cache_path.read_text()) if cache_path.exists() else {}
            if cached.get('key')==cache_key:
                runs=cached['tile_runs']
            else:
                runs=[]
                for tile in tiles:
                    crop=source.crop(tile['crop']);size=max(32,round(max(crop.size)*tile['scale']))
                    arr,scale=detector.prepare(crop,size)
                    dets=detector.run_array(arr,scale)
                    runs.append({**tile,'detections':dets})
                    if args.normalize_heads:
                        from notehead_normalization import normalize_verified_heads
                        heads=[{'box':rd.layout.syms[si].box,
                                'staff_space':rd.layout.staves[rd.layout.syms[si].staff].sp,
                                'evidence':verifications[si]} for si in tile['head_ids']]
                        normalized,normalization_audit=normalize_verified_heads(crop,tile['crop'][:2],heads)
                        if normalization_audit['normalized']:
                            arr,scale=detector.prepare(normalized,size)
                            dets=detector.run_array(arr,scale)
                            runs.append({**tile,'detections':dets,'normalization':normalization_audit})
                save(cache_path,{'key':cache_key,'tile_runs':runs,'tiles':tiles})
            merged,diagnostic=merge_recovery_detections(old_trace['detections'],runs,rd,verifications)
            observations += [{'cls':d['cls'],'conf':d['conf'],'xyxy':d['xyxy']}
                             for d in diagnostic['duration_alternatives']]
            # Preserve the previously selected layout image for this bounded experiment.
            # Additional proposals do not trigger reference-based layout selection.
            rd=read_revised(merged,*source.size,model,attention=False,image=image)
            conflicts=resolve_note_rest_conflicts(rd)
            row['recovery_detection']={**diagnostic,'tile_count':len(tiles)}
            row['conflicts']=conflicts
            readings=[('guided_verification_rhythm',rd,True)]
        for variant,rd,rhythm in readings:
            xml,emitted,details=write_variant(rd,image,observations,verification=True,rhythm=rhythm,bar_fit=args.bar_fit)
            folder=phase_dir/variant;path=folder/f'{sid}.musicxml';folder.mkdir(parents=True,exist_ok=True);path.write_text(xml)
            trace={**serialize_reading(rd),'writer':emitted,**details}
            save(path.with_suffix('.trace.json'),trace)
            comparison=compare(ref,conventional_score(path,voice_count))
            row['variants'][variant]={'comparison':comparison,
                'audit_hits':recovery_hits(sid,trace,emitted,audit),
                'verification_actions':0 if details['conservative_fallback'] else len(details['verification_decisions']),
                'conservative_fallback':details['conservative_fallback'],
                'fallback_policy':details['fallback_policy'],
                'rhythm_search_choices':len(details['rhythm_search_decisions']),
                'layout':{'staves':len(rd.layout.staves),'systems':len(rd.layout.systems)},
                'prediction':str(path.relative_to(OUT))}
        row['seconds']=time.perf_counter()-started
        save(record_path,row);rows.append(row)
        save(phase_dir/'results.json',{'samples':rows,'aggregates':aggregate(rows),
              'scoring':'Both baseline/new rescored by printed part order; 2025 edition comparison',
              'references_used_for_inference':False})
        print(f'  {row["seconds"]:.1f}s; '+str({v:round(x['comparison']['totals']['pitch_duration_error_rate']*100,1) for v,x in row['variants'].items()}),flush=True)
    save(phase_dir/'results.json',{'samples':rows,'aggregates':aggregate(rows),
          'scoring':'Both baseline/new rescored by printed part order; 2025 edition comparison',
          'references_used_for_inference':False})
    print(json.dumps(aggregate(rows),indent=2),flush=True)


if __name__=='__main__':main()
