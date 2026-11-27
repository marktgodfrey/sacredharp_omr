"""Reference-free bar decoding over competing physical glyph interpretations.

One printed head contributes one note/rest reading. Separate heads sharing a
stem may form a chord; a weak unverified proposal may be omitted. All pitches,
durations and onset distributions come from the existing neural reading.
"""
from __future__ import annotations

import copy
import itertools
import math
from contextlib import contextmanager


def _overlap(a, b):
    inter=max(0.,min(a[2],b[2])-max(a[0],b[0]))*max(0.,min(a[3],b[3])-max(a[1],b[1]))
    areas=[max(0.,r[2]-r[0])*max(0.,r[3]-r[1]) for r in (a,b)]
    return inter/max(1e-9,min(areas)), inter/max(1e-9,sum(areas)-inter)


def _probability(rd, si):
    r=rd.tok[si]['real']
    # The verifier's .51 is a writer admission threshold, not a new model p.
    return min(.99999,max(.00001,float(r.get('verified_original_p',r.get('conflict_original_p',r['p'])))))


def printed_meter_consensus(rd):
    """Anchor opening meter only with agreeing visible glyphs on two staves.

    Continuation pages, uncertain readings and conflicting printed signatures
    retain the original meter search. A pile of overlong note readings must not
    turn an unambiguous printed 2/4 into 3/4 just to accommodate them.
    """
    if not rd.layout.systems:return None
    opening=set(rd.layout.systems[0].staves);visible=set();supported={}
    for s in rd.layout.syms:
        if s.staff not in opening or s.bar!=0:continue
        tok=rd.tok.get(s.i,{})
        cls=tok.get('cls',{}).get('v','')
        if not cls.startswith('meterSig_') or tok.get('real',{}).get('p',0)<.5:continue
        parts=cls.removeprefix('meterSig_').split('_')
        if len(parts)!=2 or not all(v.isdigit() for v in parts):return None
        meter='/'.join(parts);visible.add(meter)
        st=rd.layout.staves[s.staff]
        head=rd.tok.get(st.bars[0],{}).get('time',{}) if st.bars else {}
        if (tok['real']['p']>=.9 and tok['cls'].get('p',0)>=.95
                and head.get('v')==meter and head.get('p',0)>=.99):
            supported.setdefault(meter,set()).add(s.staff)
    if len(visible)==1:
        meter=next(iter(visible))
        if len(supported.get(meter,()))>=2:return meter
    return None


def glyph_groups(rd, events):
    """Mutually exclusive readings of the same physical head, never chord tones."""
    groups=[]
    for e in events:
        if e.kind not in ('note','rest') or e.si<0:
            continue
        s=rd.layout.syms[e.si];sp=rd.layout.staves[s.staff].sp
        match=None
        for g in groups:
            root=g[0];a=rd.layout.syms[root.si]
            if e.voice!=root.voice or s.staff!=a.staff or s.bar!=a.bar:
                continue
            cover,iou=_overlap(s.box,a.box)
            if abs(e.x-root.x)>.35*sp or not(iou>=.65 or cover>=.8):
                continue
            if e.kind==root.kind=='note' and (e.step,e.octave,e.alter)!=(root.step,root.octave,root.alter):
                continue
            match=g;break
        if match is None:groups.append([e])
        else:match.append(e)
    return [g for g in groups if len(g)>1]


def shared_stem_chords(rd, events, verified):
    """Two nonoverlapping heads aligned on an image-verified shared stem."""
    groups=[];used=set()
    notes=[e for e in events if e.kind=='note' and e.si>=0 and e.grace=='none']
    for e in notes:
        if e.si in used:continue
        a=rd.layout.syms[e.si];sp=rd.layout.staves[a.staff].sp;va=verified.get(e.si,{})
        if not va.get('stem_found'):continue
        group=[e]
        for f in notes:
            if f.si==e.si or f.si in used or f.voice!=e.voice:continue
            b=rd.layout.syms[f.si];vb=verified.get(f.si,{})
            if (a.staff!=b.staff or a.bar!=b.bar or abs(e.x-f.x)>.35*sp
                    or (e.typ,e.dots,e.tup)!=(f.typ,f.dots,f.tup)
                    or (e.step,e.octave,e.alter)==(f.step,f.octave,f.alter)
                    or _overlap(a.box,b.box)[0]>.1 or not vb.get('stem_found')
                    or abs(va['stem_x']-vb['stem_x'])>.35*sp):continue
            group.append(f)
        if len(group)>1:
            used.update(f.si for f in group);groups.append(group)
    return groups


def _apply_chord(events, ids):
    members=sorted([e for e in events if e.si in ids],key=lambda e:e.x)
    if len(members)<2:return 0.
    root=members[0]
    timed=[e for e in members if e.dist is not None]
    log_scale=0.
    if timed:
        # Scale the product for numerical stability, retaining the scale in
        # the path score so an implausible common onset is still penalized.
        dist=copy.deepcopy(root.dist or timed[0].dist)
        for key in ('beat','frac'):
            product=[math.prod(max(1e-6,min(1.,e.dist[key][i])) for e in timed)
                     for i in range(len(timed[0].dist[key]))]
            scale=max(product)
            dist[key]=[v/scale for v in product]
            log_scale+=math.log(scale)
        root.dist=dist
        anchor=max(timed,key=lambda e:e.onset_p)
        root.onset,root.onset_p=anchor.onset,anchor.onset_p
    root.chord=False
    for e in members[1:]:e.chord=True
    return log_scale


@contextmanager
def fit_bar_choices(rd, verified, duration_options, *, max_states=128, min_gain=1.0):
    """Bounded joint search; no score references, note-count reward or bar stretch.

    Incompatible readings of one glyph are always alternatives. Weak unverified
    events and detector-supported duration alternatives enter the search only
    when the original voice overflows. The score combines the existing rhythm
    likelihood with neural candidate/duration priors.
    """
    from copisteria import write
    original=write._voices;original_meter=write._page_meter;decisions=[]
    meter=printed_meter_consensus(rd)

    def page_meter(reading,build):
        if meter is not None:
            decisions.append({'action':'printed_meter_consensus','meter':meter})
            return meter
        return original_meter(reading,build)

    def decode(events,args,kwargs,changes):
        evs=copy.deepcopy(events);omit=set(changes.get('omit',()))
        prior=changes.get('prior',0.)+sum(v for si,v in changes.get('type_priors',{}).items() if si not in omit)
        evs=[e for e in evs if e.si not in omit]
        for e in evs:
            if e.si in changes.get('types',{}):e.typ=changes['types'][e.si]
        for ids in changes.get('chords',()):prior+=_apply_chord(evs,ids)
        scores=[];voices=original(evs,*args,**{**kwargs,'score':scores})
        return voices,sum(scores)+prior

    def wrapped(events,*args,**kwargs):
        def unchanged():
            # Meter search compares corresponding staff-bars by index. A
            # candidate can remove an entire weak voice, so per-voice lists
            # would shift later bars' votes between meter hypotheses.
            if kwargs.get('score') is None:return original(events,*args,**kwargs)
            scores=[]
            voices=original(events,*args,**{**kwargs,'score':scores})
            kwargs['score'].append(sum(scores))
            return voices
        bar_len=kwargs.get('bar_len')
        if bar_len is None:return unchanged()
        groups=glyph_groups(rd,events)
        chords=shared_stem_chords(rd,events,verified)
        baseline,baseline_score=decode(events,args,kwargs,{})
        overflowing=any(write._voice_starts(vs,bar_len)[1]>bar_len for vs in baseline.values())
        if not groups and not chords and not overflowing:
            return unchanged()

        group_ids={e.si for g in groups for e in g}
        choices=[]
        for group in groups:
            ranked=sorted(group,key=lambda e:_probability(rd,e.si),reverse=True)
            # The model's real heads are independent Bernoulli probabilities.
            # Conditioning on exactly one real interpretation gives normalized
            # odds, not normalized p: P(i alone) = p_i * product(1-p_j).
            odds={e.si:_probability(rd,e.si)/(1-_probability(rd,e.si)) for e in group}
            total=sum(odds.values())
            choices.append([{'omit':{e.si for e in group if e.si!=winner.si},
                             'prior':math.log(odds[winner.si]/total),
                             'actions':[{'action':'choose_glyph','kept':winner.si,
                                         'omitted':[e.si for e in group if e.si!=winner.si]}]}
                            for winner in ranked[:2]])
        if overflowing:
            weak=[e for e in events if e.kind in ('note','rest') and e.si>=0 and e.si not in group_ids
                  and _probability(rd,e.si)<.9 and not verified.get(e.si,{}).get('stem_found')
                  and float(rd.tok[e.si]['real'].get('det',1.))<.3]
            weak.sort(key=lambda e:_probability(rd,e.si))
            for e in weak[:2]:
                p=_probability(rd,e.si)
                choices.append([{},
                                {'omit':{e.si},'prior':math.log((1-p)/p),
                                 'actions':[{'action':'omit_weak_unverified','sym_id':e.si}]}])
        for group in chords[:2]:
            ids=[e.si for e in group]
            choices.append([{}, {'chords':[ids],'prior':math.log(.5),
                                 'actions':[{'action':'shared_stem_chord','sym_ids':ids}]}])
        if overflowing:
            ambiguous=[e for e in events if e.kind=='note' and e.si in duration_options and e.dist is not None]
            ambiguous.sort(key=lambda e:-float(write.TYPE_QUARTERS.get(e.typ,1)))
            for e in ambiguous[:2]:
                weights=duration_options[e.si];alts=[t for t,w in weights.items() if t!=e.typ
                    and t in write.TYPE_QUARTERS and w>=.25*max(weights.values())]
                if alts:
                    alt=max(alts,key=weights.get)
                    choices.append([{}, {'types':{e.si:alt},
                        'type_priors':{e.si:math.log(max(weights[alt],1e-6)/max(weights.get(e.typ,.05),1e-6))},
                        'actions':[{'action':'duration','sym_id':e.si,'old_type':e.typ,'new_type':alt}]}])
        if not choices:return unchanged()

        states=[{'omit':set(),'types':{},'type_priors':{},'chords':[],'prior':0.,'actions':[]}]
        # Mandatory physical alternatives first; retain a bounded prior-ranked
        # beam before expensive rhythm decoding. Stable ordering breaks ties.
        for opts in choices:
            next_states=[]
            for state,opt in itertools.product(states,opts):
                next_states.append({'omit':state['omit']|opt.get('omit',set()),
                    'types':{**state['types'],**opt.get('types',{})},
                    'type_priors':{**state['type_priors'],**opt.get('type_priors',{})},
                    'chords':state['chords']+opt.get('chords',[]),
                    'prior':state['prior']+opt.get('prior',0.),
                    'actions':state['actions']+opt.get('actions',[])})
            states=sorted(next_states,key=lambda s:-(s['prior']+sum(v for si,v in s['type_priors'].items() if si not in s['omit'])))[:max_states]
        best=None;best_score=-math.inf;best_voices=None
        for state in states:
            voices,score=decode(events,args,kwargs,state)
            if score>best_score:
                best,best_score,best_voices=state,score,voices
        # An impossible duplicate interpretation is not a valid fallback.
        # Optional repairs must improve the same baseline likelihood.
        if not groups and best_score<baseline_score+min_gain:
            return unchanged()
        decisions.append({'bar_len':str(bar_len),'input_ids':[e.si for e in events],
            'score_gain':best_score-baseline_score,'states':len(states),'actions':best['actions'],
            'note':'Search includes speculative meter hypotheses; final emitted trace is authoritative.'})
        # Repeat-bar copying must see the selected events and written values,
        # rather than the incompatible proposals that entered the search.
        events[:]=[e for vs in best_voices.values() for e in vs if e.kind!='gap']
        if kwargs.get('score') is not None:
            kwargs['score'].append(best_score)
        return best_voices

    write._voices=wrapped
    write._page_meter=page_meter
    try:yield decisions
    finally:
        write._voices=original
        write._page_meter=original_meter
