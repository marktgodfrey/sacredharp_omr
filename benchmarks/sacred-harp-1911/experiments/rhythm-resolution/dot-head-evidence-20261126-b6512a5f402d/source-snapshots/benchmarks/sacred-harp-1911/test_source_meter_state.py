from types import SimpleNamespace

from source_meter_state import apply_source_meter_state, source_meter_state


class Sym:
    def __init__(self, i, cls, staff, bar, x, p=.99):
        self.i, self.cls, self.staff, self.bar, self.p = i, cls, staff, bar, p
        self.box = (x - 2, 0, x + 2, 5)
        self.fam = 'measure' if cls == 'measure' else cls.split('_')[0]
        self.cx = x


def reading(n_systems=1, bars_per_staff=4):
    syms, staves, systems, tok = [], [], [], {}
    for staff in range(2):
        bars=[]
        for bar in range(bars_per_staff):
            i=len(syms); x=bar*100+20
            syms.append(Sym(i,'measure',staff,bar,x))
            bars.append(i)
            tok[i]={'time': {'v': None, 'p': .99}}
        staves.append(SimpleNamespace(bars=bars, system=0, sp=10))
    systems.append(SimpleNamespace(staves=[0,1], columns=[list(range(bars_per_staff)),list(range(bars_per_staff))]))
    return SimpleNamespace(layout=SimpleNamespace(syms=syms,staves=staves,systems=systems,
        column=lambda staff,bar: bar),tok=tok)


def add_glyph(rd, staff, bar, meter, confidence=.9):
    i=len(rd.layout.syms); x=bar*100+30
    rd.layout.syms.append(Sym(i,'meterSig_'+meter.replace('/','_'),staff,bar,x,confidence))
    rd.tok[i]={'real':{'p':confidence},'cls':{'v':'meterSig_'+meter.replace('/','_'),'p':.99}}


def test_parallel_glyph_consensus_changes_meter_and_keeps_equal_capacity_signatures():
    rd=reading(bars_per_staff=5)
    for bar,meter in ((0,'6/8'),(2,'3/4'),(4,'6/8')):
        for staff in range(2): add_glyph(rd,staff,bar,meter)
    state=source_meter_state(rd)
    assert [(e['column'],e['meter']) for e in state['transitions']]==[(0,'6/8'),(2,'3/4'),(4,'6/8')]
    assert [state['meter_by_staff_bar'][0,b] for b in range(5)]==['6/8','6/8','3/4','3/4','6/8']


def test_low_confidence_repeat_dot_and_false_signature_are_rejected():
    rd=reading(bars_per_staff=1)
    add_glyph(rd,0,0,'4/4',.142);add_glyph(rd,1,0,'4/4',.081)
    state=source_meter_state(rd)
    assert state['transitions']==[]
    assert all(not e['accepted_candidate'] for e in state['evidence'])


def test_greenland_real_2_4_confidences_are_admitted_by_parallel_consensus():
    rd=reading(bars_per_staff=1)
    add_glyph(rd,0,0,'2/4',.682);add_glyph(rd,1,0,'2/4',.497)
    assert source_meter_state(rd)['transitions'][0]['meter']=='2/4'


def test_decoded_measure_heads_recover_opening_when_glyph_is_missing():
    rd=reading(bars_per_staff=1)
    for staff in range(2):
        rd.tok[rd.layout.staves[staff].bars[0]]['time']={'v':'4/4','p':.99}
    state=source_meter_state(rd)
    assert state['transitions'][0]['meter']=='4/4'
    apply_source_meter_state(rd,state)
    assert all(rd.tok[s.bars[0]]['time']['source_meter_state'] for s in rd.layout.staves)


def test_meter_change_applies_at_first_following_physical_bar_after_resegmentation():
    rd=reading(bars_per_staff=4)
    # The accepted change belongs to physical bar 2, even if a resegmentation
    # has shifted its old decoded head value or the previous bar index.
    for staff in range(2):
        rd.layout.syms[rd.layout.staves[staff].bars[0]].bar=0
        add_glyph(rd,staff,2,'3/4')
    state=apply_source_meter_state(rd)
    assert state['meter_by_staff_bar'][0,2] == '3/4'
    assert state['meter_by_staff_bar'][1,3] == '3/4'
    assert rd.tok[rd.layout.staves[0].bars[2]]['time']['v']=='3/4'


def test_five_confirmed_opening_meter_cases_are_recoverable_from_source_evidence():
    # Three cases have eligible source glyphs; the last two rely on the
    # already-decoded parallel measure-head time attributes.
    for meter, via_glyph in [('3/4', True), ('4/4', True), ('6/8', True),
                             ('4/4', False), ('4/4', False)]:
        rd=reading(bars_per_staff=1)
        if via_glyph:
            for staff in range(2): add_glyph(rd,staff,0,meter,.85)
        else:
            for staff in range(2):
                rd.tok[rd.layout.staves[staff].bars[0]]['time']={'v':meter,'p':.99}
        state=source_meter_state(rd)
        assert state['transitions'][0]['meter']==meter
        assert state['meter_by_staff_bar'][0,0]==meter


def test_primrose_hill_confirmed_sequence_uses_raw_glyphs_and_survives_equal_capacity():
    rd=reading(bars_per_staff=3)
    for bar,meter in enumerate(('6/8','3/4','6/8')):
        for staff in range(2): add_glyph(rd,staff,bar,meter,.995)
    assert [e['meter'] for e in source_meter_state(rd)['transitions']]==['6/8','3/4','6/8']


def test_real_cached_meter_changes_override_stale_or_copied_measure_heads():
    from pathlib import Path
    import json
    from PIL import Image
    from replay_writer_trace import _reading
    from run_local_recovery import samples
    root=Path(__file__).parent
    wanted={'Primrose Hill':['6/8','3/4','6/8'], 'Greenland':['2/4','6/8','3/4'],
            'Ninety-Third Psalm':['3/4'],'Fillmore':['4/4'],'Alabama':['6/8'], 'Saint’s Delight':['4/4']}
    for s in samples():
        if s['title'] not in wanted:continue
        t=json.loads((root/'experiments/proposal-rhythm/final-0318d4f06bb9/predictions'/f'{s["id"]}.trace.json').read_text())
        rd=_reading(t,Image.open(root/s['input']))
        assert [e['meter'] for e in source_meter_state(rd)['transitions']]==wanted[s['title']],s['title']


def test_inactive_old_measure_and_unsupported_later_head_cannot_create_change():
    rd=reading(bars_per_staff=2)
    for staff in range(2):
        add_glyph(rd,staff,0,'4/4')
        rd.tok[rd.layout.staves[staff].bars[1]]['time']={'v':'3/2','p':.999}
        i=len(rd.layout.syms);rd.layout.syms.append(Sym(i,'measure',staff,0,0))
        rd.tok[i]={'time':{'v':'6/8','p':.999}}
    assert [e['meter'] for e in source_meter_state(rd)['transitions']]==['4/4']
