"""Source-pixel evidence that a proposed fast head is part of a beam stroke."""
from __future__ import annotations
import numpy as np


def beam_region_evidence(image,box,sp,other_heads,require_exterior=True):
    x0,y0,x1,y1=map(float,box);sp=float(sp);pixels=np.asarray(image)
    empty={'beam_region':False,'reason':'no_long_thick_stroke_with_two_other_heads'}
    if pixels.ndim!=2 or sp<=0:return empty
    a=max(0,int(x0-1.7*sp));b=min(pixels.shape[1],int(x1+1.7*sp))
    top=max(0,int(y0-1.1*sp));bottom=min(pixels.shape[0],int(y1+1.1*sp))
    if b-a<2*sp:return empty
    crop=pixels[top:bottom,a:b];cut=float(np.clip(np.percentile(crop,90)-40,130,205));ink=crop<cut
    xs=np.arange(a,b);cx=(x0+x1)/2;radius=max(2,int(round(.09*sp)))
    best=None
    for slope in np.arange(-.6,.601,.1):
        for intercept in np.arange(y0,y1+.01,.1*sp):
            ys=np.rint(intercept+slope*(xs-cx)).astype(int)-top
            valid=(ys-radius>=0)&(ys+radius<ink.shape[0]);support=np.zeros(len(xs),dtype=bool)
            inds=np.flatnonzero(valid)
            if not len(inds):continue
            sample=np.stack([ink[ys[inds]+off,inds] for off in range(-radius,radius+1)])
            support[inds]=sample.mean(axis=0)>=.85
            # A beam may be interrupted by a thin broken scan column.
            gap=max(1,int(round(.10*sp)));start=last=None;runs=[]
            for j,present in enumerate(support):
                if present:
                    if start is None:start=j
                    last=j
                elif start is not None and j-last>gap:
                    runs.append((a+start,a+last+1));start=last=None
            if start is not None:runs.append((a+start,a+last+1))
            for left,right in runs:
                overlap=max(0,min(right,x1)-max(left,x0))
                if right-left<1.8*sp or overlap<(.35 if require_exterior else .6)*(x1-x0):continue
                if require_exterior and max(x0-left,right-x1)<.6*sp:continue
                peers=[]
                for h in other_heads:
                    hx0,hy0,hx1,hy1=h['box'];hc=(hx0+hx1)/2;hy=(hy0+hy1)/2
                    by=intercept+slope*(hc-cx)
                    # Stems attach at a head edge. A beam ending at the left
                    # edge of its final head need not reach the head center.
                    edge_attached=any(left-.3*sp<=x<=right+.3*sp for x in (hx0,hc,hx1))
                    if edge_attached and 1.2*sp<=abs(hy-by)<=4.2*sp:
                        peers.append(h)
                if len(peers)<2 or max(h['x'] for h in peers)-min(h['x'] for h in peers)<.6*sp:continue
                candidate={'beam_region':True,'reason':'long_thick_beam_stroke_and_two_separate_noteheads',
                    'stroke_x':[left,right],'slope':round(float(slope),3),'center_y':round(float(intercept),2),
                    'length_staff_spaces':round((right-left)/sp,3),'overlap_head_fraction':round(overlap/(x1-x0),3),
                    'other_head_ids':[h['si'] for h in peers],'threshold':cut}
                if best is None or candidate['length_staff_spaces']>best['length_staff_spaces']:best=candidate
    return best or empty
