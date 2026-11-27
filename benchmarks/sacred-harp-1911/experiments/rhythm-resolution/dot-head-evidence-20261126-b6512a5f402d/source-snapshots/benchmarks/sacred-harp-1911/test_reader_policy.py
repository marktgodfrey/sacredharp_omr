from fractions import Fraction
from types import SimpleNamespace as NS

from reader_policy import apply_stem_verification, supported_rhythm_choices


def reading(note=True):
    st=NS(sp=10.,mid=50.)
    syms=[NS(i=0,fam='rest',staff=0,bar=0,box=(40,45,50,55))]
    tok={0:{'cls':{'v':'rest_half'},'real':{'p':.99,'det':.9}}}
    if note:
        syms.append(NS(i=1,fam='note',staff=0,bar=0,box=(40,45,50,55)))
        tok[1]={'cls':{'v':'note_quarter'},'real':{'p':0.,'det':.7,'conflict_original_p':.7},
                'pos':{'v':0,'p':.99}}
    return NS(layout=NS(syms=syms,staves=[st]),tok=tok)


def test_image_evidence_can_reverse_confidence_only_false_rest_decision():
    rd=reading()
    apply_stem_verification(rd,{0:{'stem_found':True,'stem_score':.9}})
    assert rd.tok[0]['real']['p']==0
    assert rd.tok[1]['real']['p']==.7


def test_no_stem_abstains_and_rest_only_does_not_fabricate_pitch():
    rd=reading()
    apply_stem_verification(rd,{0:{'stem_found':False}})
    assert rd.tok[0]['real']['p']==.99 and rd.tok[1]['real']['p']==0
    rd=reading(note=False)
    apply_stem_verification(rd,{0:{'stem_found':True}})
    assert len(rd.tok)==1 and rd.tok[0]['cls']['v']=='rest_half'


def events():
    from copisteria.write import Event
    out=[]
    for i in range(3):
        beat=[1e-6]*16;beat[i]=.999
        frac=[1e-6]*48;frac[0]=.999
        out.append(Event(x=20+i*30,kind='note',typ='half',si=i,
                         onset=float(i),onset_p=.99,dist={'beat':beat,'frac':frac,'tup':None}))
    return out


def test_rhythm_uses_observed_alternatives_and_restores_hook():
    from copisteria import write
    original=write._voices
    options={0:{'half':.9,'quarter':.8},1:{'half':.9,'quarter':.8}}
    with supported_rhythm_choices(options) as changes:
        voices=write._voices(events(),10.,bar_len=Fraction(4))
        assert changes
        kept=[e for v in voices.values() for e in write._chop(v,Fraction(4)) if e.kind=='note']
        assert len(kept)==3
        assert all(e.typ in ('half','quarter') for e in kept)
    assert write._voices is original


def test_rhythm_without_observed_alternative_keeps_original_values():
    from copisteria import write
    with supported_rhythm_choices({}) as changes:
        voices=write._voices(events(),10.,bar_len=Fraction(4))
    assert not changes
    assert all(e.typ=='half' for v in voices.values() for e in v if e.kind=='note')
