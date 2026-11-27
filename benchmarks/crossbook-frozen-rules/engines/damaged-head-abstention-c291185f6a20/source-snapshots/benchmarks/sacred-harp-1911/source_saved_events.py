"""Reconstruct source-linked final writer Events from saved XML and trace."""
from __future__ import annotations

from fractions import Fraction
import xml.etree.ElementTree as ET


def _tag(element):
    return element.tag.rsplit('}', 1)[-1]


def _child_text(parent, name, default=None):
    child = next((x for x in parent if _tag(x) == name), None)
    return child.text if child is not None and child.text is not None else default


def _frac(value):
    return Fraction(str(value))


def _xml_note_records(xml):
    from copisteria import write
    mark_names={v:k for table in (write.ARTIC,write.AFTER_MARK,write.TECH,write.ORNAMENT)
                for k,v in table.items()}
    root = ET.fromstring(xml) if isinstance(xml, (str, bytes)) else xml
    records=[]
    for part_no, part in enumerate((x for x in root if _tag(x) == 'part'), 1):
        divisions=1
        for measure in (x for x in part if _tag(x) == 'measure'):
            for node in measure:
                name=_tag(node)
                if name == 'attributes':
                    d=_child_text(node,'divisions')
                    if d: divisions=int(d)
                elif name in ('backup','forward'):
                    amount=_frac(_child_text(node,'duration','0'))/divisions
                    records.append({'kind':name,'part':part_no,'measure':measure.get('number'),
                                    'duration':amount})
                elif name == 'note':
                    if node.get('print-object') == 'no':
                        # Generated invisible padding is not a source Event and
                        # has no matching source symbol in the writer trace.
                        records.append({'kind':'padding','part':part_no,
                                        'measure':measure.get('number'),
                                        'duration':_frac(_child_text(node,'duration','0'))/divisions})
                        continue
                    duration=_frac(_child_text(node,'duration','0'))/divisions
                    pitch=next((x for x in node if _tag(x) == 'pitch'),None)
                    rest=next((x for x in node if _tag(x) == 'rest'),None)
                    ties=[x.get('type') for x in node if _tag(x) == 'tie']
                    marks=[mark_names[_tag(x)] for x in node.iter() if _tag(x) in mark_names]
                    if any(_tag(x)=='fermata' for x in node.iter()):marks.append('fermata')
                    records.append({'kind':'note','part':part_no,'measure':measure.get('number'),
                        'duration':duration,'voice':int(_child_text(node,'voice','1')),
                        'staff_no':int(_child_text(node,'staff','1')),
                        'grace':any(_tag(x)=='grace' for x in node),
                        'chord':any(_tag(x)=='chord' for x in node),
                        'step':_child_text(pitch,'step') if pitch is not None else 'C',
                        'octave':int(_child_text(pitch,'octave','4')) if pitch is not None else 4,
                        'alter':int(_child_text(pitch,'alter','0')) if pitch is not None else 0,
                        'rest':rest is not None,'tie_start':'start' in ties,'tie_stop':'stop' in ties,
                        'accidental':_child_text(node,'accidental',''),'marks':marks,
                        'arpeggiate':any(_tag(x)=='arpeggiate' for x in node.iter()),
                        'xml_type':_child_text(node,'type'), 'xml_dots':sum(_tag(x)=='dot' for x in node)})
    return records


def source_saved_events(trace, xml):
    """Return ``(events_by_staff, metadata)`` from a saved final trace and MusicXML.

    The final XML establishes serialized order, cursor onsets, chords, ties and
    actual durations after backups/forwards. Source event attributes and source
    symbol identities come from the writer's final ``_note`` trace. Negative or
    absent source IDs (padding/generated events) are excluded explicitly.
    """
    from copisteria.write import Event

    records=_xml_note_records(xml)
    xml_events=[r for r in records if r['kind']=='note']
    emitted=trace.get('writer',{}).get('emitted',[])
    source=[e for e in emitted if int(e.get('e.si',-1)) >= 0]
    if len(xml_events) != len(source):
        raise ValueError(f'XML/source trace event count differs: {len(xml_events)} XML events, {len(source)} traced source events')

    # Cursor is MusicXML's per-part measure stream position; backup/forward
    # operations are retained in metadata and applied before the next note.
    events_by_staff={}
    metadata=[]
    cursor=Fraction(0)
    root_onset=Fraction(0)
    part=measure=None
    event_index=0
    for record in records:
        if record['kind']=='padding':
            if part != record['part'] or measure != record['measure']:
                part,measure=record['part'],record['measure'];cursor=Fraction(0)
            cursor += record['duration']
            continue
        if record['kind'] in ('backup','forward'):
            if part != record['part'] or measure != record['measure']:
                part,measure=record['part'],record['measure'];cursor=Fraction(0)
            cursor += -record['duration'] if record['kind']=='backup' else record['duration']
            metadata.append({'kind':record['kind'],'part':part,'measure':measure,
                             'duration':str(record['duration']),'cursor_after':str(cursor)})
            continue
        if record['kind']!='note':
            continue
        if part != record['part'] or measure != record['measure']:
            part,measure=record['part'],record['measure'];cursor=Fraction(0)
        # XML note order and final _note calls are identical after padding removal.
        index=event_index
        t=source[index]
        si=int(t['e.si'])
        syms=trace.get('syms',[])
        if si >= len(syms):
            raise ValueError(f'trace symbol index {si} is out of range')
        staff=int(syms[si].get('staff',-1))
        if staff < 0:
            raise ValueError(f'trace symbol {si} has no physical staff')
        onset=root_onset if record['chord'] else cursor
        if not record['chord']:root_onset=cursor
        # Ensure source trace and actual XML describe the same serialized event.
        expected_kind='rest' if record['rest'] else 'note'
        if t.get('kind') not in (expected_kind,'mrest' if record['rest'] else expected_kind):
            raise ValueError(f'XML/trace kind mismatch at event {index}: {expected_kind} vs {t.get("kind")}')
        duration=record['duration']
        if t.get('kind') != 'mrest' and _frac(t.get('e.dur', duration)) != duration:
            raise ValueError(f'XML/trace duration mismatch at {index}')
        event=Event(x=float(t.get('x',0)),kind=t.get('kind',expected_kind),typ=t.get('typ','quarter'),
                    dots=int(t.get('dots',0)),voice=record['voice']-4*(record['staff_no']-1),
                    chord=record['chord'],tup=t.get('tup','none'),step=record['step'],
                    octave=record['octave'],alter=record['alter'],tie=record['tie_start'],
                    tie_stop=record['tie_stop'],dur=duration,si=si,onset=float(onset))
        event.accidental=record['accidental'];event.marks=record['marks'];event.arpeggiate=record['arpeggiate']
        if record['grace']:
            event.grace=trace.get('tokens',{}).get(str(si),{}).get('grace',{}).get('v','acc')
        events_by_staff.setdefault(staff,[]).append(event)
        metadata.append({'kind':'event','source_si':si,'staff':staff,'part':record['part'],
                         'measure':record['measure'],'onset':str(onset),
                         'xml_duration':str(record['duration']),'trace_duration':str(duration),
                         'xml_voice':record['voice'],'trace_voice':int(t.get('voice',record['voice']))})
        cursor += record['duration'] if not record['chord'] else Fraction(0)
        event_index += 1
    return events_by_staff, metadata
