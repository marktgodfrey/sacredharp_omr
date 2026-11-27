import copy
import json

from PIL import Image

from run_local_recovery import ROOT, samples
from replay_writer_trace import _reading
from source_bar_grid import rebuild_source_bars
from source_saved_events import source_saved_events


def test_confirmed_fragment_and_collapsed_bar_cases_share_source_cuts_without_losing_heads():
    parent=ROOT/'experiments/proposal-rhythm/final-0318d4f06bb9/predictions'
    for sample in samples():
        if sample['title'] not in ('Fillmore','Salem','Farewell To All'):
            continue
        stem=parent/sample['id']
        trace=json.loads(stem.with_suffix('.trace.json').read_text())
        xml=stem.with_suffix('.musicxml').read_text()
        image=Image.open(ROOT/sample['input']).convert('L')
        rd=_reading(copy.deepcopy(trace),image)
        events,_=source_saved_events(trace,xml)
        before=[(s.i,s.box,s.staff) for s in rd.layout.syms if s.fam!='measure']
        decisions=rebuild_source_bars(rd,image,events,xml)
        assert before==[(s.i,s.box,s.staff) for s in rd.layout.syms if s.fam!='measure']
        for system in rd.layout.systems:
            grids=[[rd.layout.syms[i].box[0::2] for i in rd.layout.staves[k].bars]
                   for k in system.staves]
            assert all(g==grids[0] for g in grids)
            assert all(b-a>=rd.layout.staves[system.staves[0]].sp for a,b in grids[0])
            for k in system.staves:
                staff=rd.layout.staves[k]
                assert all(0<=rd.layout.syms[e.si].bar<len(staff.bars) for e in events[k])
        if sample['title']=='Fillmore':
            assert all(d['new_bar_count']>max(d['old_bar_counts']) for d in decisions)
