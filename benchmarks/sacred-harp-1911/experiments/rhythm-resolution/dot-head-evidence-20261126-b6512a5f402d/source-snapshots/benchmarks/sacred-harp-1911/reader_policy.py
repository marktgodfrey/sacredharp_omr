"""Opt-in, reference-free image verification and detector-supported rhythm choices."""
from __future__ import annotations

import copy
import math
from contextlib import contextmanager
from fractions import Fraction

from glyph_verifier import verify_head


def near_head(a, b, sp):
    return (abs((a[0]+a[2]-b[0]-b[2])/2) <= .7*sp
            and abs((a[1]+a[3]-b[1]-b[3])/2) <= .7*sp)


def verify_reading(rd, image):
    import numpy as np
    image=np.asarray(image.convert('L')) if hasattr(image,'convert') else np.asarray(image)
    results = {}
    for s in rd.layout.syms:
        if s.fam not in ('note','rest') or s.staff < 0 or s.bar < 0:
            continue
        st = rd.layout.staves[s.staff]
        results[s.i] = verify_head(image, s.box, st.sp, rd.layout.bar_box(s.staff,s.bar))
    return results


def apply_stem_verification(rd, verifications):
    """A verified physical stem rejects a rest interpretation; admit only existing neural notes.

    The .51 floor is an explicit writer admission decision, not a calibrated new
    model probability. Original context probabilities remain in the audit fields.
    A rest-only detection is never relabeled as a fabricated pitched note.
    """
    decisions, seen = [], set()
    for sid, evidence in verifications.items():
        if not evidence['stem_found'] or sid in seen:
            continue
        head = rd.layout.syms[sid]
        st = rd.layout.staves[head.staff]
        related = [s for s in rd.layout.syms if s.fam in ('note','rest')
                   and s.staff==head.staff and s.bar==head.bar and near_head(head.box,s.box,st.sp)]
        seen.update(s.i for s in related)
        for s in related:
            r = rd.tok.get(s.i)
            if r and 'conflict_original_p' in r['real']:
                old = r['real']['p']; r['real']['p']=r['real']['conflict_original_p']
                decisions.append({'action':'restore_before_conflict','sym_id':s.i,'old_p':old,'new_p':r['real']['p']})
        candidates = []
        for s in related:
            r = rd.tok.get(s.i)
            if not r or not r['cls']['v'].startswith('note_'):
                continue
            cy=(s.box[1]+s.box[3])/2
            geometry_pos=round((st.mid-cy)*2/st.sp)
            if (max(r['real']['p'],r['real'].get('det',0)) >= .15
                    and r.get('pos',{}).get('p',0) >= .6
                    and abs(r['pos']['v']-geometry_pos) <= 1):
                candidates.append((r['real']['p'],s.i))
        if candidates:
            _, winner=max(candidates)
            r=rd.tok[winner]['real']
            if r['p']<.5:
                old=r['p'];r['verified_original_p']=old;r['p']=.51
                decisions.append({'action':'admit_existing_note','sym_id':winner,'old_p':old,'new_p':.51,
                                  'evidence':evidence})
        for s in related:
            r=rd.tok.get(s.i)
            if r and r['cls']['v'].startswith('rest_') and r['real']['p']>=.5:
                old=r['real']['p'];r['real']['verified_original_p']=old;r['real']['p']=0
                decisions.append({'action':'reject_stemmed_rest','sym_id':s.i,'old_p':old,'new_p':0,
                                  'evidence':evidence})
    return decisions


def detector_duration_options(rd, observations):
    """Only duration classes independently observed by the detector are alternatives."""
    options={}
    for s in rd.layout.syms:
        r=rd.tok.get(s.i)
        if not r or not r['cls']['v'].startswith('note_') or s.staff<0:
            continue
        st=rd.layout.staves[s.staff]
        current=r['cls']['v'].split('_',1)[1]
        weights={current:max(.05,r['cls'].get('p',.5))}
        for d in observations:
            if (d['cls'].startswith('note_') and d.get('conf',0)>=.15
                    and near_head(s.box,d['xyxy'],st.sp)):
                typ=d['cls'].split('_',1)[1]
                weights[typ]=max(weights.get(typ,0),float(d['conf']))
        if len(weights)>1:
            options[s.i]=weights
    return options


@contextmanager
def supported_rhythm_choices(options, *, max_ambiguous=2, min_gain=1.0):
    """Try a bounded set of observed duration readings when the baseline drops notes.

    Selection uses the existing onset/rhythm likelihood plus detector class
    evidence. No reference, target note count, invented duration or bar stretching
    enters the choice. The context manager restores the writer hook on exit.
    """
    from copisteria import write
    original=write._voices
    decisions=[]

    def score_path(events, args, kwargs, changes):
        copied=copy.deepcopy(events)
        prior=0.
        for e in copied:
            if e.si in changes:
                new=changes[e.si];weights=options[e.si]
                prior+=math.log(max(weights[new],1e-6)/max(weights.get(e.typ,.05),1e-6))
                e.typ=new
        scores=[]
        kw={**kwargs,'score':scores}
        voices=original(copied,*args,**kw)
        return voices,sum(scores)+prior

    def wrapped(events,*args,**kwargs):
        bar_len=kwargs.get('bar_len')
        # The decoder's score is defined only for notes with onset distributions.
        relevant=[e for e in events if e.kind=='note' and e.si in options and e.dist is not None]
        if bar_len is None or not relevant:
            return original(events,*args,**kwargs)
        base,base_score=score_path(events,args,kwargs,{})
        dropped={e.si for vs in base.values() for e in vs if e.kind=='note'} - {
            e.si for vs in base.values() for e in write._chop(copy.deepcopy(vs),bar_len) if e.kind=='note'}
        if not dropped:
            return original(events,*args,**kwargs)
        ambiguous=[]
        for e in relevant:
            alternatives=[t for t,w in options[e.si].items() if t!=e.typ and t in write.TYPE_QUARTERS
                          and w>=.25*max(options[e.si].values())]
            if alternatives:
                ambiguous.append((e.si,e.typ,sorted(alternatives,key=lambda t:-options[e.si][t])[:1]))
        # Prefer testing ambiguous notes whose long written value can cause overflow.
        ambiguous.sort(key=lambda x:-float(write.TYPE_QUARTERS.get(x[1],Fraction(1))))
        states=[{}]
        for si,typ,alts in ambiguous[:max_ambiguous]:
            states += [{**s,si:alt} for s in list(states) for alt in alts]
        best,best_score={},base_score
        for changes in states[1:]:
            _,score=score_path(events,args,kwargs,changes)
            if score>best_score+1e-9:
                best,best_score=changes,score
        prior=0.
        if best and best_score>=base_score+min_gain:
            for e in events:
                if e.si in best:
                    prior+=math.log(max(options[e.si][best[e.si]],1e-6)/max(options[e.si].get(e.typ,.05),1e-6))
                    decisions.append({'sym_id':e.si,'old_type':e.typ,'new_type':best[e.si],
                                      'score_gain':best_score-base_score,'bar_len':str(bar_len),
                                      'note':'writer search calls may include speculative meter hypotheses'})
                    e.typ=best[e.si]
        result=original(events,*args,**kwargs)
        if prior and kwargs.get('score'):
            kwargs['score'][-1]+=prior
        return result
    write._voices=wrapped
    try:
        yield decisions
    finally:
        write._voices=original
