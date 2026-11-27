"""Structural ink rejection must preserve actual physical source heads."""
import json
from types import SimpleNamespace as NS
import numpy as np
from PIL import Image,ImageDraw
from run_local_recovery import ROOT,samples
from replay_writer_trace import _reading
from source_saved_events import source_saved_events
from source_rhythm_resolution import unique_physical_events
from false_head_evidence import line_or_blemish_evidence,repeat_dot_head_evidence,proven_non_head
from run_proposal_rhythm_recovery import PROPOSALS


def _clean(sample):
    parent=ROOT/'experiments/proposal-rhythm/final-0318d4f06bb9/predictions'
    trace=json.loads((parent/f"{sample['id']}.trace.json").read_text())
    image=Image.open(ROOT/sample['input']).convert('L');rd=_reading(trace,image)
    events,_=source_saved_events(trace,(parent/f"{sample['id']}.musicxml").read_text())
    return unique_physical_events(events,rd,np.asarray(image))


def test_cached_false_heads_removed_without_removing_their_real_neighbors():
    targets={'Done With The World':(394,{397}), 'Jackson':(256,{202,248,233}),
             'Primrose':(243,{229,228,5})}
    for sample in samples():
        if sample['title'] not in targets:continue
        rejected,kept=targets[sample['title']];clean,removed=_clean(sample)
        ids={e.si for rows in clean.values() for e in rows if e.kind=='note'}
        assert rejected not in ids and kept<=ids
        assert any(r['sym_id']==rejected and proven_non_head(r) for r in removed)


def test_all_protected_physical_heads_and_ambiguous_stemless_head_survive():
    cases=json.loads((PROPOSALS/'source-review.json').read_text())['cases']
    protected={}
    for case in cases:protected.setdefault(case['song_id'],set()).add(case['proposal_id'])
    for sample in samples():
        if sample['id'] not in protected and sample['title']!='Elder':continue
        clean,_=_clean(sample);ids={e.si for rows in clean.values() for e in rows if e.kind=='note'}
        assert protected.get(sample['id'],set())<=ids
        if sample['title']=='Elder':assert {111,365,83,361}<=ids


def test_two_small_aligned_heads_without_repeat_boundary_are_not_rejected():
    image=Image.new('L',(150,160),255);d=ImageDraw.Draw(image)
    for y in (50,70):d.ellipse((40,y,48,y+8),fill=0)
    d.rectangle((65,50,85,70),fill=0)
    sym=NS(box=(40,50,48,58));staff=NS(sp=20,y0=20,y1=100)
    assert not repeat_dot_head_evidence(np.asarray(image),sym,staff,[{'box':(65,50,85,70)}],[])['repeat_dot_head']


def test_enclosed_counter_vetoes_line_rejection_even_with_weak_verification():
    image=np.full((120,120),255,dtype=np.uint8)
    sym=NS(box=(40,40,60,60));staff=NS(sp=20,y0=20,y1=100)
    ver={'reason':'no_head_ink','head_ink_fraction':.1}
    morph={'enclosed_white_area_fraction':.12,'central_ink_fraction':.1}
    assert not line_or_blemish_evidence(image,sym,staff,ver,morph)['line_or_blemish']


def test_unproven_removal_is_not_exempted_from_physical_head_guard():
    for reason in ('repeat_dot_misread_as_notehead','line_or_blemish_misread_as_notehead',
                   'beam_stroke_misread_as_notehead'):
        assert not proven_non_head({'reason':reason,'source_geometry_evidence':{}})
