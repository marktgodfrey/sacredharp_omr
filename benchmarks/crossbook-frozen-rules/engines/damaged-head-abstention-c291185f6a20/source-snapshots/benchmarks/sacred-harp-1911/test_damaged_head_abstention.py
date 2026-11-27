"""Development controls only; no held-out 1860 image is opened here."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
from PIL import Image,ImageDraw
from run_local_recovery import ROOT
from replay_writer_trace import _reading
from source_saved_events import source_saved_events
from source_rhythm_resolution import unique_physical_events
from false_head_evidence import line_or_blemish_evidence


def test_only_independently_supported_staff_ink_can_be_rejected():
    for sp in (12,20,32):
        image=Image.new('L',(8*sp,8*sp),255);d=ImageDraw.Draw(image)
        for j in range(5):d.line((0,(j+1)*sp,8*sp,(j+1)*sp),fill=0,width=2)
        staff=NS(sp=sp,y0=sp,y1=5*sp);box=(3*sp,1.5*sp,4*sp,2.5*sp);sym=NS(box=box)
        ver={'reason':'no_head_ink','head_ink_fraction':.1,'ink_threshold':175}
        morph={'enclosed_white_area_fraction':0,'central_ink_fraction':.1}
        proof=line_or_blemish_evidence(np.asarray(image),sym,staff,ver,morph)
        assert proof['line_or_blemish'] and proof['unexplained_ink_pixels']==0
        # Even a single off-line remnant is uncertain; no minimum fragment
        # size fitted to a particular damaged source head is imposed.
        d.point((int(3.5*sp),int(1.65*sp)),fill=0)
        proof=line_or_blemish_evidence(np.asarray(image),sym,staff,ver,morph)
        assert not proof['line_or_blemish'] and proof['abstained']


def test_open_rims_and_partial_shapes_abstain_at_multiple_scales():
    for sp in (12,20,32):
        for shape in ('arc','corner','stem'):
            image=Image.new('L',(8*sp,8*sp),255);d=ImageDraw.Draw(image)
            for j in range(5):d.line((0,(j+1)*sp,8*sp,(j+1)*sp),fill=0,width=2)
            staff=NS(sp=sp,y0=sp,y1=5*sp);box=(3*sp,1.5*sp,4*sp,2.5*sp);sym=NS(box=box)
            if shape=='arc':d.arc(box,start=10,end=170,fill=0,width=2)
            elif shape=='corner':d.line((3.1*sp,2.4*sp,3.7*sp,2.25*sp),fill=0,width=2)
            else:d.line((3.2*sp,1.6*sp,3.2*sp,2.4*sp),fill=0,width=2)
            proof=line_or_blemish_evidence(np.asarray(image),sym,staff,
                {'reason':'no_head_ink','head_ink_fraction':.1,'ink_threshold':175},
                {'enclosed_white_area_fraction':0,'central_ink_fraction':.1})
            assert not proof['line_or_blemish'] and proof['abstained'],(sp,shape,proof)


def test_external_support_is_required_even_if_a_box_contains_horizontal_ink():
    image=Image.new('L',(160,160),255);d=ImageDraw.Draw(image)
    d.line((60,40,80,40),fill=0,width=2)
    proof=line_or_blemish_evidence(np.asarray(image),NS(box=(60,30,80,50)),NS(sp=20,y0=20,y1=100),
        {'reason':'no_head_ink','head_ink_fraction':.1,'ink_threshold':175},
        {'enclosed_white_area_fraction':0,'central_ink_fraction':.1})
    assert not proof['line_or_blemish'] and proof['abstained']


def test_development_damaged_and_mislocalized_objects_survive_in_both_layouts():
    cross=ROOT.parent/'crossbook-frozen-rules/runs/expanded52-frozen-dot-head-20261126'
    historical=ROOT.parent/'historical-sacred-harp'
    samples={s['id']:s for s in json.loads((cross/'manifest.json').read_text())['samples']}
    for variant in ('default','clean_layout'):
        for sid,si in [('1911-Sacred-EMU-28t-aylesbury',186),('1870-Sacred-MTS-48b-kedron',219)]:
            path=cross/'seeds'/variant/'predictions'/f'{sid}.trace.json'
            trace=json.loads(path.read_text());image=Image.open(historical/samples[sid]['input']).convert('L')
            rd=_reading(trace,image);events,_=source_saved_events(trace,path.with_suffix('').with_suffix('.musicxml').read_text())
            abstentions=[];clean,removed=unique_physical_events(events,rd,np.asarray(image),abstentions=abstentions)
            ids={e.si for rows in clean.values() for e in rows if e.kind=='note'}
            # Some configurations were already retained by the earlier filter;
            # they need not log abstention if they are not rejection candidates.
            selected=any(e.si==si for rows in events.values() for e in rows if e.kind=='note')
            if selected:assert si in ids
            previous=json.loads((cross/'current'/variant/f'{sid}.trace.json').read_text())
            formerly_removed=any(r['sym_id']==si for r in previous['rhythm_resolution_details']['duplicate_serialized_events_removed'])
            if formerly_removed:assert any(a['sym_id']==si for a in abstentions)
            assert not any(r['sym_id']==si for r in removed)
