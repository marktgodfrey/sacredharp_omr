"""Source-meter-constrained bar timing without copied fragment lengths.

All selected physical note events are kept. Duration alternatives require
separate source evidence; an impossible bar is reported, never silently clipped.
"""
from __future__ import annotations
import copy
import itertools
import math
from collections import Counter,defaultdict
from fractions import Fraction


def shared_onset_anchors(rd, events, cap, trusted_only=False):
    """Use only agreeing parallel-staff onsets, rejecting reset/ordering conflicts."""
    points=[]
    for e in events:
        if e.si<0 or e.kind not in ('note','rest'):continue
        r=rd.tok.get(e.si,{})
        if trusted_only:
            sym=rd.layout.syms[e.si]
            if (e.kind!='note' or not sym.cls.startswith('note_') or not r.get('cls',{}).get('v','').startswith('note_')
                    or r.get('cls',{}).get('p',0)<.9 or r.get('real',{}).get('p',0)<.9):continue
        if r.get('onset_p',0)<.9 or r.get('onset') is None:continue
        onset=Fraction(round(r['onset']*48),48)
        if not 0<=onset<cap:continue
        s=rd.layout.syms[e.si];points.append((e.x,s.staff,onset,r['onset_p']))
    sp=sum(s.sp for s in rd.layout.staves)/max(1,len(rd.layout.staves))
    clusters=[]
    for p in sorted(points):
        if clusters and p[0]-clusters[-1][0][0]<=.45*sp:clusters[-1].append(p)
        else:clusters.append([p])
    anchors=[]
    for group in clusters:
        votes=defaultdict(set)
        for x,staff,onset,p in group:votes[onset].add(staff)
        ranked=sorted(votes,key=lambda v:-len(votes[v]))
        if len(votes[ranked[0]])<2 or len(ranked)>1 and len(votes[ranked[0]])==len(votes[ranked[1]]):continue
        onset=ranked[0];anchors.append((sum(p[0] for p in group)/len(group),onset))
    if any(a[1]>=b[1] for a,b in zip(anchors,anchors[1:])):
        return [],'nonmonotonic_prior_onsets'
    return anchors,'parallel_source_onsets'


def _options(e, choices):
    from copisteria import write
    options=choices.get(e.si)
    if isinstance(options,dict):options=options.get('options')
    if not options:
        return [{'typ':e.typ,'dots':e.dots,'tup':e.tup,'duration':str(e.dur),'weight':1.,'reason':'saved_event'}]
    result=[]
    for option in options:
        if option.get('weight',1)<=0:continue
        o=dict(option)
        if 'duration' not in o:
            same=(o['typ'],o.get('dots',e.dots),o.get('tup',e.tup))==(e.typ,e.dots,e.tup)
            o['duration']=str(e.dur if same else write._duration(o['typ'],o.get('dots',e.dots),o.get('tup',e.tup)))
        result.append(o)
    return result


def fit_voice(events, cap, choices, anchors=(), sp=30, preserve_onsets=False):
    """Bounded duration DP; no event omission or fabricated tuplets/voices."""
    from copisteria import write
    events=copy.deepcopy(events);roots=[e for e in events if not e.chord]
    members=defaultdict(list)
    for e in events:
        if not e.chord:continue
        near=[r for r in roots if r.kind=='note' and abs(r.x-e.x)<=1.5*sp]
        if near:members[id(min(near,key=lambda r:abs(r.x-e.x)))].append(e)
        else:e.chord=False;roots.append(e)
    roots.sort(key=lambda e:e.x)
    # Full-measure rest interpretations cannot share one voice with music.
    conflicts=[e.si for e in roots if e.kind=='mrest' and any(r.kind=='note' for r in roots)]
    roots=[e for e in roots if e.si not in conflicts]
    # Saved selected XML onsets are preferable to speculative neural onsets in
    # a bar whose physical membership has not changed. Preserve them only when
    # all durations are unchanged and fit inside the new shared capacity.
    if preserve_onsets and all(e.kind!='mrest' and e.onset is not None and 0<=Fraction(str(e.onset))+e.dur<=cap
                               and any((o['typ'],o.get('dots',e.dots),o.get('tup',e.tup),Fraction(o['duration']))
                                       ==(e.typ,e.dots,e.tup,e.dur) for o in _options(e,choices)) for e in roots):
        out=[];cursor=Fraction(0);valid=True
        for e in roots:
            start=Fraction(str(e.onset)).limit_denominator(192)
            if start<cursor:valid=False;break
            if start>cursor:out.append(write.Event(x=e.x-.01,kind='gap',dur=start-cursor,voice=e.voice))
            e.onset=None;e.dist=None;e.onset_p=0
            out.extend([e,*members.get(id(e),[])]);cursor=start+e.dur
        if valid:
            return out,{'resolved':True,'duration_actions':[],'end':str(cursor),'fit_cost':0.,
                        'measure_rest_conflicts':conflicts,'preserved_selected_xml_onsets':True}
    states={Fraction(0):(0.,[],[])}
    for e in roots:
        new={}
        opts=_options(e,choices)
        for cursor,(cost,out,actions) in states.items():
            starts=[(cursor,0.)]
            near=[a for a in anchors if abs(a[0]-e.x)<=.5*sp]
            if near:
                desired=min(near,key=lambda a:abs(a[0]-e.x))[1]
                starts=[(cursor,1.5*float(abs(desired-cursor)))]
                if desired>cursor:starts.append((desired,.05*float(desired-cursor)))
            for opt,(start,gap_cost) in itertools.product(opts,starts):
                d=cap if e.kind=='mrest' else Fraction(str(opt.get('duration',write._duration(opt['typ'],opt.get('dots',e.dots),opt.get('tup',e.tup)))))
                if start+d>cap:continue
                selected=copy.deepcopy(e);selected.typ=opt['typ'];selected.dots=opt.get('dots',e.dots);selected.tup=opt.get('tup',e.tup)
                selected.dur=d;selected.onset=None;selected.dist=None;selected.onset_p=0
                extra=[];child_actions=[];child_cost=0.;valid=True
                for child in members.get(id(e),[]):
                    child_opts=_options(child,choices)
                    feasible=[o for o in child_opts if start+Fraction(str(o.get('duration',child.dur)))<=cap]
                    if not feasible:valid=False;break
                    o=max(feasible,key=lambda o:o.get('weight',1.));c=copy.deepcopy(child)
                    c.typ=o['typ'];c.dots=o.get('dots',c.dots);c.tup=o.get('tup',c.tup);c.dur=Fraction(str(o.get('duration',child.dur)))
                    c.onset=None;c.dist=None;c.onset_p=0;extra.append(c)
                    child_cost-=math.log(max(o.get('weight',1.),1e-12))
                    if (c.typ,c.dots,c.tup,c.dur)!=(child.typ,child.dots,child.tup,child.dur):
                        child_actions.append({'sym_id':c.si,'from':[child.typ,child.dots,child.tup,str(child.dur)],'to':[c.typ,c.dots,c.tup,str(c.dur)],'reason':o.get('reason')})
                if not valid:continue
                notes=copy.deepcopy(out)
                if start>cursor:notes.append(write.Event(x=e.x-.01,kind='gap',dur=start-cursor,voice=e.voice))
                notes.extend([selected,*extra]);act=list(actions)+child_actions
                if (selected.typ,selected.dots,selected.tup,selected.dur)!=(e.typ,e.dots,e.tup,e.dur):
                    act.append({'sym_id':e.si,'from':[e.typ,e.dots,e.tup,str(e.dur)],'to':[selected.typ,selected.dots,selected.tup,str(selected.dur)],'reason':opt.get('reason')})
                score=cost+gap_cost+child_cost-math.log(max(opt.get('weight',1.),1e-12))
                end=start+d
                if end not in new or score<new[end][0]:new[end]=(score,notes,act)
        states=dict(sorted(new.items(),key=lambda item:item[1][0])[:256])
        if not states:
            return None,{'resolved':False,'reason':'no_source_supported_duration_fit','source_ids':[r.si for r in roots],
                         'required_meter_quarters':str(cap),'measure_rest_conflicts':conflicts}
    end,(score,out,actions)=min(states.items(),key=lambda item:item[1][0]+.02*float(cap-item[0]))
    return out,{'resolved':True,'duration_actions':actions,'end':str(end),'fit_cost':score,'measure_rest_conflicts':conflicts}


def packed(events):
    """Preserve source values for unresolved diagnostics, removing stale gaps."""
    out=[]
    for e in sorted(copy.deepcopy(events),key=lambda e:e.x):
        e.onset=None;e.dist=None;e.onset_p=0;out.append(e)
    return out


def source_fallback(events,choices):
    """Keep evidence-backed repairs even if another event prevents a full fit."""
    out=packed(events);actions=[]
    out=[e for e in out if not(e.kind=='mrest' and any(f.kind=='note' and f.voice==e.voice for f in out))]
    for e in out:
        opts=_options(e,choices)
        exact=[o for o in opts if (o['typ'],o.get('dots',e.dots),o.get('tup',e.tup),Fraction(o['duration']))==(e.typ,e.dots,e.tup,e.dur)]
        if exact or not opts:continue
        o=max(opts,key=lambda o:o.get('weight',1));before=[e.typ,e.dots,e.tup,str(e.dur)]
        e.typ=o['typ'];e.dots=o.get('dots',e.dots);e.tup=o.get('tup',e.tup);e.dur=Fraction(o['duration'])
        actions.append({'sym_id':e.si,'from':before,'to':[e.typ,e.dots,e.tup,str(e.dur)],'reason':o.get('reason'),
                        'applied_in_unresolved_voice':True})
    return out,actions


def encoded_voice_time(events,mrest_len):
    """Track XML cursor and held chord duration separately."""
    cursor=root=end=Fraction(0)
    for e in events:
        if e.kind=='gap':cursor+=e.dur;end=max(end,cursor);continue
        duration=mrest_len if e.kind=='mrest' else e.dur
        if e.chord:onset=root
        else:onset=root=cursor;cursor+=duration
        end=max(end,onset+duration)
    return end,cursor


def source_bar_transform(rd,events_by_staff,choices,decisions,*,parent_measures=None,opening_pickup=False,refine_timing=False,reset_onset_ids=()):
    """Fit each shared physical bar once; fragment cut lengths never enter."""
    from copisteria import write
    L=rd.layout
    by_bar=defaultdict(list)
    for staff,events in events_by_staff.items():
        for e in events:
            if e.si>=0:by_bar[staff,L.syms[e.si].bar].append(e)

    def transform(built,opening):
        selected=copy.deepcopy(built);n=max((len(p) for p in selected),default=0);cuts=[]
        for m in range(n):
            rows=[]
            for part,measures in enumerate(selected,1):
                if m>=len(measures):continue
                for row in measures[m]['staves']:
                    if row is not None:rows.append((part,row))
            if not rows:cuts.append(None);continue
            meter_counts=Counter(row['state']['time'] for _,row in rows)
            meter=meter_counts.most_common(1)[0][0];nominal=write._time_len(meter)
            staff_events={}
            for part,row in rows:
                sid,j=row['staff'],row['bar'];st=L.staves[sid];sy=L.systems[st.system];cols=sy.columns[sy.staves.index(sid)]
                merged=[b for b,c in enumerate(cols) if c==cols[j]]
                staff_events[sid]=[e for b in merged for e in by_bar[sid,b]]
            all_events=[e for evs in staff_events.values() for e in evs]
            anchors,anchor_kind=shared_onset_anchors(rd,all_events,nominal,trusted_only=refine_timing)
            # Only source-marked opening/terminal bars can be a short complement.
            eligible=(m==0 and opening_pickup) or any(row['marks']['right'] in write.SHORT_RIGHT for _,row in rows)
            votes=Counter()
            same_bar=bool(parent_measures) and len({parent_measures.get(e.si) for e in all_events})==1
            if eligible:
                for sid,evs in staff_events.items():
                    primary=[e for e in evs if e.voice==1 and not e.chord and e.grace=='none']
                    length=(max((Fraction(str(e.onset)).limit_denominator(192)+e.dur for e in primary),default=Fraction(0))
                            if same_bar and all(e.onset is not None for e in primary)
                            else sum((e.dur for e in primary if e.kind!='mrest'),Fraction(0)))
                    if primary and all(e.kind!='mrest' for e in primary) and 0<length<=nominal:votes[length]+=1
            cap=nominal
            if votes and not refine_timing:
                short,count=votes.most_common(1)[0]
                if count>=2 and short<nominal:cap=short
            unresolved=[];details=[]
            for part,row in rows:
                sid=row['staff'];voices=defaultdict(list)
                for e in staff_events[sid]:voices[e.voice].append(e)
                fitted={}
                for voice,evs in voices.items():
                    preserve=same_bar and not any(e.si in reset_onset_ids for e in all_events)
                    fit,detail=fit_voice(evs,cap,choices,anchors,L.staves[sid].sp,preserve_onsets=preserve)
                    detail.update(part=part,staff=sid,bar=row['bar'],voice=voice)
                    if fit is None:
                        unresolved.append(detail)
                        if refine_timing:
                            fit,actions=source_fallback(evs,choices);detail['duration_actions']=actions
                        else:fit=packed(evs)
                    fitted[voice]=fit;details.append(detail)
                row['voices']=fitted
            if refine_timing and eligible and not unresolved:
                # Decide pickup/complement length after source values are
                # repaired. Previously clipped quarters cannot vote a printed
                # whole head back down to a one-beat pickup.
                votes=Counter();ends=[]
                for _,row in rows:
                    primary=row['voices'].get(1,[])
                    if primary and not any(e.kind=='mrest' for e in primary):
                        end=encoded_voice_time(primary,nominal)[0]
                        if end>0:votes[end]+=1;ends.append(end)
                if votes:
                    short,count=votes.most_common(1)[0]
                    all_ends=[encoded_voice_time(evs,nominal)[0] for _,row in rows for evs in row['voices'].values()
                              if any(e.kind in ('note','rest') for e in evs)]
                    if count>=2 and short<nominal and max(all_ends or ends)<=short:cap=short
            cut=cap
            if unresolved:
                # Keep every prior physical head and expose residual overflow;
                # it is never labelled as a successful meter-constrained fit.
                cut=max([cap]+[(encoded_voice_time(evs,cap)[0] if refine_timing else write._voice_starts(evs,cap)[1])
                              for _,row in rows for evs in row['voices'].values()])
            # The serializer normally leaves opening/repeat voices short even
            # when an explicit common cut was selected. Materialize remaining
            # time as a forward, so every part shares the actual encoded bar
            # length without inventing a visible rest or a missing note.
            for _,row in rows:
                for voice,evs in row['voices'].items():
                    if refine_timing:
                        for e in evs:
                            if e.kind=='mrest':e.dur=cut
                    end=encoded_voice_time(evs,cut)[1] if refine_timing else write._voice_starts(evs,cut)[1]
                    if end<cut:
                        evs.append(write.Event(x=max((e.x for e in evs),default=0)+.01,
                            kind='gap',dur=cut-end,voice=voice))
            cuts.append(cut)
            decisions.append({'column':m,'meter':meter,'nominal_quarters':str(nominal),'selected_cut':str(cut),
                'short_source_complement':cap<nominal,'source_onset_anchors':[(x,str(t)) for x,t in anchors],
                'anchor_policy':anchor_kind,'resolved':not unresolved,'unresolved':unresolved,'voice_fits':details,
                'fragment_cut_sum_used':False})
        return selected,cuts
    return transform
