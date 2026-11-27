#!/usr/bin/env python3
"""Trace scan-confirmed missed glyphs through the saved reader and writer stages."""
from __future__ import annotations

import csv
import html
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'diagnostics/miss-trace'


def center(box):
    return (box[0]+box[2])/2, (box[1]+box[3])/2


def same_head(box, other, sp):
    x, y = center(box)
    ox, oy = center(other)
    return abs(x-ox) < .7*sp and abs(y-oy) < .7*sp


def run():
    review = json.loads((OUT/'visual-confirmations.json').read_text())
    pool = {r['review_id']: r for r in json.loads((OUT/'review-pool.json').read_text())['records']}
    samples = {s['id']: s for s in json.loads((ROOT/'reader-gallery/results.json').read_text())['samples']}
    cases, duplicate_annotations = [], []
    for sid, shapes in review['songs'].items():
        sample = samples[sid]
        trace = json.loads((ROOT/'reader-gallery/transcriptions'/f'{sid}.trace.json').read_text())
        replay = json.loads((OUT/'replays'/f'{sid}.replay.json').read_text())
        assert replay['verification']['status'] == 'EXACT'
        emitted_notes = {e['e.si'] for e in trace['writer']['emitted'] if e['kind'] == 'note'}
        raw_events = {e['si'] for bar in replay['stages']['events'] for e in bar['events'] if e['kind']=='note'}
        clipped = {e['si']: chop for chop in replay['stages']['chops'] for e in chop['dropped'] if e['kind']=='note'}
        image = Image.open(ROOT/sample['input']).convert('RGB')
        song_cases = []
        for shape, ids in shapes.items():
            for si in ids:
                item = pool[f'{sid}:{si}']
                anchor = trace['syms'][si]
                st = trace['staves'][anchor['staff']]
                sp = st['sp']
                old = next((c for c in song_cases if same_head(c['box'],anchor['box'],sp)),None)
                if old:
                    assert old['shape'] == shape
                    old['review_anchor_ids'].append(si)
                    duplicate_annotations.append({'song_id':sid,'kept_anchor':old['anchor_sym_id'],'duplicate_anchor':si})
                    continue
                nearby = [s for s in trace['syms'] if s['cls'].split('_')[0] in ('note','rest')
                          and same_head(anchor['box'],s['box'],sp)]
                assert not any(s['i'] in emitted_notes for s in nearby), (sid,si,'nearby emitted note')
                notes = [s for s in nearby if s['cls'].startswith('note_')]
                accepted = [s for s in notes if trace['tokens'].get(str(s['i']),{}).get('real',{}).get('p',0)>=.5
                            and trace['tokens'][str(s['i'])]['cls']['v'].startswith('note_')]
                clip_notes = [s for s in accepted if s['i'] in clipped]
                raw_near = [d for d in trace['detections'] if d['cls'].split('_')[0] in ('note','rest')
                            and same_head(anchor['box'],d['xyxy'],sp)]
                if clip_notes:
                    stage = 'accepted_note_clipped'
                elif accepted:
                    stage = 'accepted_note_other_writer_loss'
                elif notes:
                    if any('conflict_original_p' in trace['tokens'].get(str(s['i']),{}).get('real',{}) for s in notes):
                        stage = 'note_suppressed_by_conflict_rule'
                    elif any(str(s['i']) in trace['tokens'] for s in notes):
                        stage = 'note_candidate_not_accepted'
                    else:
                        stage = 'layout_or_token_assignment'
                elif any(d['cls'].startswith('note_') for d in raw_near):
                    stage = 'note_proposal_lost_in_frontend'
                else:
                    stage = 'rest_only_no_recorded_note_proposal'
                matches = []
                for s in nearby:
                    tok = trace['tokens'].get(str(s['i']),{})
                    matches.append({'sym_id':s['i'],'detector_cls':s['cls'],'box':s['box'],
                                    'staff':s['staff'],'bar':s['bar'],
                                    'final_cls':tok.get('cls',{}).get('v'),
                                    'real':tok.get('real'),
                                    'writer_event':s['i'] in raw_events,
                                    'clipped':s['i'] in clipped,
                                    'emitted':next((e for e in trace['writer']['emitted'] if e['e.si']==s['i']),None)})
                rest_ids = [m['sym_id'] for m in matches if (m['final_cls'] or '').startswith('rest_')
                            and m['real'] and m['real']['p']>=.5]
                # Per-part printed position is used only as a readable label; geometry is kept in original pixels.
                physical_rank = sorted(range(len(trace['staves'])), key=lambda i: trace['staves'][i]['y0']).index(anchor['staff'])
                voice_count = len(sample['reference_structure'])
                # The second Repentance reference part is named "Bass Trombone".
                # Use the printed Sacred Harp order for scan labels, not instrument metadata.
                physical_voices = ['treble','alto','tenor','bass'] if voice_count == 4 else ['treble','tenor','bass']
                voice = physical_voices[physical_rank % voice_count]
                case = {'case_id':f'M{len(cases)+len(song_cases)+1:03d}', 'song_id':sid,
                        'title':sample['title'],'printed_page_1911':sample['printed_page_1911'],
                        'source_url':sample['source_url'],'shape':shape,'anchor_sym_id':si,
                        'review_anchor_ids':[si],'box':anchor['box'],'staff':anchor['staff'],
                        'part':voice,'physical_system_index':physical_rank//voice_count,
                        'system_index':st['system'],'model_position_in_system':st['pos'],
                        'bar_index_in_staff':anchor['bar'],
                        'stage':stage,'confirmed_printed_note':True,'emitted_note_at_glyph':False,
                        'accepted_rest_at_glyph':rest_ids,'symbols_at_glyph':matches,
                        'recorded_detections_at_glyph':raw_near,'replay_verification':replay['verification'],
                        'review_sheet':item['sheet'],'crop_box':item['crop_box'],
                        'chop_evidence':[{**clipped[s['i']], 'source_note_id':s['i']} for s in clip_notes]}
                # Add a tight, scan-only head+stem crop with a marker, plus the whole staff bar for context.
                cx,cy=center(anchor['box'])
                crop_box=[round(cx-2.5*sp),round(cy-3.5*sp),round(cx+2.5*sp),round(cy+2.8*sp)]
                crop=image.crop(crop_box)
                draw=ImageDraw.Draw(crop)
                x0,y0,x1,y1=anchor['box']
                draw.rectangle([x0-crop_box[0],y0-crop_box[1],x1-crop_box[0],y1-crop_box[1]],outline='#d50091',width=2)
                rel=f"evidence/{case['case_id']}.jpg"
                (OUT/'evidence').mkdir(exist_ok=True)
                crop.resize((round(crop.width*1.5),round(crop.height*1.5))).save(OUT/rel,quality=94)
                bx=trace['syms'][st['bars'][anchor['bar']]]['box']
                bar_box=[round(bx[0]-.6*sp),round(st['y0']-3*sp),round(bx[2]+.6*sp),round(st['y1']+3*sp)]
                bar=image.crop(bar_box);d=ImageDraw.Draw(bar)
                d.rectangle([x0-bar_box[0],y0-bar_box[1],x1-bar_box[0],y1-bar_box[1]],outline='#d50091',width=3)
                bar_rel=f"evidence/{case['case_id']}-bar.jpg";bar.save(OUT/bar_rel,quality=94)
                case.update(evidence_image=rel,bar_image=bar_rel,bar_crop_box=bar_box)
                song_cases.append(case)
        cases += song_cases
    assert 50 <= len(cases) <= 100
    stats = {'confirmed_misses':len(cases),'songs':len(review['songs']),
             'by_shape':dict(Counter(c['shape'] for c in cases)),
             'by_stage':dict(Counter(c['stage'] for c in cases)),
             'by_song':dict(Counter(c['title'] for c in cases)),
             'with_accepted_rest_at_same_glyph':sum(bool(c['accepted_rest_at_glyph']) for c in cases),
             'square_by_stage':dict(Counter(c['stage'] for c in cases if c['shape']=='la'))}
    result = {'summary':stats,'reviewer':review['reviewer'],'selection':review['selection'],
              'confirmation_basis':review['confirmation_basis'],
              'limitations':['Purposeful candidate-based audit, not population error rates',
                             'No estimate of glyphs entirely absent from all retained detections',
                             'Physical same-head association uses reviewed anchors and a 0.7-staff-space center tolerance',
                             'Only a visually confirmed printed note with no corresponding emitted note is counted',
                             'Reference editions nominate songs but do not establish confirmation',
                             'Scan voice labels use printed vertical order; reference instrument metadata is not used (Repentance part 2 is named Bass Trombone)'],
              'duplicate_review_anchors_collapsed':duplicate_annotations,'cases':cases}
    (OUT/'confirmed-misses.json').write_text(json.dumps(result,indent=2)+'\n')
    with (OUT/'confirmed-misses.csv').open('w') as f:
        fields=['case_id','title','printed_page_1911','part','staff','bar_index_in_staff','shape','stage','anchor_sym_id','accepted_rest_at_glyph','evidence_image','bar_image']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(cases)
    print(json.dumps(stats,indent=2))
    return result


if __name__ == '__main__':
    run()
