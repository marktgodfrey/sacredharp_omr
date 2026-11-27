from audit_bar_meter import xml_inventory


def xml(content):
    return '<score-partwise><part id="P1">'+content+'</part></score-partwise>'


def attrs():
    return '<attributes><divisions>2</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>'


def test_polyphonic_backup_and_chord_do_not_sum_parallel_time():
    s=xml('<measure number="1">'+attrs()+'<note><duration>8</duration></note>'
          '<backup><duration>8</duration></backup><note><duration>8</duration><voice>2</voice></note>'
          '<note><chord/><duration>8</duration><voice>2</voice></note></measure>')
    r=xml_inventory(s)['measures'][0]
    assert r['encoded_span_quarters']=='4' and r['status']=='nominal'


def test_forward_padding_and_overfull_span_are_recorded():
    s=xml('<measure number="1">'+attrs()+'<note><duration>4</duration></note>'
          '<note print-object="no"><rest/><duration>4</duration></note></measure>'
          '<measure number="2"><forward><duration>2</duration></forward><note><duration>8</duration></note></measure>')
    a,b=xml_inventory(s)['measures']
    assert a['invisible_padding_quarters']=='2' and a['status']=='nominal'
    assert b['encoded_span_quarters']=='5' and b['status']=='over_nominal'


def test_pickup_terminal_complement_and_unmarked_short_are_separate():
    s=xml('<measure number="1" implicit="yes">'+attrs()+'<note><duration>2</duration></note></measure>'
          '<measure number="2"><note><duration>6</duration></note><barline location="right"><repeat direction="backward"/></barline></measure>'
          '<measure number="3"><note><duration>6</duration></note></measure>')
    assert [r['status'] for r in xml_inventory(s)['measures']]==['short_implicit','short_terminal_candidate','short_unmarked']
