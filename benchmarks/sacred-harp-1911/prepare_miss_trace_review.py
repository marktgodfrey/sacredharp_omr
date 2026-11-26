"""Build scan-first review sheets of suspect glyphs; nothing is auto-confirmed."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'diagnostics/miss-trace'
TITLES = ['Repentance', 'Protection', 'Greenland', 'Arbacoochee', 'Newburgh',
          'New Lebanon', 'Exhilaration', 'Rees', 'Never Part']


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = json.loads((ROOT / 'reader-gallery/results.json').read_text())
    records = []
    font = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 13)
    for song in results['samples']:
        if song['title'] not in TITLES:
            continue
        trace = json.loads((ROOT / 'reader-gallery/transcriptions' / (song['id'] + '.trace.json')).read_text())
        emitted = {e['e.si']: e for e in trace['writer']['emitted']}
        image = Image.open(ROOT / song['input']).convert('RGB')
        buckets = {'note_not_emitted': [], 'note_rejected': [], 'rest_reading': []}
        for sym in trace['syms']:
            tok = trace['tokens'].get(str(sym['i']))
            if not tok or sym['staff'] < 0:
                continue
            cls = tok['cls']['v']
            if cls.startswith('note_') and sym['i'] not in emitted:
                bucket = 'note_not_emitted' if tok['real']['p'] >= .5 else 'note_rejected'
            elif cls.startswith('rest_') and tok['real']['p'] >= .5:
                bucket = 'rest_reading'
            else:
                continue
            # Avoid diagnosing a duplicate box where an emitted note covers the same head.
            x0, y0, x1, y1 = sym['box']
            cx, cy = (x0+x1)/2, (y0+y1)/2
            sp = trace['staves'][sym['staff']]['sp']
            nearby = []
            for e in trace['writer']['emitted']:
                if e['kind'] != 'note' or e['e.si'] < 0:
                    continue
                other = trace['syms'][e['e.si']]
                ox0, oy0, ox1, oy1 = other['box']
                if abs(cx-(ox0+ox1)/2) < .65*sp and abs(cy-(oy0+oy1)/2) < .65*sp:
                    nearby.append(e['e.si'])
            if nearby:
                continue
            buckets[bucket].append((sym, tok))
        # Purposeful, stage-stratified review pool; do not interpret proportions as population rates.
        selected = []
        for bucket, rows in buckets.items():
            selected += [(bucket, s, t) for s, t in sorted(rows, key=lambda z:(z[0]['staff'],z[0]['bar'],z[0]['box'][0]))[:24]]
        for page in range((len(selected)+23)//24):
            sheet = Image.new('RGB', (1600, 6*240), '#ffffff')
            draw = ImageDraw.Draw(sheet)
            for pos, (bucket, sym, tok) in enumerate(selected[page*24:(page+1)*24]):
                x0, y0, x1, y1 = sym['box'];cx,cy=(x0+x1)/2,(y0+y1)/2
                sp=trace['staves'][sym['staff']]['sp']
                crop_box=[round(cx-3.2*sp),round(cy-3.4*sp),round(cx+3.2*sp),round(cy+2.7*sp)]
                crop=image.crop(crop_box);crop.thumbnail((390,190))
                col,row=pos%4,pos//4;left,top=col*400,row*240
                draw.text((left+5,top+3),f"{song['title']} #{sym['i']} s{sym['staff']} b{sym['bar']}",fill='#000',font=font)
                draw.text((left+5,top+21),f"{bucket} {tok['cls']['v']} p={tok['real']['p']:.3f}",fill='#000',font=font)
                sheet.paste(crop,(left+5,top+45))
                scale=crop.width/(crop_box[2]-crop_box[0])
                box=[left+5+(x0-crop_box[0])*scale,top+45+(y0-crop_box[1])*scale,
                     left+5+(x1-crop_box[0])*scale,top+45+(y1-crop_box[1])*scale]
                draw.rectangle(box,outline='#dd00cc',width=2)
                rec={'review_id':song['id']+':'+str(sym['i']),'song_id':song['id'],'title':song['title'],
                     'sym_id':sym['i'],'staff':sym['staff'],'bar':sym['bar'],'box':sym['box'],
                     'pool':bucket,'detector_cls':sym['cls'],'final_cls':tok['cls']['v'],
                     'detector_real_p':tok['real']['det'],'final_real_p':tok['real']['p'],
                     'emitted_kind':emitted.get(sym['i'],{}).get('kind'),
                     'review_status':'UNCONFIRMED','crop_box':crop_box,
                     'sheet':f"review/{song['id']}-{page+1}.jpg"}
                records.append(rec)
            dest=OUT/'review'/f"{song['id']}-{page+1}.jpg";dest.parent.mkdir(exist_ok=True)
            sheet.save(dest,quality=92)
    (OUT/'review-pool.json').write_text(json.dumps({'selection':'Purposeful stage-stratified scan-review pool; not a random error sample',
                                                  'records':records},indent=2)+'\n')
    print(f'{len(records)} unconfirmed review glyphs')


if __name__ == '__main__':
    main()
