import copy
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from proposal_rhythm_policy import constrain_proposal_rhythms

ROOT = Path(__file__).parent
SAVED = ROOT/'experiments/missing-proposals/final-d190393b6a83/predictions'


def test_reviewed_quarter_and_undotted_quarter_preserve_true_dot_and_eighth():
    controls = [('1911-s0416-protection', 593, 'note_quarter', 0),
                ('1911-s0316-greenland', 855, 'note_quarter', 0),
                ('1911-s0316-greenland', 829, 'note_quarter', 1),
                ('1911-s0316-greenland', 844, 'note_eighth', 0)]
    for sid, i, typ, dots in controls:
        source = ROOT/('sources/1911-Origin-JPK-0416.jpg' if 'protection' in sid
                       else 'sources/1911-Origin-JPK-0316.jpg')
        t = json.loads((SAVED/f'{sid}.trace.json').read_text())
        a = next(a for a in t['new_note_proposals'] if a['proposal_id'] == i)
        rd = SimpleNamespace(tok={i: copy.deepcopy(t['tokens'][str(i)])})
        constraints = {i: set(t['proposal_duration_constraints'][str(i)])}
        constrain_proposal_rhythms(rd, [a], Image.open(source), constraints)
        assert rd.tok[i]['cls']['v'] == typ
        assert rd.tok[i]['dots']['v'] == dots
        if i == 593:
            assert constraints[i] == {'quarter'}


def test_loss_guard_restores_only_affected_source_bar():
    from proposal_rhythm_policy import restore_lossy_rhythm_bars
    syms = [SimpleNamespace(staff=0, bar=0),SimpleNamespace(staff=0,bar=0),SimpleNamespace(staff=0,bar=1)]
    tok = {i:{'cls':{'v':'note_eighth'},'dots':{'v':0}} for i in range(3)}
    before=SimpleNamespace(tok=copy.deepcopy(tok));rd=SimpleNamespace(tok=tok,layout=SimpleNamespace(syms=syms))
    rd.tok[0]['cls']['v']='note_quarter';rd.tok[2]['cls']['v']='note_quarter'
    constraints={0:{'quarter'},2:{'quarter'}};prior={0:{'eighth','quarter'},2:{'eighth','quarter'}}
    decisions=[{'sym_id':i,'action':'direct_visual_duration'} for i in (0,2)]
    assert restore_lossy_rhythm_bars(rd,before,constraints,prior,decisions,[1])==1
    assert rd.tok[0]['cls']['v']=='note_eighth' and rd.tok[2]['cls']['v']=='note_quarter'
    assert decisions[0]['rejected'] and not decisions[1].get('rejected')
    assert constraints[0]==prior[0]


def test_direct_head_posterior_cannot_change_open_duration_or_introduce_flag():
    controls=[('1911-s0192-newburgh',727,'note_whole'),
              ('1911-holdout-s0130-chambers',568,'note_whole'),
              ('1911-holdout-s0182-harmony',767,'note_quarter')]
    for sid,i,expected in controls:
        t=json.loads((SAVED/f'{sid}.trace.json').read_text())
        a=next(a for a in t['new_note_proposals'] if a['proposal_id']==i)
        rd=SimpleNamespace(tok={i:copy.deepcopy(t['tokens'][str(i)])})
        constraints={i:set(t['proposal_duration_constraints'][str(i)])}
        constrain_proposal_rhythms(rd,[a],Image.new('L',(10,10),255),constraints)
        assert rd.tok[i]['cls']['v']==expected
