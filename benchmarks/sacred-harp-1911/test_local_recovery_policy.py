from types import SimpleNamespace as NS

import run_local_recovery as runner


def reading(note=True, pos=0):
    rest = NS(i=0, fam='rest', staff=0, bar=0, box=(40,45,50,55))
    st = NS(sp=10., mid=50.)
    syms = [rest]
    tok = {0: {'cls': {'v': 'rest_half'}, 'real': {'p': .99, 'det': .9}}}
    if note:
        syms.append(NS(i=1, fam='note', staff=0, bar=0, box=(40,45,50,55)))
        tok[1] = {'cls': {'v': 'note_quarter'}, 'real': {'p': .4, 'det': .7},
                  'pos': {'v': pos, 'p': .99}}
    return NS(layout=NS(syms=syms, staves=[st], bar_box=lambda staff,bar: (0,30,100,70)), tok=tok)


def evidence(monkeypatch):
    import note_rest_evidence
    monkeypatch.setattr(runner, 'verify_reading', lambda rd,image: {})
    monkeypatch.setattr(note_rest_evidence, 'short_stem_evidence', lambda *a,**kw: {
        'found': True, 'score': .9, 'direction': 'up', 'stem_x': 49, 'reason': 'edge_anchored_short_stem'})


def test_rest_replacement_requires_existing_position_supported_neural_note(monkeypatch):
    evidence(monkeypatch)
    rd = reading()
    _, actions, extra = runner.evidence_reading(rd, None, True)
    assert rd.tok[0]['real']['p'] == 0
    assert rd.tok[1]['real']['p'] == .51
    assert rd.tok[1]['real']['verified_original_p'] == .4
    assert rd.tok[1]['cls']['v'] == 'note_quarter'
    assert rd.tok[1]['pos']['v'] == 0
    assert len(extra) == 1
    assert any(a['action'] == 'admit_existing_note' for a in actions)


def test_rest_only_detection_never_acquires_a_fabricated_pitch(monkeypatch):
    evidence(monkeypatch)
    rd = reading(note=False)
    _, actions, extra = runner.evidence_reading(rd, None, True)
    assert len(rd.tok) == 1
    assert rd.tok[0]['real']['p'] == .99
    assert actions == extra == []


def test_inconsistent_note_position_does_not_suppress_rest(monkeypatch):
    evidence(monkeypatch)
    rd = reading(pos=5)
    _, actions, extra = runner.evidence_reading(rd, None, True)
    assert rd.tok[0]['real']['p'] == .99
    assert rd.tok[1]['real']['p'] == .4
    assert actions == extra == []
