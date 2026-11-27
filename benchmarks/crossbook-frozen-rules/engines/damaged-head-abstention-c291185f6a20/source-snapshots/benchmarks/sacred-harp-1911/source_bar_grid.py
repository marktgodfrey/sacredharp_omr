"""Opt-in common source bar partitions, preserving physical symbol identities."""
from __future__ import annotations
import copy
from fractions import Fraction
import xml.etree.ElementTree as ET
import numpy as np


def saved_source_states(rd, xml):
    """Map selected XML key/clef states to the old physical staff bars."""
    from copisteria import write
    L=rd.layout;plans=write._plan_parts(rd);places=write._align_systems(rd,plans,[])
    columns=[(i,c) for i,sy in enumerate(L.systems)
             for c in range(1+max((max(v) for v in sy.columns if v),default=-1))]
    result={}
    for plan,part in zip(plans,ET.fromstring(xml).findall('part')):
        state=[{'key':0,'clef':'G2'} for _ in plan.staves]
        for mi,measure in enumerate(part.findall('measure')):
            if mi>=len(columns):break
            si,col=columns[mi];sy=L.systems[si];attrs=measure.find('attributes')
            if attrs is not None:
                key=attrs.findtext('key/fifths')
                if key is not None:
                    for s in state:s['key']=int(key)
                for ce in attrs.findall('clef'):
                    slot=int(ce.get('number','1'))-1
                    if slot>=len(state):continue
                    sign,line=ce.findtext('sign'),ce.findtext('line','')
                    base=sign+line if sign in ('G','F','C') else 'perc' if sign=='percussion' else 'G2'
                    octc=ce.findtext('clef-octave-change')
                    if octc in ('-1','1','-2','2'):base += {'-1':'_8b','1':'_8a','-2':'_15b','2':'_15a'}[octc]
                    state[slot]['clef']=base
            for slot,pos in enumerate(plan.staves):
                staff=places[si].get(pos)
                if staff is None:continue
                cols=sy.columns[sy.staves.index(staff)]
                for bar,c in enumerate(cols):
                    if c==col:result[staff,bar]=copy.deepcopy(state[slot])
    return result


def rebuild_source_bars(rd,image,events_by_staff,xml):
    """Apply ink-voted shared cuts, retaining firm narrow ending bars.

    The existing segmenter provides candidates. Current cuts are additionally
    retained only when at least three quarters of source staves have a vertical
    stroke spanning three quarters of the staff. Broken print and slanted
    barlines need this tolerance; note stems alone cover less of the staff.
    Every new head is appended; source note IDs/boxes/staff identities stay fixed.
    """
    from copisteria import front
    from copisteria.vocab import CLS_ID
    L=rd.layout;old=copy.deepcopy(L);tok=copy.deepcopy(rd.tok)
    states=saved_source_states(rd,xml);mask=front.ink_mask(np.asarray(image.convert('L')))
    diagnostics=[]
    for si,sy in enumerate(L.systems):
        if len(sy.staves) not in (3,4):
            diagnostics.append({'system':si,'status':'outside_3_4_staff_scope'});continue
        group=sy.staves;sp=float(np.median([L.staves[k].sp for k in group]))
        candidate=copy.deepcopy(L)
        front._segment(candidate.syms,candidate.staves,candidate.systems[si],mask)
        ref=group[0];bb=[candidate.syms[i].box for i in candidate.staves[ref].bars]
        left,right=bb[0][0],bb[-1][2]
        cuts=[b[2] for b in bb[:-1]]
        oldcuts=[old.syms[i].box[2] for k in group for i in old.staves[k].bars[:-1]]
        additions=[]
        for x in oldcuts:
            if not left+sp<x<right-.5*sp:continue
            if any(L.syms[e.si].box[0]+.2*sp<x<L.syms[e.si].box[2]-.2*sp
                   for k in group for e in events_by_staff.get(k,[]) if e.kind=='note' and e.si>=0):
                continue
            support=[max(front._ink_run(mask,xx,L.staves[k].y0+1,L.staves[k].y1-1,reach=2)
                         for xx in (x-.2*sp,x,x+.2*sp)) for k in group]
            if sum(v>=.75 for v in support)>=.75*len(group):
                cuts.append(x);additions.append({'x':x,'vertical_coverage':support})
        clusters=[]
        for x in sorted(cuts):
            if clusters and x-clusters[-1][-1]<.5*sp:clusters[-1].append(x)
            else:clusters.append([x])
        cuts=[float(np.median(c)) for c in clusters]
        # Thin duplicate strokes and repeat-dot slivers do not create measures.
        xs=[left,*cuts,right]
        music=[e.x for k in group for e in events_by_staff.get(k,[]) if e.kind in ('note','rest','mrest')]
        j=0
        while j<len(xs)-1:
            a,b=xs[j:j+2]
            if b-a<sp and not any(a<=x<=b for x in music) and len(xs)>2:
                del xs[j+1 if j==0 else j];j=max(0,j-1)
            else:j+=1
        diag={'system':si,'old_bar_counts':[len(old.staves[k].bars) for k in group],
              'new_bar_count':len(xs)-1,'cuts':xs,'retained_firm_narrow_boundaries':additions}
        for k in group:
            st=L.staves[k];before=old.staves[k];new=[]
            for j,(a,b) in enumerate(zip(xs,xs[1:])):
                old_i=max(before.bars,key=lambda i:min(old.syms[i].box[2],b)-max(old.syms[i].box[0],a))
                i=len(L.syms);L.syms.append(front.Sym(i,'measure',{CLS_ID['measure']:1.},0.,0,
                    (a,st.y0,b,st.y1),staff=k,bar=j,synthetic=True))
                r=copy.deepcopy(tok[old_i]);r['cls']={'v':'measure'};r['real']={'p':1.}
                r['time']={'v':None,'p':1.}
                state=states.get((k,old.syms[old_i].bar),{})
                for attr in ('key','clef'):
                    if attr in state:r[attr]={'v':state[attr],'p':1.,'selected_xml_state':True}
                rd.tok[i]=r;new.append(i)
            st.bars=new;st.x0,st.x1=left,right
            for sym in L.syms:
                if sym.staff==k and sym.fam!='measure':
                    sym.bar=min(range(len(new)),key=lambda j:max(xs[j]-sym.cx,sym.cx-xs[j+1],0))
        sy.columns=[list(range(len(xs)-1)) for k in group]
        diagnostics.append(diag)
    return diagnostics
