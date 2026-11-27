"""Positive source geometry for structural ink serialized as a notehead."""
from __future__ import annotations
import numpy as np
from proposal_rhythm_evidence import _components
from head_morphology import head_morphology


def _staff_mask(image, box, staff, margin=0):
    pixels=np.asarray(image);sp=staff.sp
    x0,y0,x1,y1=box
    a=max(0,int(np.floor(x0-margin)));b=min(pixels.shape[1],int(np.ceil(x1+margin)))
    top=max(0,int(np.floor(y0)));bottom=min(pixels.shape[0],int(np.ceil(y1)))
    crop=pixels[top:bottom,a:b]
    if crop.size==0:return None
    threshold=float(np.clip(np.percentile(crop,90)-40,130,205))
    mask=crop<threshold
    half=max(1,int(round(.08*sp)))
    for j in range(5):
        yy=int(round(staff.y0+j*sp-top))
        if yy+half>=0 and yy-half<mask.shape[0]:
            mask[max(0,yy-half):min(mask.shape[0],yy+half+1),:]=False
    return mask,a,top,threshold


def repeat_dot_head_evidence(image,sym,staff,neighbor_heads,structural_symbols):
    """Require a compact disconnected dot in a regularly spaced repeat column.

    Three or more dots establish a column independently. A two-dot sign also
    needs a nearby printed barline. A real neighboring head supplies context;
    neither a small head nor a stemless head alone is sufficient for rejection.
    """
    sp=staff.sp;x0,y0,x1,y1=sym.box;cx=(x0+x1)/2;cy=(y0+y1)/2
    empty={'repeat_dot_head':False}
    if not (.18*sp<=x1-x0<=.8*sp and .18*sp<=y1-y0<=.8*sp):return empty
    if not any(.5*sp<(h['box'][0]+h['box'][2])/2-cx<2*sp for h in neighbor_heads):return empty
    result=_staff_mask(image,(cx-.5*sp,staff.y0-.2*sp,cx+.5*sp,staff.y1+.2*sp),staff)
    if result is None:return empty
    mask,a,top,threshold=result;dots=[]
    if head_morphology(image,sym.box,threshold)['enclosed_white_area_fraction']>=.02:return empty
    for area,left,upper,right,lower in _components(mask):
        w,h=right-left,lower-upper
        if not (.2*sp<=w<=.8*sp and .2*sp<=h<=.8*sp and .6<=w/max(h,1)<=1.6
                and .04*sp*sp<=area<=.55*sp*sp):continue
        if left==0 or right==mask.shape[1] or upper==0 or lower==mask.shape[0]:continue
        dots.append({'box':[a+left,top+upper,a+right,top+lower],
                     'cx':a+(left+right)/2,'cy':top+(upper+lower)/2})
    group=sorted([d for d in dots if abs(d['cx']-cx)<.2*sp],key=lambda d:d['cy'])
    if len(group)<2 or not any(abs(d['cy']-cy)<.2*sp for d in group):return empty
    if not all(.75*sp<=b['cy']-a['cy']<=1.25*sp for a,b in zip(group,group[1:])):return empty
    barlines=[q.i for q in structural_symbols if q.cls.startswith('barLine') and q.p>=.5
              and min(abs(q.box[0]-cx),abs(q.box[2]-cx))<=1.5*sp]
    if len(group)<3:
        middle_spaces=all(abs(d['cy']-(staff.y0+offset*sp))<=.25*sp
                          for d,offset in zip(group,(1.5,2.5)))
        if not barlines or not middle_spaces:return empty
    return {'repeat_dot_head':True,'reason':'isolated_compact_dot_in_regular_repeat_column',
            'pixel_components':group,'nearby_barlines':barlines,'threshold':threshold}


def line_or_blemish_evidence(image,sym,staff,verification,morphology):
    """Require absence of a compact head after staff-line removal as well as
    independent no-head verification and absence of any enclosed counter.
    """
    empty={'line_or_blemish':False}
    if (verification.get('reason')!='no_head_ink' or verification.get('head_ink_fraction',1)>.2
            or morphology.get('enclosed_white_area_fraction',1)>=.02
            or morphology.get('central_ink_fraction',1)>=.35):return empty
    if not any(sym.box[1]<=staff.y0+j*staff.sp<=sym.box[3] for j in range(5)):return empty
    result=_staff_mask(image,sym.box,staff)
    if result is None:return empty
    mask,a,top,threshold=result;sp=staff.sp
    components=_components(mask)
    substantial=[c for c in components if c[3]-c[1]>=.35*sp and c[4]-c[2]>=.35*sp
                 and c[0]>=.04*sp*sp]
    if substantial:return empty
    return {'line_or_blemish':True,'empty_head_box':True,
            'reason':'staff_line_or_small_residual_without_compact_head_or_counter',
            'remaining_components':[{'area':c[0],'box':[a+c[1],top+c[2],a+c[3],top+c[4]]} for c in components],
            'verification':verification,'morphology':morphology,'threshold':threshold}


def proven_non_head(removal):
    """One evidence gate shared by generation and validation."""
    proof=removal.get('source_geometry_evidence',{})
    return bool((removal.get('reason')=='beam_stroke_misread_as_notehead' and proof.get('beam_region'))
        or (removal.get('reason')=='empty_source_box_misread_as_notehead' and proof.get('empty_head_box'))
        or (removal.get('reason')=='line_or_blemish_misread_as_notehead' and proof.get('line_or_blemish'))
        or (removal.get('reason')=='repeat_dot_misread_as_notehead' and proof.get('repeat_dot_head')))
