import json
from PIL import Image,ImageDraw
import numpy as np
from beam_region_evidence import beam_region_evidence
from run_local_recovery import ROOT,samples


def test_thin_staff_line_does_not_look_like_a_beam_body():
    im=Image.new('L',(180,160),255);d=ImageDraw.Draw(im)
    d.line((0,50,180,50),fill=0,width=1);d.rectangle((70,45,90,65),fill=0)
    peers=[{'si':1,'x':45,'box':(35,100,55,120)},{'si':2,'x':115,'box':(105,100,125,120)}]
    assert not beam_region_evidence(np.asarray(im),(70,45,90,65),20,peers)['beam_region']


def test_source_beam_fragment_is_distinct_from_its_two_actual_heads():
    sample=next(s for s in samples() if s['title']=='Ocean')
    path=ROOT/'experiments/proposal-rhythm/final-0318d4f06bb9/predictions'/f"{sample['id']}.trace.json"
    trace=json.loads(path.read_text());pixels=np.asarray(Image.open(ROOT/sample['input']).convert('L'))
    syms=trace['syms'];sp=trace['staves'][syms[555]['staff']]['sp']
    peers=[{'si':i,'x':sum(syms[i]['box'][0::2])/2,'box':syms[i]['box']} for i in (575,652)]
    result=beam_region_evidence(pixels,syms[555]['box'],sp,peers)
    assert result['beam_region'] and set(result['other_head_ids'])=={575,652}
    assert not beam_region_evidence(pixels,syms[575]['box'],sp,peers[1:])['beam_region']


def test_short_connector_requires_ink_joining_both_endpoint_heads():
    im=Image.new('L',(180,180),255);d=ImageDraw.Draw(im)
    d.polygon([(70,45),(100,39),(100,47),(70,53)],fill=0)
    d.rectangle((52,100,70,118),fill=0);d.rectangle((82,94,100,112),fill=0)
    peers=[{'si':1,'x':61,'box':(52,100,70,118)}, {'si':2,'x':91,'box':(82,94,100,112)}]
    box=(69,39,101,54)
    # A slanted stroke and unrelated heads are not enough.
    assert not beam_region_evidence(np.asarray(im),box,20,peers)['beam_region']
    d.line((70,48,70,107),fill=0,width=2);d.line((100,43,100,101),fill=0,width=2)
    result=beam_region_evidence(np.asarray(im),box,20,peers)
    assert result['beam_region'] and len(result['endpoint_stems'])==2
