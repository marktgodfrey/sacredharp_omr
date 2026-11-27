"""Opt-in source constraints for inherited clipping, tuplets and note values."""
from __future__ import annotations
import copy
from collections import defaultdict
from fractions import Fraction

from source_duration_options import source_duration_options
from proposal_rhythm_evidence import detached_dot_evidence


def unique_physical_events(events_by_staff,rd=None,image=None):
    """Undo serialized repeat copies reassigned to their original physical head.

    A saved copy has no second physical head. Keep its source occurrence once;
    source-positioned measure repeats must be handled at their own destination.
    """
    result={};removed=[]
    for staff,events in events_by_staff.items():
        seen=set();out=[]
        for e in events:
            key=(e.si,e.voice,e.kind,e.step,e.octave,e.alter)
            if e.si>=0 and key in seen:
                removed.append({'staff':staff,'sym_id':e.si,'kind':e.kind,'voice':e.voice,
                    'reason':'duplicate_serialized_occurrence_of_same_physical_head'})
                continue
            seen.add(key);out.append(copy.deepcopy(e))
        if rd is not None:
            from bar_fitting import _overlap
            notes=[e for e in out if e.kind=='note'];kept=[];sp=rd.layout.staves[staff].sp
            for e in out:
                matches=[]
                if e.kind in ('rest','mrest'):
                    s=rd.layout.syms[e.si];w,h=s.box[2]-s.box[0],s.box[3]-s.box[1]
                    head_box=.5*sp<=w<=1.8*sp and .48*sp<=h<=1.8*sp
                    composite=(e.kind=='rest' and .5*sp<=w<=1.8*sp and 1.8*sp<h<=4.5*sp)
                    if head_box or composite:
                        for n in notes:
                            q=rd.layout.syms[n.si];cover,iou=_overlap(s.box,q.box)
                            same_head=(head_box and abs(s.cx-q.cx)<.25*sp and abs(s.cy-q.cy)<.25*sp and cover>=.8 and iou>=.65)
                            qw=q.box[2]-q.box[0]
                            qh=q.box[3]-q.box[1]
                            same_head_and_flag=(composite and .5*sp<=qw<=1.8*sp and .48*sp<=qh<=1.8*sp
                                and abs(s.cx-q.cx)<.15*sp and .75<=w/max(qw,1e-9)<=1.4 and cover>=.9
                                and min(abs(s.box[1]-q.box[1]),abs(s.box[3]-q.box[3]))<.25*sp)
                            if s.bar==q.bar and (same_head or same_head_and_flag):
                                matches.append((iou,n))
                if matches:
                    n=max(matches,key=lambda pair:pair[0])[1]
                    for mark in e.marks:
                        if mark not in n.marks:n.marks.append(mark)
                    removed.append({'staff':staff,'sym_id':e.si,'kind':e.kind,'voice':e.voice,
                        'note_kept':n.si,'reason':'same_physical_head_already_emitted_as_note'})
                else:kept.append(e)
            out=kept
            if image is not None:
                from beam_region_evidence import beam_region_evidence
                from glyph_verifier import verify_head
                from head_morphology import head_morphology
                from false_head_evidence import repeat_dot_head_evidence,line_or_blemish_evidence
                kept=[]
                for e in out:
                    s=rd.layout.syms[e.si];w=s.box[2]-s.box[0]
                    if e.kind=='note' and e.grace=='none':
                        peers=[{'box':rd.layout.syms[n.si].box} for n in out if n.kind=='note'
                               and n.si!=e.si and rd.layout.syms[n.si].bar==s.bar]
                        repeat=repeat_dot_head_evidence(image,s,rd.layout.staves[staff],peers,
                            [q for q in rd.layout.syms if q.staff==staff])
                        if repeat['repeat_dot_head']:
                            removed.append({'staff':staff,'sym_id':e.si,'kind':e.kind,'voice':e.voice,
                                'reason':'repeat_dot_misread_as_notehead','source_geometry_evidence':repeat})
                            continue
                        if s.p<.8:
                            ver=verify_head(image,s.box,sp,bar_box=rd.layout.bar_box(staff,s.bar))
                            morph=head_morphology(image,s.box,ver.get('ink_threshold') or 175)
                            residual=line_or_blemish_evidence(image,s,rd.layout.staves[staff],ver,morph)
                            if residual['line_or_blemish']:
                                reason=('empty_source_box_misread_as_notehead' if s.p<.3
                                    and ver['head_ink_fraction']<=.08 and ver['supported_quadrants']<=1
                                    and morph['central_ink_fraction']<.08 else 'line_or_blemish_misread_as_notehead')
                                removed.append({'staff':staff,'sym_id':e.si,'kind':e.kind,'voice':e.voice,
                                    'reason':reason,'source_geometry_evidence':residual})
                                continue
                    if e.kind=='note' and e.grace=='none' and s.p<.3:
                        ver=verify_head(image,s.box,sp,bar_box=rd.layout.bar_box(staff,s.bar))
                        if ver['reason']=='no_head_ink' and ver['head_ink_fraction']<=.08 and ver['supported_quadrants']<=1:
                            morph=head_morphology(image,s.box,ver.get('ink_threshold') or 175)
                            if morph['central_ink_fraction']<.08 and morph['enclosed_white_area_fraction']<.02:
                                removed.append({'staff':staff,'sym_id':e.si,'kind':e.kind,'voice':e.voice,
                                    'reason':'empty_source_box_misread_as_notehead',
                                    'source_geometry_evidence':{'empty_head_box':True,'verification':ver,'morphology':morph}})
                                continue
                    candidate=(e.kind=='note' and e.typ in ('eighth','16th','32nd') and not e.chord
                               and e.grace=='none' and s.p<.95 and w>=1.25*sp)
                    evidence=None
                    if candidate:
                        peers=[{'si':n.si,'x':n.x,'box':rd.layout.syms[n.si].box} for n in out
                               if n.kind=='note' and n.si!=e.si and rd.layout.syms[n.si].bar==s.bar]
                        evidence=beam_region_evidence(image,s.box,sp,peers)
                    if evidence and evidence['beam_region']:
                        removed.append({'staff':staff,'sym_id':e.si,'kind':e.kind,'voice':e.voice,
                            'reason':'beam_stroke_misread_as_notehead','source_geometry_evidence':evidence})
                    else:kept.append(e)
                out=kept
        result[staff]=out
    return result,removed


def _non_tuplet_bars(rd,events_by_staff):
    grouped=defaultdict(list)
    for staff,events in events_by_staff.items():
        for e in events:
            if e.si>=0:grouped[staff,rd.layout.syms[e.si].bar].append(e)
    result={}
    for (staff,bar),events in grouped.items():
        inherited=[e for e in events if e.tup not in ('none','other')]
        if not inherited:continue
        evidence=[];valid=True
        for e in inherited:
            token=rd.tok.get(e.si,{})
            if token.get('tup',{}).get('v')!='none' or token['tup'].get('p',0)<.99:
                valid=False;break
            evidence.append({'sym_id':e.si,'reading_tuplet':token['tup']})
        glyphs=[s.i for s in rd.layout.syms if s.staff==staff and s.bar==bar and s.cls.startswith(('tuplet','number')) and s.p>=.2]
        fractional=[]
        for e in events:
            r=rd.tok.get(e.si,{})
            if r.get('onset_p',0)<.9 or r.get('onset') is None:continue
            f=float(r['onset'])%1
            if min(abs(f-1/3),abs(f-2/3))<.04:fractional.append(e.si)
        if valid and not glyphs and not fractional:
            result[staff,bar]={'source':'no_tuplet_readings_and_no_numeric_or_fractional_support',
                'reading_evidence':evidence,'numeric_glyphs':glyphs,'fractional_onset_support':fractional}
    return result


def _printed_beam(rd,event,events,image=None):
    """Permit a fast value for a filled head even when labelled as a rest."""
    sym=rd.layout.syms[event.si];sp=rd.layout.staves[sym.staff].sp
    peers=[e for e in events if e.si!=event.si and e.kind in ('note','rest')
           and rd.layout.syms[e.si].bar==sym.bar and .7*sp<abs(e.x-event.x)<5*sp]
    # A missed source head can still establish the other end of a printed
    # beam. It supplies geometry only; no new pitched event is created.
    from types import SimpleNamespace
    seen={e.si for e in peers}
    for other in rd.layout.syms:
        if other.i==event.si or other.i in seen or other.staff!=sym.staff or other.bar!=sym.bar or other.p<.3:continue
        if other.fam not in ('note','rest','mRest') or not .7*sp<abs(other.cx-event.x)<5*sp:continue
        w,h=other.box[2]-other.box[0],other.box[3]-other.box[1]
        if .5*sp<=w<=1.8*sp and .48*sp<=h<=1.8*sp:
            peers.append(SimpleNamespace(si=other.i,x=other.cx,kind='source_head'))
    for beam in rd.layout.syms:
        wide_candidate=(beam.cls in ('beam','flag') and beam.p>=.05 and beam.box[2]-beam.box[0]>=1.5*sp)
        if not(beam.cls=='beam' and beam.p>=.5 or wide_candidate) or beam.staff!=sym.staff or beam.bar!=sym.bar:continue
        a,b,c,d=beam.box
        if not (.5*sp<min(abs(b-sym.cy),abs(d-sym.cy))<3.8*sp):continue
        if not any(a-.35*sp<=x<=c+.35*sp for x in (sym.box[0],sym.box[2])):continue
        partners=[e.si for e in peers if any(a-.35*sp<=x<=c+.35*sp for x in (rd.layout.syms[e.si].box[0],rd.layout.syms[e.si].box[2]))]
        if partners:
            proof=None
            if beam.p<(.5 if beam.cls=='beam' else .7):
                if image is None:continue
                from beam_region_evidence import beam_region_evidence
                heads=[{'si':e.si,'x':e.x,'box':rd.layout.syms[e.si].box} for e in [event,*peers]]
                proof=beam_region_evidence(image,beam.box,sp,heads,require_exterior=False)
                if not proof['beam_region']:continue
            return {'beam_id':beam.i,'confidence':beam.p,'partners':partners,'pixel_beam_evidence':proof}
    return None


def _printed_flag(rd,event,events):
    sym=rd.layout.syms[event.si];sp=rd.layout.staves[sym.staff].sp
    for flag in rd.layout.syms:
        if flag.cls!='flag' or flag.p<.6 or flag.staff!=sym.staff or flag.bar!=sym.bar:continue
        candidates=[]
        for e in events:
            if e.kind not in ('note','rest') or e.si<0:continue
            h=rd.layout.syms[e.si]
            if h.bar!=sym.bar:continue
            dx=min(abs(x-y) for x in (h.box[0],h.box[2]) for y in (flag.box[0],flag.box[2]))/sp
            gap=max(h.box[1]-flag.box[3],flag.box[1]-h.box[3],0)/sp
            if dx<=.45 and .2<=gap<=3.8:
                candidates.append((dx+.05*abs(h.cy-flag.cy)/sp,e.si))
        if candidates and min(candidates)[1]==event.si:
            return {'flag_id':flag.i,'confidence':flag.p}
    return None


def _repeat_dot_column(rd,sym,sp,image=None):
    def repeat_context(group):
        ys=sorted(p['cy'] for p in group)
        if len(ys)<2 or not all(.7*sp<=b-a<=1.3*sp for a,b in zip(ys,ys[1:])):return False
        # A dotted chord can also make a regular vertical dot column. Multiple
        # distinct heads immediately to the left make repeat identity unsafe.
        companions=[]
        for s in rd.layout.syms:
            if s.staff!=sym.staff or s.bar!=sym.bar or not s.cls.startswith('note_') or s.p<.3:continue
            w,h=s.box[2]-s.box[0],s.box[3]-s.box[1]
            if not (.5*sp<=w<=1.8*sp and .48*sp<=h<=1.8*sp):continue
            if any(.08*sp<p['cx']-s.box[2]<1.2*sp and abs(p['cy']-s.cy)<.65*sp for p in group):
                if not any(abs(s.cx-x)<.25*sp and abs(s.cy-y)<.25*sp for x,y in companions):
                    companions.append((s.cx,s.cy))
        if len(companions)>=max(2,len(group)-1):return False
        if len(group)>=3:return True
        st=rd.layout.staves[sym.staff];cx=sum(p['cx'] for p in group)/len(group)
        middle_spaces=all(abs(y-(st.y0+offset*sp))<=.25*sp for y,offset in zip(ys,(1.5,2.5)))
        boundary=any(s.staff==sym.staff and s.cls.startswith('barLine') and s.p>=.5
                     and min(abs(s.box[0]-cx),abs(s.box[2]-cx))<=1.5*sp for s in rd.layout.syms)
        return middle_spaces and boundary
    dots=[s for s in rd.layout.syms if s.cls.startswith('dots_') and s.p>=.05
          and s.staff==sym.staff and s.bar==sym.bar and sym.box[2]+.05*sp<s.cx<sym.box[2]+1.8*sp]
    for a in dots:
        group=[s for s in dots if abs(s.cx-a.cx)<.25*sp]
        if repeat_context([{'cx':s.cx,'cy':s.cy} for s in group]):
            return {'glyph_ids':[s.i for s in group]}
    if image is not None:
        import numpy as np
        from proposal_rhythm_evidence import _components
        pixels=np.asarray(image);st=rd.layout.staves[sym.staff]
        x0=max(0,int(sym.box[2]+.08*sp));x1=min(pixels.shape[1],int(sym.box[2]+1.8*sp))
        y0=max(0,int(st.y0-.2*sp));y1=min(pixels.shape[0],int(st.y1+.2*sp))
        cut=pixels[y0:y1,x0:x1]
        if cut.size:
            threshold=float(np.clip(np.percentile(cut,90)-40,130,205));mask=cut<threshold
            for j in range(5):
                yy=int(round(st.y0+j*sp-y0));half=max(1,int(round(.08*sp)))
                mask[max(0,yy-half):min(mask.shape[0],yy+half+1),:]=False
            compact=[]
            for area,a,b,c,d in _components(mask):
                w,h=c-a,d-b
                if .25*sp<=w<=.75*sp and .2*sp<=h<=.75*sp and .5<=w/max(h,1)<=1.8 and .04*sp*sp<=area<=.55*sp*sp:
                    compact.append({'box':[x0+a,y0+b,x0+c,y0+d],'cx':x0+(a+c)/2,'cy':y0+(b+d)/2})
            for dot in compact:
                group=[p for p in compact if abs(p['cx']-dot['cx'])<.25*sp]
                if repeat_context(group):
                    return {'pixel_components':group,'threshold':threshold}
    return None


def resolved_duration_options(rd,image,events_by_staff):
    from copisteria import write
    from attached_stem_evidence import attached_stem_evidence
    choices=source_duration_options(rd,image,events_by_staff)
    no_tuplet=_non_tuplet_bars(rd,events_by_staff)
    for staff,events in events_by_staff.items():
        st=rd.layout.staves[staff]
        for e in events:
            if e.si<0 or e.kind not in ('note','rest') or e.grace!='none':continue
            sym=rd.layout.syms[e.si];r=rd.tok.get(e.si,{})
            choice=choices[e.si];evidence=choice['evidence'];morph=evidence['morphology'];ver=evidence['verification']
            stem=attached_stem_evidence(image,sym.box,st.sp,bar_box=rd.layout.bar_box(staff,sym.bar))
            evidence['attached_stem']=stem
            w,h=sym.box[2]-sym.box[0],sym.box[3]-sym.box[1]
            headlike=.55*st.sp<=w<=1.8*st.sp and .48*st.sp<=h<=1.8*st.sp and .5<=w/h<=1.9
            hollow=(headlike and morph.get('hollow_head',False) and morph.get('enclosed_white_area_fraction',0)>=.12
                    and morph.get('central_ink_fraction',1)<=.55)
            raw_stem=sym.attrs.get('stem_dir') in ('up','down','both') and sym.attr_p.get('stem_dir',0)>=.5
            raw_no_stem=sym.attrs.get('stem_dir') in ('<na>',None) and sym.attr_p.get('stem_dir',0)>=.95
            restore_whole=e.typ not in ('half','breve','long')
            # The short-stub veto prevents a damaged half stem being treated as
            # a whole note merely because a long-stem detector cannot see it.
            forced_type=None;reason=None
            if hollow and stem.get('visible'):
                if stem.get('long_stem'):
                    forced_type='half';reason='source_hollow_head_with_attached_stem'
                elif not stem.get('short_stub') and not raw_stem and raw_no_stem and restore_whole:
                    forced_type='whole';reason='source_hollow_head_without_attached_stem'
            filled=(headlike and not morph.get('hollow_head') and morph.get('central_ink_fraction',0)>=.60
                    and ver.get('head_ink_fraction',0)>=.35 and ver.get('supported_quadrants',0)>=3)
            if filled and e.typ in ('half','whole','breve','long'):
                forced_type='quarter';reason='source_dense_filled_head'
            if evidence.get('strict_source_filled_head') and e.typ in ('half','whole','breve','long'):
                forced_type='quarter';reason='source_filled_square_head'
            beam=_printed_beam(rd,e,events,image) if filled or evidence.get('strict_source_filled_head') else None
            flag=_printed_flag(rd,e,events) if filled or evidence.get('strict_source_filled_head') else None
            if (beam and (beam.get('pixel_beam_evidence') or {}).get('beam_region')
                    and e.typ=='quarter' and sym.cls=='note_eighth'
                    and evidence.get('eighth_class_posterior',0)>=.6):
                forced_type='eighth';reason='source_pixel_beam_and_direct_eighth_reading'
            if (filled and e.typ in ('eighth','16th','32nd') and r.get('cls',{}).get('v')=='note_quarter'
                    and r['cls'].get('p',0)>=.85 and sym.cls=='note_quarter' and sym.p>=.9
                    and (stem.get('long_stem') or ver.get('stem_found') and ver.get('stem_score',0)>=.5)
                    and not beam and not flag):
                forced_type='quarter';reason='source_plain_stem_and_quarter_reading_restore_clipped_fast_value'
            shallow=(w>=.55*st.sp and .12*st.sp<=h<.75*st.sp and w/h>=1.8
                     and morph.get('central_ink_fraction',0)>=.65
                     and min(morph.get('edge_coverage',{}).get(k,0) for k in ('top','bottom'))>=.65)
            if e.kind=='rest' and shallow and sym.cls in ('rest_half','rest_whole') and sym.p>=.9:
                cls=r.get('cls',{})
                if cls.get('v')==sym.cls and cls.get('p',0)>=.95:
                    forced_type=sym.cls.removeprefix('rest_');reason='source_shallow_rest_and_agreeing_readings'
            dot=detached_dot_evidence(image,sym.box,st.sp,threshold=ver.get('ink_threshold') or 175)
            strong_dots=[d for d in dot.get('components',[]) if .015<=d['area_staff_spaces2']<=.20
                and .12<=d['width_staff_spaces']<=.50 and .12<=d['height_staff_spaces']<=.50
                and .6<=d['width_staff_spaces']/max(d['height_staff_spaces'],1e-9)<=1.7]
            neighbors=[other.si for other in events if other.si!=e.si and 0<other.x-e.x<1.3*st.sp]
            raw_dot=sym.attr_dist.get('dots',{}).get('1',0)
            context_dot=r.get('dots',{}).get('p',0) if r.get('dots',{}).get('v')==1 else 0
            repeat_dots=(_repeat_dot_column(rd,sym,st.sp,image)
                         if e.dots>0 or strong_dots and max(raw_dot,context_dot)>=.9 else None)
            from source_dot_evidence import diffuse_dot_mark,component_is_repeat
            augmentation_components=[d for d in strong_dots if not component_is_repeat(d,repeat_dots,rd,st.sp)]
            force_dot=bool(e.dots==0 and max(raw_dot,context_dot)>=.9 and augmentation_components and not neighbors
                           and (hollow or filled or evidence.get('strict_source_filled_head')))
            raw_no_dot=sym.attr_dist.get('dots',{}).get('<na>',sym.attr_dist.get('dots',{}).get('0',0))
            dot_p=r.get('dots',{}).get('p',1)
            current_zero=r.get('dots',{}).get('v')==0 and dot_p>=.95
            diffuse=diffuse_dot_mark(image,sym.box,st) if e.dots>0 and not dot.get('present') else {}
            no_dot=(e.dots>0 and dot.get('visible') and not dot.get('present')
                    and (raw_no_dot>=.9 and (dot_p<.99 or current_zero)
                         or dot_p<.9 and raw_no_dot>=.7 or diffuse.get('diffuse_non_dot_mark')))
            all_repeat=bool(dot.get('components')) and all(component_is_repeat(d,repeat_dots,rd,st.sp)
                                                          for d in dot.get('components',[]))
            if e.dots>0 and repeat_dots and dot.get('visible') and (all_repeat or not dot.get('present') and raw_no_dot>=.9):
                no_dot=True
            evidence['source_dot_resolution']={'measurement':dot,'strong_components':strong_dots,
                'nearby_event_veto':neighbors,'force_one_dot':force_dot,'force_no_dot':no_dot,
                'raw_no_dot_probability':raw_no_dot,'positive_dot_reading_support':max(raw_dot,context_dot),
                'separate_vertical_repeat_dot_column':repeat_dots,'diffuse_mark':diffuse,
                'non_repeat_augmentation_components':augmentation_components}
            clear_tup=no_tuplet.get((staff,sym.bar))
            evidence['inherited_tuplet_resolution']=clear_tup
            options=[]
            for old in choice['options']:
                if old.get('weight',1)<=0:continue
                opt=dict(old);changed=False;why=[]
                if forced_type and opt['typ']!=forced_type:
                    # An independently supported beam may still supply an
                    # eighth of a filled head; a hollow head cannot be fast.
                    if forced_type=='quarter' and opt['typ']=='eighth':pass
                    else:opt['typ']=forced_type;changed=True;why.append(reason)
                if force_dot and opt.get('dots',e.dots)!=1:
                    opt['dots']=1;changed=True;why.append('source_compact_augmentation_dot')
                if no_dot and opt.get('dots',e.dots)!=0:
                    opt['dots']=0;changed=True;why.append('source_no_dot_and_visible_empty_dot_region')
                if clear_tup and opt.get('tup',e.tup)!='none':
                    opt['tup']='none';changed=True;why.append('source_no_tuplet_clock')
                # Recover canonical durations only when an independent source
                # constraint changes the old value. Otherwise preserve actual
                # selected/clipped XML time until evidence supports changing it.
                opt['duration']=str(write._duration(opt['typ'],opt.get('dots',e.dots),opt.get('tup',e.tup))
                    if changed or (opt['typ'],opt.get('dots',e.dots),opt.get('tup',e.tup))!=(e.typ,e.dots,e.tup) else e.dur)
                if changed:opt['reason']='+'.join(why);opt['weight']=1.
                options.append(opt)
            if not options and forced_type:
                options=[{'typ':forced_type,'dots':1 if force_dot else e.dots,
                    'tup':'none' if clear_tup else e.tup,'weight':1.,'reason':reason}]
            evidence['source_beam_resolution']=beam;evidence['source_flag_resolution']=flag
            if (beam or flag) and any(o['typ']=='quarter' for o in options):
                for old in list(options):
                    if old['typ']!='quarter':continue
                    opt={**old,'typ':'eighth','weight':.5,'reason':'filled_source_head_and_printed_beam_or_flag'}
                    opt['duration']=str(write._duration('eighth',opt.get('dots',e.dots),opt.get('tup',e.tup)))
                    options.append(opt)
            unique={}
            for opt in options:
                key=(opt['typ'],opt.get('dots',e.dots),opt.get('tup',e.tup),opt.get('duration'))
                if key not in unique or opt['weight']>unique[key]['weight']:unique[key]=opt
            choice['options']=list(unique.values());evidence['forced_source_type']=forced_type
            evidence['forced_source_type_reason']=reason
    return choices
