"""Source-pixel evidence that a proposed fast head is part of a beam stroke."""
from __future__ import annotations
import numpy as np


def _endpoint_stem(ink, xoff, yoff, edge, beam_y, head_y, sp):
    """A short connector needs actual ink joining a beam end to a head edge."""
    xa=max(0,int(round(edge-xoff-.12*sp)));xb=min(ink.shape[1],int(round(edge-xoff+.12*sp))+1)
    lo,hi=sorted((beam_y,head_y))
    ya=max(0,int(round(lo-yoff)));yb=min(ink.shape[0],int(round(hi-yoff))+1)
    if xb<=xa or yb-ya<1.2*sp:return None
    coverage=float(ink[ya:yb,xa:xb].any(axis=1).mean())
    return {'x':round(edge,2),'coverage':round(coverage,3)} if coverage>=.7 else None


def beam_region_evidence(image,box,sp,other_heads,require_exterior=True):
    x0,y0,x1,y1=map(float,box);sp=float(sp);pixels=np.asarray(image)
    empty={'beam_region':False,'reason':'no_long_thick_stroke_with_two_other_heads'}
    if pixels.ndim!=2 or sp<=0:return empty
    a=max(0,int(x0-1.7*sp));b=min(pixels.shape[1],int(x1+1.7*sp))
    nearby=[h['box'] for h in other_heads if a<=h['x']<=b and
            abs((h['box'][1]+h['box'][3])/2-(y0+y1)/2)<=4.2*sp]
    top=max(0,int(min([y0-1.1*sp]+[h[1] for h in nearby])))
    bottom=min(pixels.shape[0],int(max([y1+1.1*sp]+[h[3] for h in nearby])))
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
                if right-left<1.25*sp or overlap<(.35 if require_exterior else .6)*(x1-x0):continue
                long_stroke=(right-left>=1.8*sp and
                    (not require_exterior or max(x0-left,right-x1)>=.6*sp))
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
                endpoint_stems=[]
                if not long_stroke:
                    # A beam between adjacent heads need not extend beyond its
                    # erroneous head box. Require both physical stem endpoints,
                    # rather than relaxing the long-beam rule for all strokes.
                    for h in peers:
                        hx0,hy0,hx1,hy1=h['box'];hy=(hy0+hy1)/2
                        edge=hx1 if hy>intercept else hx0
                        by=intercept+slope*(edge-cx)
                        if min(abs(edge-left),abs(edge-right))>.3*sp:continue
                        stem=_endpoint_stem(ink,a,top,edge,by,hy,sp)
                        if stem:endpoint_stems.append({'si':h['si'],**stem,'head_below':bool(hy>by)})
                    pairs=[(l,r) for l in endpoint_stems for r in endpoint_stems
                           if r['x']-l['x']>=.6*sp and abs(l['x']-left)<=.3*sp
                           and abs(r['x']-right)<=.3*sp and l['head_below']==r['head_below']]
                    if not pairs:continue
                candidate={'beam_region':True,'reason':'long_thick_beam_stroke_and_two_separate_noteheads',
                    'stroke_x':[left,right],'slope':round(float(slope),3),'center_y':round(float(intercept),2),
                    'length_staff_spaces':round((right-left)/sp,3),'overlap_head_fraction':round(overlap/(x1-x0),3),
                    'other_head_ids':[h['si'] for h in peers],'threshold':cut}
                if not long_stroke:
                    candidate.update(reason='short_thick_connector_with_two_attached_head_stems',
                                     endpoint_stems=endpoint_stems)
                if best is None or candidate['length_staff_spaces']>best['length_staff_spaces']:best=candidate
    return best or empty
