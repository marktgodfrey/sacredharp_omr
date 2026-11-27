import json
import os
import sys
from types import SimpleNamespace

from PIL import Image

ROOT=os.path.dirname(__file__)
sys.path.insert(0,os.path.join(ROOT,'..','..','copisteria','src'))
sys.path.insert(0,ROOT)
from source_saved_events import source_saved_events
from source_duration_options import source_duration_options
from copisteria.write import Event

PRED=os.path.join(ROOT,'experiments/proposal-rhythm/final-0318d4f06bb9/predictions')
SOURCES=os.path.join(ROOT,'sources')


def _load(stem, sourcefile):
    from run_local_recovery import samples
    trace=json.load(open(os.path.join(PRED,stem+'.trace.json'),encoding='utf-8'))
    xml=open(os.path.join(PRED,stem+'.musicxml'),encoding='utf-8').read()
    syms=[]
    for s in trace['syms']:
        cls=s['cls']
        syms.append(SimpleNamespace(**{**s,'fam':cls.split('_')[0],
            'cx':(s['box'][0]+s['box'][2])/2}))
    staves=[SimpleNamespace(**s) for s in trace['staves']]
    layout=SimpleNamespace(syms=syms,staves=staves,
        bar_box=lambda sid,bar:syms[staves[sid].bars[bar]].box)
    rd=SimpleNamespace(layout=layout,tok={int(k):v for k,v in trace['tokens'].items()})
    events,_=source_saved_events(trace,xml)
    source=next(s['input'] for s in samples() if s['id']==stem)
    options=source_duration_options(rd,Image.open(os.path.join(ROOT,source)),events)
    return rd,events,options


def _option_types(options, sid):
    return {o['typ'] for o in options[sid]['options']}


def test_golden_harp_source_filled_half_symbols_in_rest_and_note_classes_offer_quarter():
    _,_,options=_load('1911-s0288-the-golden-harp','1911-Origin-JPK-0288.jpg')
    for sid in (276,294):
        evidence=options[sid]['evidence']
        assert evidence['strict_source_filled_head']
        assert 'quarter' in _option_types(options,sid)
        baseline=next(o for o in options[sid]['options'] if o['reason'].startswith('baseline'))
        assert baseline['typ']=='half' and baseline['weight']==0
    assert options[276]['evidence']['baseline']['kind']=='rest'
    assert options[294]['evidence']['baseline']['kind']=='note'


def test_shallow_half_rest_and_hollow_whole_controls_keep_baseline_duration():
    _,_,clamanda=_load('1911-Origin-JPK-0052','1911-Origin-JPK-0052.jpg')
    assert 'quarter' not in _option_types(clamanda,70)
    assert not clamanda[70]['evidence']['strict_source_filled_head']
    _,_,newburgh=_load('1911-s0192-newburgh','1911-Origin-JPK-0192.jpg')
    _,_,chambers=_load('1911-holdout-s0130-chambers','1911-Origin-JPK-0130.jpg')
    for opts,sid in ((newburgh,727),(chambers,568)):
        assert opts[sid]['evidence']['morphology']['hollow_head']
        assert not opts[sid]['evidence']['strict_source_filled_head']
        assert 'quarter' not in _option_types(opts,sid)
        assert 'whole' in _option_types(opts,sid)


def test_m095_shallow_hollow_half_with_stem_stub_does_not_become_quarter():
    rd,events,options=_load('1911-s0308-never-part','1911-Origin-JPK-0308.jpg')
    # The recovered physical M095 note is proposal 522; anchor 449 remains an
    # unselected rest interpretation of the same location.
    assert options[522]['evidence']['baseline']['kind']=='note'
    assert not options[522]['evidence']['strict_source_filled_head']
    assert 'quarter' not in _option_types(options,522)
    assert 'half' in _option_types(options,522)
    sid=449
    # Its shallow anchor box must not create a filled-square duration either.
    sym=rd.layout.syms[sid]
    ev=Event(x=sym.cx,kind='rest',typ='half',si=sid)
    options=source_duration_options(rd,Image.open(os.path.join(SOURCES,'1911-Origin-JPK-0308.jpg')),
                                    {sym.staff:[ev]})
    assert not options[sid]['evidence']['strict_source_filled_head']
    assert 'quarter' not in _option_types(options,sid)
    assert 'half' in _option_types(options,sid)


def test_quarter_to_eighth_requires_independent_beam_and_posterior_support():
    # Minimal source geometry: a beam outside two filled heads at their stem tips.
    box=(20,20,30,30)
    sym=SimpleNamespace(i=0,cls='note_quarter',p=.9,box=box,staff=0,bar=0,cx=25,
        attrs={'stem_dir':'up'},attr_dist={},post={})
    peer=SimpleNamespace(i=1,cls='note_quarter',p=.9,box=(50,20,60,30),staff=0,bar=0,cx=55,
        attrs={'stem_dir':'up'},attr_dist={},post={})
    beam=SimpleNamespace(i=2,cls='beam',p=.6,box=(28,10,61,12),staff=0,bar=0,cx=44.5,
        attrs={},attr_dist={},post={})
    rd=SimpleNamespace(layout=SimpleNamespace(syms=[sym,peer,beam],staves=[SimpleNamespace(sp=10,bars=[0])],
        bar_box=lambda *_:box),tok={0:{'cls':{'v':'note_quarter','p':.8},'dots':{'v':0,'p':1}},
                                     1:{'cls':{'v':'note_quarter','p':.8}}})
    # Use a filled synthetic square image and retain the baseline options.
    from copisteria.vocab import CLASSES
    sym.post={CLASSES.index('note_eighth'):.4}
    from PIL import ImageDraw
    image=Image.new('L',(90,45),255); d=ImageDraw.Draw(image)
    d.rectangle(box,fill=0);d.rectangle((50,20,60,30),fill=0);d.rectangle((28,10,61,12),fill=0)
    first=Event(x=25,kind='note',typ='quarter',si=0)
    second=Event(x=55,kind='note',typ='quarter',si=1)
    opts=source_duration_options(rd,image,{0:[first,second]})
    assert 'eighth' in _option_types(opts,0)
    beam.p=.49
    opts=source_duration_options(rd,image,{0:[first,second]})
    assert 'eighth' not in _option_types(opts,0)
    beam.p=.6;sym.post={'quarter':1.0};rd.tok[0]['cls']={'v':'note_quarter','p':.8}
    opts=source_duration_options(rd,image,{0:[first,second]})
    assert 'eighth' not in _option_types(opts,0)
