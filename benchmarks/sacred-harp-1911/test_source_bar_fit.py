from fractions import Fraction
from types import SimpleNamespace as NS
from copisteria.write import Event
from source_bar_fit import fit_voice, shared_onset_anchors, source_bar_transform


def note(i,dur=1,x=None):
    return Event(x=float(i*30 if x is None else x),kind='note',si=i,typ='quarter',dur=Fraction(dur))


def test_voice_fit_keeps_all_heads_and_uses_only_source_supported_changes():
    ev=[note(0,2),note(1,Fraction(1,2)),note(2,Fraction(1,2))]
    ev[0].typ='half';ev[1].typ=ev[2].typ='eighth'
    out,d=fit_voice(ev,Fraction(2),{0:[{'typ':'quarter','duration':'1','weight':1,'reason':'source_filled_head'}]})
    assert d['resolved'] and [e.si for e in out]==[0,1,2]
    assert sum(e.dur for e in out)==2 and out[0].typ=='quarter'
    assert ev[0].typ=='half'


def test_impossible_whole_is_not_silently_shortened_or_omitted():
    e=note(0,4);e.typ='whole'
    out,d=fit_voice([e],Fraction(2),{})
    assert out is None and not d['resolved'] and d['source_ids']==[0]


def test_parallel_onset_resets_cannot_create_artificial_tuplets():
    ev=[note(i,x=x) for i,x in enumerate((10,10,90,90))]
    rd=NS(layout=NS(staves=[NS(sp=20),NS(sp=20)],syms=[NS(staff=i%2) for i in range(4)]),
          tok={i:{'onset':0,'onset_p':.999} for i in range(4)})
    anchors,reason=shared_onset_anchors(rd,ev,Fraction(4))
    assert anchors==[] and reason=='nonmonotonic_prior_onsets'
    out,d=fit_voice([note(0),note(1)],Fraction(2),{})
    assert d['resolved'] and all(e.tup=='none' for e in out)


def test_merged_fragments_do_not_sum_copied_column_lengths():
    sy=NS(staves=[0],columns=[[0,0,0]])
    st=NS(sp=20,system=0)
    rd=NS(layout=NS(syms=[NS(staff=0,bar=0),NS(staff=0,bar=2)],staves=[st],systems=[sy]),tok={})
    rows=[[{'staves':[{'staff':0,'bar':0,'state':{'time':'4/4'},'marks':{'meter':False,'right':None},'voices':{}}]}]]
    ev=[note(0,2),note(1,2)];ev[0].typ=ev[1].typ='half';decisions=[]
    transform=source_bar_transform(rd,{0:ev},{},decisions)
    selected,cuts=transform(rows,'4/4')
    assert cuts==[Fraction(4)] and decisions[0]['resolved']
    assert [e.si for e in selected[0][0]['staves'][0]['voices'][1]]==[0,1]


def test_saved_selected_onsets_preserve_real_gaps_without_neural_retiming():
    ev=[note(0),note(1)];ev[0].onset=0;ev[1].onset=2
    out,d=fit_voice(ev,Fraction(4),{},anchors=[(30,Fraction(1))],preserve_onsets=True)
    assert d['preserved_selected_xml_onsets']
    assert [(e.kind,e.dur) for e in out]==[('note',1),('gap',1),('note',1)]
    assert d['end']=='3'


def test_optional_dot_alternative_cannot_retime_an_already_fitting_selected_voice():
    first=note(0,3);first.typ='half';first.dots=1;first.onset=0
    second=note(1);second.onset=3
    choices={0:[{'typ':'half','dots':1,'tup':'none','weight':1},
                {'typ':'half','dots':0,'tup':'none','weight':.25}]}
    out,d=fit_voice([first,second],Fraction(4),choices,anchors=[(30,Fraction(2))],preserve_onsets=True)
    assert d['preserved_selected_xml_onsets'] and not d['duration_actions']
    assert [(e.typ,e.dots,e.dur) for e in out]==[('half',1,3),('quarter',0,1)]


def test_agreeing_incomplete_opening_does_not_invent_a_pickup():
    staves=[NS(sp=20,system=0),NS(sp=20,system=0)]
    rd=NS(layout=NS(syms=[NS(staff=0,bar=0),NS(staff=1,bar=0)],staves=staves,
          systems=[NS(staves=[0,1],columns=[[0],[0]])]),tok={})
    rows=[[{'staves':[{'staff':k,'bar':0,'state':{'time':'4/4'},
             'marks':{'meter':True,'right':None},'voices':{}}]}] for k in range(2)]
    ev={k:[note(k,2)] for k in range(2)};decisions=[]
    selected,cuts=source_bar_transform(rd,ev,{},decisions)(rows,'4/4')
    assert cuts==[Fraction(4)] and not decisions[0]['short_source_complement']
    for measures in selected:
        voice=measures[0]['staves'][0]['voices'][1]
        assert voice[-1].kind=='gap' and voice[-1].dur==2
    _,cuts=source_bar_transform(rd,ev,{},[] ,opening_pickup=True)(rows,'4/4')
    assert cuts==[Fraction(2)]
