from fractions import Fraction
from types import SimpleNamespace as NS
import json
import numpy as np
from PIL import Image
from copisteria.write import Event
from source_rhythm_resolution import unique_physical_events,_non_tuplet_bars,resolved_duration_options
from source_bar_fit import source_bar_transform,source_fallback,encoded_voice_time
from run_local_recovery import ROOT,samples
from source_saved_events import source_saved_events
from replay_writer_trace import _reading


def test_overlapping_note_and_rest_are_one_head_even_with_different_voices():
    syms=[NS(box=(20,20,40,40),bar=0,cx=30,cy=30),NS(box=(21,20,40,41),bar=0,cx=30.5,cy=30.5),
          NS(box=(65,20,90,27),bar=0,cx=77.5,cy=23.5)]
    rd=NS(layout=NS(syms=syms,staves=[NS(sp=20)]))
    events={0:[Event(x=30,kind='rest',typ='half',si=0,voice=2),Event(x=30.5,kind='note',si=1),
               Event(x=77.5,kind='rest',typ='half',si=2)]}
    out,removed=unique_physical_events(events,rd)
    assert [e.si for e in out[0]]==[1,2]
    assert removed[0]['sym_id']==0 and removed[0]['note_kept']==1
    assert len(events[0])==3


def test_fast_note_head_and_stem_flag_rest_box_are_one_printed_object():
    syms=[NS(box=(20,20,40,40),bar=0,cx=30,cy=30),
          NS(box=(20,20,40,100),bar=0,cx=30,cy=60)]
    rd=NS(layout=NS(syms=syms,staves=[NS(sp=20)]))
    note=Event(x=30,kind='note',si=0,typ='eighth')
    shadow=Event(x=30,kind='rest',si=1,typ='eighth')
    out,removed=unique_physical_events({0:[note,shadow]},rd)
    assert [e.si for e in out[0]]==[0] and removed[0]['note_kept']==0
    # A tall quarter-rest alternative covering the same head/stem is also one
    # object. A separately positioned rest remains independent.
    shadow.typ='quarter'
    out,removed=unique_physical_events({0:[note,shadow]},rd)
    assert [e.si for e in out[0]]==[0] and removed
    syms[1].box=(50,20,70,100);syms[1].cx=60;shadow.x=60
    out,removed=unique_physical_events({0:[note,shadow]},rd)
    assert [e.si for e in out[0]]==[0,1] and not removed


def test_numeric_or_fractional_tuplet_support_vetoes_clearing():
    e=Event(x=30,kind='note',si=0,tup='3/2',dur=Fraction(2,3))
    rd=NS(layout=NS(syms=[NS(bar=0,staff=0,cls='note_quarter',p=1)]),
        tok={0:{'tup':{'v':'none','p':.999},'onset':0,'onset_p':.999}})
    assert (0,0) in _non_tuplet_bars(rd,{0:[e]})
    rd.tok[0]['onset']=1/3
    assert not _non_tuplet_bars(rd,{0:[e]})
    rd.tok[0]['onset']=0
    rd.layout.syms.append(NS(i=1,bar=0,staff=0,cls='tuplet_3',p=.9))
    assert not _non_tuplet_bars(rd,{0:[e]})


def test_source_repairs_survive_an_unresolved_other_event():
    events=[Event(x=20,kind='note',si=0,typ='half',dur=Fraction(2)),Event(x=40,kind='note',si=1,typ='whole',dur=Fraction(4))]
    fit,actions=source_fallback(events,{0:[{'typ':'quarter','duration':'1','weight':1,'reason':'source_filled'}]})
    assert [e.si for e in fit]==[0,1] and [e.dur for e in fit]==[1,4]
    assert actions[0]['applied_in_unresolved_voice']


def test_pickup_vote_uses_repaired_values_instead_of_clipped_input():
    staves=[NS(sp=20,system=0),NS(sp=20,system=0)]
    rd=NS(layout=NS(syms=[NS(staff=0,bar=0,cls='note_quarter'),NS(staff=1,bar=0,cls='note_quarter')],staves=staves,
          systems=[NS(staves=[0,1],columns=[[0],[0]])]),tok={})
    built=[[{'staves':[{'staff':k,'bar':0,'state':{'time':'4/4'},'marks':{'meter':True,'right':None},'voices':{}}]}] for k in range(2)]
    events={k:[Event(x=k*20,kind='note',si=k,typ='quarter',dur=Fraction(1))] for k in range(2)}
    choices={k:[{'typ':'whole','duration':'4','weight':1,'reason':'visible_hollow_stemless_head'}] for k in range(2)}
    _,cuts=source_bar_transform(rd,events,choices,[],opening_pickup=True,refine_timing=True)(built,'4/4')
    assert cuts==[Fraction(4)]


def test_short_common_bar_normalizes_measure_rest_trace_duration():
    rd=NS(layout=NS(syms=[NS(staff=k,bar=0,cls='note_half') for k in range(3)],
        staves=[NS(sp=20,system=0) for _ in range(3)],systems=[NS(staves=[0,1,2],columns=[[0],[0],[0]])]),tok={})
    built=[[{'staves':[{'staff':k,'bar':0,'state':{'time':'4/4'},'marks':{'meter':True,'right':None},'voices':{}}]}] for k in range(3)]
    events={0:[Event(x=20,kind='mrest',si=0,dur=Fraction(4))],
            1:[Event(x=20,kind='note',si=1,typ='half',dur=Fraction(2))],
            2:[Event(x=20,kind='note',si=2,typ='half',dur=Fraction(2))]}
    fitted,cuts=source_bar_transform(rd,events,{},[],opening_pickup=True,refine_timing=True)(built,'4/4')
    assert cuts==[Fraction(2)]
    assert fitted[0][0]['staves'][0]['voices'][1][0].dur==2


def test_chord_hold_and_trailing_forward_have_distinct_cursor_times():
    root=Event(x=20,kind='note',dur=Fraction(1))
    held=Event(x=20,kind='note',chord=True,dur=Fraction(3))
    assert encoded_voice_time([root,held],Fraction(4))==(Fraction(3),Fraction(1))
    forward=Event(x=21,kind='gap',dur=Fraction(3))
    assert encoded_voice_time([root,held,forward],Fraction(4))==(Fraction(4),Fraction(4))


def test_cached_whole_and_short_stub_source_controls_remain_in_their_family():
    parent=ROOT/'experiments/proposal-rhythm/final-0318d4f06bb9/predictions'
    targets={'Never Part':[(522,'half')],'Newburgh':[(727,'whole')],'Chambers':[(568,'whole')],
             'Wells':[(67,'half'),(162,'whole')],'The Golden Harp':[(293,'half')]}
    for sample in samples():
        if sample['title'] not in targets:continue
        image=Image.open(ROOT/sample['input']).convert('L');trace=json.loads((parent/f"{sample['id']}.trace.json").read_text())
        rd=_reading(trace,image);events,_=source_saved_events(trace,(parent/f"{sample['id']}.musicxml").read_text())
        options=resolved_duration_options(rd,np.asarray(image),events)
        for sid,expected in targets[sample['title']]:
            assert {o['typ'] for o in options[sid]['options']}=={expected},(sample['title'],options[sid])


def test_cached_duane_repeat_dots_empty_box_and_beam_endpoints():
    sample=next(s for s in samples() if s['title']=='Duane Street')
    parent=ROOT/'experiments/proposal-rhythm/final-0318d4f06bb9/predictions'
    image=Image.open(ROOT/sample['input']).convert('L')
    trace=json.loads((parent/f"{sample['id']}.trace.json").read_text())
    rd=_reading(trace,image)
    events,_=source_saved_events(trace,(parent/f"{sample['id']}.musicxml").read_text())
    cleaned,removed=unique_physical_events(events,rd,np.asarray(image))
    assert any(r['sym_id']==519 and r['reason']=='empty_source_box_misread_as_notehead' for r in removed)
    assert not any(e.si==519 for rows in cleaned.values() for e in rows)
    # The neighboring printed heads survive the empty-box rejection.
    assert {289,362,372,563,495}<={e.si for rows in cleaned.values() for e in rows if e.kind=='note'}
    options=resolved_duration_options(rd,np.asarray(image),cleaned)
    for sid in (437,247,219,254):
        assert {(o['typ'],o['dots'],o['duration']) for o in options[sid]['options']}=={('half',0,'2')}
        assert options[sid]['evidence']['source_dot_resolution']['separate_vertical_repeat_dot_column']
    for sid in (563,495):
        assert {(o['typ'],o['duration']) for o in options[sid]['options']}=={('eighth','1/2')}
        proof=options[sid]['evidence']['source_beam_resolution']
        assert proof['beam_id']==487 and proof['pixel_beam_evidence']['beam_region']
