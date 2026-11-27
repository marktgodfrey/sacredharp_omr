from fractions import Fraction
from types import SimpleNamespace as NS

import pytest

from bar_fitting import fit_bar_choices, glyph_groups, shared_stem_chords, printed_meter_consensus


def make_case(items):
    """Build (x, kind, type, box, p, det, pitch, onset) event specs."""
    from copisteria.write import Event

    st = NS(sp=10.0)
    syms, tok, events = [], {}, []
    for i, (x, kind, typ, box, p, det, pitch, onset) in enumerate(items):
        fam = kind
        syms.append(NS(i=i, fam=fam, staff=0, bar=0, box=box))
        tok[i] = {"real": {"p": p, "det": det}}
        beat = [1e-5] * 16
        beat[max(0, min(15, int(onset)))] = .999
        frac = [1e-5] * 48
        frac[0] = .999
        events.append(Event(x=x, kind=kind, typ=typ, si=i, step=pitch,
                            onset=float(onset), onset_p=.999,
                            dist={"beat": beat, "frac": frac, "tup": None}))
    rd = NS(layout=NS(syms=syms, staves=[st], systems=[]), tok=tok)
    return rd, events


def run_fit(rd, events, bar_len, verified=None):
    from copisteria import write
    with fit_bar_choices(rd, verified or {}, {}) as decisions:
        voices = write._voices(events, 10.0, bar_len=Fraction(bar_len))
        chopped = [e for voice in voices.values() for e in write._chop(voice, Fraction(bar_len))]
    return chopped, decisions


def test_same_glyph_note_rest_readings_are_exclusive_and_fit_six_quarters():
    # The first glyph has competing high-confidence note/rest readings. The
    # lower-confidence note is needed for the three notes to fit six quarters.
    box = (6, 20, 14, 28)
    items = [(10, "rest", "half", box, .995, .9, "C", 0),
             (10.5, "note", "quarter", box, .989, .8, "C", 0),
             (30, "note", "half", (26, 20, 34, 28), .99, .9, "D", 1),
             (50, "note", "half", (46, 20, 54, 28), .99, .9, "E", 3)]
    rd, events = make_case(items)
    events[3].dots = 1
    assert len(glyph_groups(rd, events)) == 1
    kept, _ = run_fit(rd, events, 6)
    notes = [e for e in kept if e.kind == "note"]
    assert len(notes) == 3
    assert sum((Fraction(3 if e.dots == 1 else 2 if e.typ == "half" else 1)
                for e in notes), Fraction()) == 6


def test_partial_duplicate_cannot_displace_certain_final_note():
    rd, events = make_case([
        (10, "note", "quarter", (6, 20, 15, 28), .2, .1, "C", 0),
        (12, "note", "quarter", (11, 20, 14, 28), .999, .9, "C", 0),
        (42, "note", "quarter", (38, 20, 47, 28), .999, .9, "D", 1),
    ])
    assert glyph_groups(rd, events)
    kept, _ = run_fit(rd, events, 2)
    assert not any(e.si == 0 for e in kept)
    assert any(e.si == 1 for e in kept)
    assert any(e.si == 2 for e in kept)


def test_weak_unverified_ghost_is_omitted_to_keep_last_true_quarter():
    rd, events = make_case([
        (10, "note", "quarter", (6, 20, 14, 28), .99, .9, "C", 0),
        (20, "note", "quarter", (16, 20, 24, 28), .66, .139, "D", 1),
        (30, "note", "quarter", (26, 20, 34, 28), .99, .9, "E", 1),
        (40, "note", "quarter", (36, 20, 44, 28), .99, .9, "F", 2),
    ])
    kept, decisions = run_fit(rd, events, 3)
    assert {e.si for e in kept if e.kind == "note"} == {0, 2, 3}
    assert any(a.get("action") == "omit_weak_unverified"
               for d in decisions for a in d.get("actions", []))


def test_nonoverflowing_weak_candidate_is_not_removed():
    rd, events = make_case([
        (10, "note", "quarter", (6, 20, 14, 28), .99, .9, "C", 0),
        (20, "note", "quarter", (16, 20, 24, 28), .66, .139, "D", 1),
        (30, "note", "quarter", (26, 20, 34, 28), .99, .9, "E", 2),
    ])
    kept, _ = run_fit(rd, events, 4)
    assert {e.si for e in kept if e.kind == "note"} == {0, 1, 2}


def test_verified_shared_stem_dotted_half_chord_keeps_both_pitches():
    rd, events = make_case([
        (20, "note", "half", (12, 18, 19, 28), .95, .9, "C", 0),
        (20.5, "note", "half", (21, 12, 28, 22), .95, .9, "E", 0),
    ])
    for event in events:
        event.dots = 1
    verified = {0: {"stem_found": True, "stem_x": 18},
                1: {"stem_found": True, "stem_x": 18}}
    assert shared_stem_chords(rd, events, verified)
    kept, _ = run_fit(rd, events, 3, verified)
    assert {e.si for e in kept if e.kind == "note"} == {0, 1}


def test_nonoverlapping_genuine_rest_is_retained():
    rd, events = make_case([
        (10, "note", "quarter", (6, 20, 14, 28), .99, .9, "C", 0),
        (30, "rest", "quarter", (26, 20, 34, 28), .99, .9, "C", 1),
        (50, "note", "quarter", (46, 20, 54, 28), .99, .9, "D", 2),
    ])
    kept, _ = run_fit(rd, events, 3)
    assert any(e.si == 1 and e.kind == "rest" for e in kept)


def test_writer_hook_is_restored_after_exception():
    from copisteria import write
    original = write._voices
    original_meter = write._page_meter
    with pytest.raises(RuntimeError):
        with fit_bar_choices(NS(layout=NS(syms=[], staves=[], systems=[]), tok={}), {}, {}):
            assert write._voices is not original
            raise RuntimeError("test exception")
    assert write._voices is original
    assert write._page_meter is original_meter


def test_duration_repair_requires_an_observed_class_alternative():
    from copisteria import write
    items=[
        (10, 'note', 'half', (6,20,14,28), .99, .9, 'C', 0),
        (30, 'note', 'half', (26,20,34,28), .99, .9, 'D', 1),
        (50, 'note', 'quarter', (46,20,54,28), .99, .9, 'E', 2),
    ]
    rd,events=make_case(items)
    with fit_bar_choices(rd, {}, {i:{'half':.9,'quarter':.8} for i in (0,1)}):
        voices=write._voices(events,10.,bar_len=Fraction(3))
    kept=[e for vs in voices.values() for e in write._chop(vs,Fraction(3)) if e.kind=='note']
    assert len(kept)==3 and all(e.typ=='quarter' for e in kept)
    rd,events=make_case(items)
    with fit_bar_choices(rd, {}, {}):
        voices=write._voices(events,10.,bar_len=Fraction(3))
    assert next(e for vs in voices.values() for e in vs if e.si==0).typ=='half'


def test_shared_stem_chord_uses_onset_evidence_from_both_heads():
    from copisteria import write
    rd,events=make_case([
        (20,'note','half',(12,18,19,28),.95,.9,'C',1),
        (20.5,'note','half',(21,12,28,22),.99,.9,'E',0),
    ])
    for e in events:e.dots=1
    events[0].dist['beat'][0]=.4
    events[0].dist['beat'][1]=.6
    events[0].onset_p=.6
    events[1].dist['beat'][0]=.98
    events[1].dist['beat'][1]=.02
    verified={i:{'stem_found':True,'stem_x':18} for i in (0,1)}
    with fit_bar_choices(rd,verified,{}):
        voices=write._voices(events,10.,bar_len=Fraction(3))
    starts,end=write._voice_starts(voices[1],Fraction(3))
    heads=[(e,s) for e,s in zip(voices[1],starts) if e.kind=='note']
    assert len(heads)==2 and heads[0][1]==heads[1][1]==0
    assert end==3


def meter_reading():
    syms=[NS(i=i,staff=i,bar=0) for i in (0,1)]
    tok={i:{'real':{'p':.999},'cls':{'v':'meterSig_2_4','p':.99}} for i in (0,1)}
    tok.update({i+2:{'time':{'v':'2/4','p':.999}} for i in (0,1)})
    return NS(layout=NS(syms=syms,staves=[NS(bars=[2]),NS(bars=[3])],
                        systems=[NS(staves=[0,1])]),tok=tok)


def test_visible_agreeing_printed_meter_is_not_stretched_to_fit_bad_readings():
    from copisteria import write
    rd=meter_reading()
    original=write._page_meter
    with fit_bar_choices(rd,{},{}):
        assert write._page_meter(rd,lambda _: (_ for _ in ()).throw(AssertionError('should not search')))== '2/4'
    assert write._page_meter is original


def test_meter_anchor_abstains_for_missing_uncertain_or_conflicting_glyphs():
    rd=meter_reading();rd.layout.syms=[]
    assert printed_meter_consensus(rd) is None
    rd=meter_reading();rd.tok[1]['cls']['p']=.5
    assert printed_meter_consensus(rd) is None
    rd=meter_reading();rd.tok[1]['cls']['v']='meterSig_3_4'
    assert printed_meter_consensus(rd) is None


def test_meter_votes_keep_the_same_bar_slots_when_a_whole_voice_is_omitted():
    from copisteria import write
    votes=[]
    for bar_len in (1,2):
        rd,events=make_case([(10,'note','half',(6,20,14,28),.1,.1,'C',0)])
        scores=[]
        with fit_bar_choices(rd,{},{}):
            write._voices(events,10.,bar_len=Fraction(bar_len),score=scores)
            write._voices([],10.,bar_len=Fraction(bar_len),score=scores)
        # Each staff/bar contributes one joint likelihood, including empty bars;
        # a deleted voice must not shift all later bars in the meter comparison.
        assert len(scores)==2 and scores[1]==0
        votes.append(scores)
    assert votes[0][0]!=votes[1][0]
