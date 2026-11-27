"""Source-backed duration alternatives for rebuilding saved staff-bars.

All returned weights are explicit search weights, not calibrated probabilities.
The baseline event is always recorded; weight zero marks it as disallowed when
source pixels decisively conflict with an open-head duration.
"""
from __future__ import annotations

from collections import defaultdict

from glyph_verifier import verify_head
from head_morphology import head_morphology
from proposal_rhythm_evidence import detached_dot_evidence

OPEN_TYPES={'half','whole','breve','long'}


def _class_p(sym, name):
    try:
        from copisteria.vocab import CLASSES
        wanted=CLASSES.index(name)
    except (ImportError,ValueError):
        return 0.0
    return float(sym.post.get(wanted, sym.post.get(str(wanted), 0.0)))


def _strict_filled(sym, staff, image, verification, morphology):
    x0,y0,x1,y1=map(float,sym.box); sp=float(staff.sp)
    w,h=x1-x0,y1-y0
    square=.65*sp <= w <= 1.65*sp and .65*sp <= h <= 1.65*sp and .70 <= w/max(h,1e-9) <= 1.30
    filled=(verification.get('head_ink_fraction',0)>=.55
            and morphology.get('central_ink_fraction',0)>=.80
            and not morphology.get('hollow_head',False))
    return square and filled


def _beam_support(rd, event, staff_events):
    sym=rd.layout.syms[event.si]; staff=rd.layout.staves[sym.staff]
    x0,y0,x1,y1=map(float,sym.box); sp=float(staff.sp)
    stemdir=sym.attrs.get('stem_dir')
    tip_x=x1 if stemdir=='up' else x0 if stemdir=='down' else None
    if tip_x is None:
        return None
    peers=[]
    for other in staff_events:
        if other.si==event.si or other.kind not in ('note','rest') or other.si<0:
            continue
        osym=rd.layout.syms[other.si]
        if osym.staff!=sym.staff or osym.bar!=sym.bar: continue
        ox0,oy0,ox1,oy1=map(float,osym.box)
        if abs(osym.cx-sym.cx)>.45*sp:
            peers.append((other,osym,(ox0,oy0,ox1,oy1)))
    for beam in rd.layout.syms:
        if beam.cls!='beam' or beam.p<.5 or beam.staff!=sym.staff or beam.bar!=sym.bar:
            continue
        bx0,by0,bx1,by1=map(float,beam.box)
        outside=(by1 < y0-.04*sp) or (by0 > y1+.04*sp)
        if not outside or not (bx0-.2*sp <= tip_x <= bx1+.2*sp):
            continue
        partners=[]
        for other,osym,(ox0,oy0,ox1,oy1) in peers:
            odir=osym.attrs.get('stem_dir')
            ox=ox1 if odir=='up' else ox0 if odir=='down' else osym.cx
            if bx0-.2*sp <= ox <= bx1+.2*sp:
                partners.append(other.si)
        if partners:
            return {'beam_symbol':beam.i,'beam_confidence':beam.p,
                    'stem_tip_x':tip_x,'partner_heads':partners,
                    'beam_box':list(beam.box)}
    return None


def _option(typ,dots,tup,weight,reason):
    return {'typ':typ,'dots':int(dots),'tup':tup,'weight':float(weight),'reason':reason}


def source_duration_options(rd, image, events_by_staff):
    """Return ``{source_si: {options, evidence}}`` for emitted source events.

    Filled square source heads prohibit half/whole readings and add a quarter
    candidate regardless of whether the current event was decoded as a rest.
    Eighth alternatives need an independent beam glyph and supporting duration
    evidence. Weak context dots can be removed only with raw no-dot support and
    a visible, empty detached-dot search region.
    """
    options={};
    for staff_id,events in events_by_staff.items():
        if staff_id<0 or staff_id>=len(rd.layout.staves): continue
        staff=rd.layout.staves[staff_id]
        for event in events:
            sid=int(getattr(event,'si',-1))
            if sid<0 or sid>=len(rd.layout.syms): continue
            sym=rd.layout.syms[sid]; token=rd.tok.get(sid,{})
            typ=str(getattr(event,'typ','quarter')); dots=int(getattr(event,'dots',0)); tup=getattr(event,'tup','none')
            ev={'source_si':sid,'staff':staff_id,'baseline':{'kind':event.kind,'typ':typ,'dots':dots,'tup':tup},
                'box':list(sym.box),'staff_space':float(staff.sp),'verification':{},'morphology':{},'decisions':[]}
            try:
                ver=verify_head(image,sym.box,staff.sp,bar_box=rd.layout.bar_box(staff_id,sym.bar))
                threshold=ver.get('ink_threshold') or 175
                morph=head_morphology(image,sym.box,threshold)
            except (ValueError,IndexError,TypeError):
                ver={};morph={}
            ev['verification']=ver;ev['morphology']=morph
            strict=_strict_filled(sym,staff,image,ver,morph)
            ev['strict_source_filled_head']=strict
            entries=[_option(typ,dots,tup,1.0,'baseline')]
            if strict and typ in OPEN_TYPES:
                entries[0]['weight']=0.0
                entries[0]['reason']='baseline_open_duration_forbidden_by_filled_source_head'
                entries.append(_option('quarter',dots,tup,1.0,'strict_filled_source_head_longest_filled_value'))
                ev['decisions'].append({'action':'forbid_open_baseline','candidate':'quarter'})

            beam=_beam_support(rd,event,events)
            class_eighth=_class_p(sym,'note_eighth')
            context_eighth=(float(token.get('cls',{}).get('p',0))
                            if token.get('cls',{}).get('v')=='note_eighth' else 0.0)
            eighth_support=max(class_eighth,context_eighth)
            ev['beam_support']=beam;ev['eighth_class_posterior']=class_eighth
            ev['eighth_context_support']=context_eighth
            if beam and ((typ in OPEN_TYPES and strict) or (typ=='quarter' and eighth_support>=.15)):
                if not any(x['typ']=='eighth' and x['dots']==dots and x['tup']==tup for x in entries):
                    entries.append(_option('eighth',dots,tup,.25,
                        'independent_beam_and_duration_support' if typ=='quarter'
                        else 'independent_beam_on_strict_filled_source_head'))
                    ev['decisions'].append({'action':'allow_eighth','support':eighth_support,'beam':beam})

            token_dots=token.get('dots',{})
            if dots>0 and token_dots.get('v',dots)>0 and token_dots.get('p',1)>=0 and token_dots.get('p',1)<.9:
                attr_dist=sym.attr_dist.get('dots',{})
                raw_no_dot=float(attr_dist.get('<na>',attr_dist.get('0',0)))
                dot_evidence=detached_dot_evidence(image,sym.box,staff.sp,threshold=threshold)
                ev['raw_no_dot_posterior']=raw_no_dot;ev['detached_dot_evidence']=dot_evidence
                if raw_no_dot>=.9 and not dot_evidence.get('present') and dot_evidence.get('visible'):
                    entries.append(_option(typ,0,tup,.25,'raw_no_dot_and_visible_empty_detached_dot_region'))
                    ev['decisions'].append({'action':'allow_no_dot','raw_no_dot_posterior':raw_no_dot,
                                            'context_dot_posterior':token_dots.get('p'),'ink':dot_evidence})
            # Stable de-duplication protects the fitter from duplicate tuples.
            unique={}
            for option in entries:
                key=(option['typ'],option['dots'],option['tup'])
                if key not in unique or option['weight']>unique[key]['weight']:
                    unique[key]=option
            options[sid]={'options':list(unique.values()),'evidence':ev}
    return options
