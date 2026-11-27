"""Read-only source/XML inventory of remaining bar and meter discrepancies.

Flags are screening measurements, not confirmed source errors. The audit opens
no reference transcription and does not mutate a saved reading or prediction.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import shutil
from collections import Counter
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
from run_local_recovery import ROOT, read, save, sha, samples
from replay_writer_trace import _reading

LATEST=ROOT/'experiments/proposal-rhythm/final-0318d4f06bb9'


def meter_length(beats,beat_type):
    try:return Fraction(sum(int(v) for v in beats.split('+'))*4,int(beat_type))
    except (ValueError,TypeError,ZeroDivisionError,AttributeError):return None


def xml_inventory(xml):
    root=ET.fromstring(xml);parts=[];rows=[]
    for pi,part in enumerate(root.findall('part'),1):
        divisions=1;meter=None;nominal=None;part_rows=[]
        for mi,measure in enumerate(part.findall('measure'),1):
            cursor=end=Fraction(0);last_onset=Fraction(0);padding=Fraction(0)
            voices=Counter();times=[]
            for node in measure:
                if node.tag=='attributes':
                    divisions=int(node.findtext('divisions',str(divisions)))
                    for t in node.findall('time'):
                        beats,bt=t.findtext('beats'),t.findtext('beat-type')
                        meter=f'{beats}/{bt}';nominal=meter_length(beats,bt)
                        times.append({'meter':meter,'printed':t.get('print-object')!='no'})
                elif node.tag in ('backup','forward'):
                    amount=Fraction(int(node.findtext('duration','0')),divisions)
                    cursor += amount if node.tag=='forward' else -amount
                    end=max(end,cursor)
                elif node.tag=='note' and node.find('grace') is None:
                    duration=Fraction(int(node.findtext('duration','0')),divisions)
                    onset=last_onset if node.find('chord') is not None else cursor
                    end=max(end,onset+duration)
                    if node.find('chord') is None:last_onset=cursor;cursor+=duration
                    if node.find('rest') is not None and node.get('print-object')=='no':padding+=duration
                    voices[node.findtext('voice','1')]+=1
            right=measure.find('barline[@location="right"]')
            terminal=right is not None and (right.find('repeat') is not None or right.findtext('bar-style') in ('light-heavy','light-light'))
            implicit=measure.get('implicit')=='yes'
            if nominal is None:status='unknown_meter'
            elif end==nominal:status='nominal'
            elif end>nominal:status='over_nominal'
            elif implicit:status='short_implicit'
            elif terminal:status='short_terminal_candidate'
            else:status='short_unmarked'
            row={'part':pi,'measure':mi,'number':measure.get('number'),'meter':meter,
                 'nominal_quarters':str(nominal) if nominal is not None else None,
                 'encoded_span_quarters':str(end),'implicit':implicit,'terminal_or_repeat':terminal,
                 'invisible_padding_quarters':str(padding),'explicit_times':times,'status':status}
            part_rows.append(row);rows.append(row)
        parts.append({'part':pi,'measures':len(part_rows),'meter_changes':[
            {'measure':r['measure'],**t} for r in part_rows for t in r['explicit_times']]})
    spans={}
    for r in rows:spans.setdefault(r['measure'],set()).add(r['encoded_span_quarters'])
    return {'parts':parts,'measures':rows,'span_status_counts':dict(Counter(r['status'] for r in rows)),
            'columns_with_unequal_part_spans':[m for m,v in spans.items() if len(v)>1]}


def clustered(values,tolerance):
    groups=[]
    for x in sorted(values):
        if groups and x-groups[-1][-1]<=tolerance:groups[-1].append(x)
        else:groups.append([x])
    return [float(np.median(g)) for g in groups]


def source_boundary_inventory(rd,image):
    from copisteria import front
    mask=front.ink_mask(np.asarray(image.convert('L')));result=[]
    for si,system in enumerate(rd.layout.systems):
        if len(system.staves) not in (3,4):
            result.append({'system':si,'staves':system.staves,'status':'outside_normal_3_4_staff_scope'});continue
        L=rd.layout;group=system.staves;sp=float(np.median([L.staves[k].sp for k in group]))
        ref=max(group,key=lambda k:sum(not L.syms[i].synthetic for i in L.staves[k].bars))
        reference=[L.syms[i].box for i in L.staves[ref].bars]
        oldcuts=[b[2] for b in reference[:-1]]
        current_all=clustered([L.syms[i].box[2] for k in group for i in L.staves[k].bars[:-1]],.5*sp)
        candidate=copy.deepcopy(rd)
        front._segment(candidate.layout.syms,candidate.layout.staves,candidate.layout.systems[si],mask)
        newboxes=[candidate.layout.syms[i].box for i in candidate.layout.staves[ref].bars]
        newcuts=[b[2] for b in newboxes[:-1]]
        def support(x):
            return [round(max(front._ink_run(mask,xx,L.staves[k].y0+1,L.staves[k].y1-1,reach=2)
                for xx in (x-.25*sp,x,x+.25*sp)),3) for k in group]
        missing=[{'x':x,'vertical_ink_coverage':support(x)} for x in newcuts
                 if not current_all or min(abs(x-y) for y in current_all)>.6*sp]
        extra=[{'x':x,'vertical_ink_coverage':support(x)} for x in oldcuts
               if not newcuts or min(abs(x-y) for y in newcuts)>.6*sp]
        ncol=1+max((max(c) for c in system.columns if c),default=-1)
        result.append({'system':si,'staves':group,'status':'screened','reference_staff':ref,
            'current_staff_bar_counts':[len(L.staves[k].bars) for k in group],
            'current_column_count':ncol,'current_reference_cuts':oldcuts,
            'ink_candidate_bar_count':len(newboxes),'ink_candidate_cuts':newcuts,
            'candidate_missing_boundaries':missing,'candidate_unsupported_reference_boundaries':extra,
            'maximum_current_bar_width_staff_spaces':max((b[2]-b[0])/sp for b in reference),
            'scope':'Candidate segmenter comparison only; manual source inspection is required.'})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--titles',nargs='+');args=p.parse_args()
    selected=[s for s in samples() if not args.titles or s['title'] in args.titles]
    code=[Path(__file__),ROOT/'run_local_recovery.py',ROOT/'replay_writer_trace.py',
          ROOT.parents[1]/'copisteria/src/copisteria/front.py']
    inputs=[LATEST/'results.json',ROOT/'reader-gallery/results.json',
        ROOT/'experiments/bar-fitting/unused20/manifest.json',ROOT/'experiments/bar-fitting/unused20/results.json',
        ROOT/'experiments/reader-v2/replay_bar_fit/results.json']
    for s in selected:
        inputs.append(ROOT/s['input'])
        inputs += [LATEST/'predictions'/f"{s['id']}{ext}" for ext in ('.musicxml','.trace.json')]
    provenance={str(f.relative_to(ROOT.parents[1])):sha(f) for f in sorted(set(code+inputs))}
    key=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    out=ROOT/'diagnostics/bar-meter-audit'/f'inventory-{key[:12]}'
    out.mkdir(parents=True,exist_ok=True)
    for f in code:
        dest=out/'source-snapshots'/f.relative_to(ROOT.parents[1]);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(f,dest)
    rows=[]
    for j,s in enumerate(selected,1):
        sid=s['id'];path=LATEST/'predictions'/f'{sid}.musicxml';trace=read(path.with_suffix('.trace.json'))
        xml=xml_inventory(path.read_text());source=Image.open(ROOT/s['input']).convert('L')
        rd=_reading(copy.deepcopy(trace),source);boundaries=source_boundary_inventory(rd,source)
        flag_counts=Counter(r['status'] for r in xml['measures'] if r['status']!='nominal')
        flags=sum(flag_counts.get(k,0) for k in ('over_nominal','short_unmarked','unknown_meter'))
        missing=sum(len(r.get('candidate_missing_boundaries',[])) for r in boundaries)
        extra=sum(len(r.get('candidate_unsupported_reference_boundaries',[])) for r in boundaries)
        row={'id':sid,'title':s['title'],'dataset':s['dataset'],'input':s['input'],
            'prediction':str(path.relative_to(ROOT)),'trace_sha256':sha(path.with_suffix('.trace.json')),
            'xml':xml,'source_boundary_screen':boundaries,'flags':{'irregular_part_measures':flags,
                'span_status_counts':dict(flag_counts),'candidate_missing_source_boundaries':missing,
                'candidate_reference_cuts_not_reproduced':extra},
            'trace_fixed_column_cuts_are_final':False,
            'interpretation':'Source candidates and XML irregularities require visual confirmation; no reference score used.'}
        rows.append(row)
        if j%10==0:print(f'[{j}/{len(selected)}] {s["title"]}',flush=True)
    counts=Counter()
    for r in rows:
        counts.update(r['xml']['span_status_counts'])
        counts['systems_screened']+=sum(b['status']=='screened' for b in r['source_boundary_screen'])
        counts['candidate_missing_boundaries']+=r['flags']['candidate_missing_source_boundaries']
        counts['candidate_unreproduced_reference_cuts']+=r['flags']['candidate_reference_cuts_not_reproduced']
    ranked=sorted(rows,key=lambda r:(-r['flags']['irregular_part_measures'],
        -r['flags']['candidate_missing_source_boundaries'],-r['flags']['candidate_reference_cuts_not_reproduced']))
    value={'experiment_key':key,'prediction_stage':str(LATEST.relative_to(ROOT)),'songs':len(rows),
        'reference_xml_opened':False,'prediction_files_modified':False,'counts':dict(counts),
        'songs_with_irregular_part_measures':sum(r['flags']['irregular_part_measures']>0 for r in rows),
        'songs_with_boundary_candidates':sum(r['flags']['candidate_missing_source_boundaries']+r['flags']['candidate_reference_cuts_not_reproduced']>0 for r in rows),
        'samples':rows,'provenance':provenance}
    save(out/'inventory.json',value)
    lines=['# Remaining bar and meter screening inventory','',
        f"Screened {len(rows)} latest predictions and their exact recognition inputs without reference XML or prediction changes.",
        'Flags are not a confirmed-error count. Short implicit and terminal bars are recorded separately. '
        'Ink segmentation is a candidate generator requiring source review. Stale `fixed_column_cuts` in the saved traces '
        'are never treated as final cuts; this inventory measures encoded XML spans directly.','',
        '| Song | Irregular part-measures | Missing-boundary candidates | Current cuts not reproduced |',
        '|---|---:|---:|---:|']
    for r in ranked:
        f=r['flags']
        if f['irregular_part_measures'] or f['candidate_missing_source_boundaries'] or f['candidate_reference_cuts_not_reproduced']:
            lines.append(f"| {r['title']} | {f['irregular_part_measures']} | {f['candidate_missing_source_boundaries']} | {f['candidate_reference_cuts_not_reproduced']} |")
    (out/'SCREENING.md').write_text('\n'.join(lines)+'\n')
    print({'songs':len(rows),'counts':dict(counts),'flagged_songs':value['songs_with_irregular_part_measures'],
           'boundary_candidate_songs':value['songs_with_boundary_candidates']})
    print(out,flush=True)

if __name__=='__main__':main()
