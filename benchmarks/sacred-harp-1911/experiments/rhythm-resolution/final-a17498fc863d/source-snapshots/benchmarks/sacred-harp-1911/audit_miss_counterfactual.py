"""Oracle diagnostic: remove only visually confirmed false rests, without inference.

This is a causal probe of saved writer inputs, not an automatic correction rule.
It changes no benchmark predictions and uses no 2025 reference notes or pitches.
"""
import copy
import json
from pathlib import Path

from PIL import Image

from replay_writer_trace import _records, _reading
from reader_trace import capture_writer_trace
from copisteria import write

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'diagnostics/miss-trace'


def run():
    audit=json.loads((OUT/'confirmed-misses.json').read_text())
    rows=[]
    for title in dict.fromkeys(c['title'] for c in audit['cases']):
        sample,trace,report,_,_,image_path=_records(title)
        source=Image.open(image_path).convert('L')
        if report['layout_choice']=='normalized':
            import numpy as np
            from copisteria.front import clean_page
            source=Image.fromarray(clean_page(np.asarray(source)))
        cases=[c for c in audit['cases'] if c['song_id']==sample['id']]
        false_rests=sorted({si for c in cases for si in c['accepted_rest_at_glyph']})
        stages={}
        for variant in ('unchanged_replay','remove_confirmed_false_rests','remove_rests_restore_conflict_losers'):
            rd=_reading(copy.deepcopy(trace),source)
            restored=[]
            if variant!='unchanged_replay':
                for si in false_rests:rd.tok[si]['real']['p']=0
            if variant=='remove_rests_restore_conflict_losers':
                for c in cases:
                    for sym in c['symbols_at_glyph']:
                        if sym['detector_cls'].startswith('note_'):
                            real=rd.tok[sym['sym_id']]['real']
                            if 'conflict_original_p' in real:
                                real['p']=real['conflict_original_p'];restored.append(sym['sym_id'])
            with capture_writer_trace() as emitted:
                xml=write.write(rd,image=source)
            notes=[e for e in emitted['emitted'] if e['kind']=='note']
            note_ids={e['e.si'] for e in notes}
            if variant=='unchanged_replay':
                saved=[e for e in trace['writer']['emitted'] if e['kind']=='note']
                fields=('e.si','step','octave','alter','dur')
                assert [tuple(e[k] for k in fields) for e in notes]==[tuple(e[k] for k in fields) for e in saved],title
            recovered=[c['case_id'] for c in cases if any(s['sym_id'] in note_ids for s in c['symbols_at_glyph']
                                                        if s['detector_cls'].startswith('note_'))]
            dest=OUT/'counterfactuals'/f"{sample['id']}-{variant}.musicxml"
            dest.parent.mkdir(exist_ok=True);dest.write_text(xml)
            stages[variant]={'recovered_confirmed_glyphs':recovered,'count':len(recovered),
                             'total_emitted_pitched_notes':len(notes),'restored_note_candidates':restored,
                             'musicxml':str(dest.relative_to(OUT))}
        rows.append({'song_id':sample['id'],'title':title,'confirmed_false_rest_ids':false_rests,
                     'variants':stages})
    summary={v:sum(r['variants'][v]['count'] for r in rows) for v in rows[0]['variants']}
    result={'method':'Oracle removal of visually confirmed false-rest readings at reviewed noteheads; optional restoration of three note candidates suppressed by the conflict rule',
            'limitations':['Not a deployable heuristic; the false-rest labels came from scan review',
                           'Recovered means the correct physical note candidate reaches XML, not a guarantee of correct pitch or duration',
                           'No re-inference, no reference-derived note insertion, no changes to saved benchmark predictions'],
            'summary':summary,'songs':rows}
    (OUT/'counterfactual.json').write_text(json.dumps(result,indent=2)+'\n')
    audit['counterfactual']=result
    (OUT/'confirmed-misses.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':run()
