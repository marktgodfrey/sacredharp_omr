import glob
import json
import os
import sys
from fractions import Fraction

import pytest

ROOT=os.path.dirname(__file__)
sys.path.insert(0,os.path.join(ROOT,'..','..','copisteria','src'))
sys.path.insert(0,ROOT)
from source_saved_events import source_saved_events


def test_chords_backups_forwards_and_ties_reconstruct_actual_xml_positions():
    trace={'syms':[{'staff':3}], 'writer':{'emitted':[{
        'e.si':0,'kind':'note','x':12.5,'step':'C','octave':4,'alter':0,
        'typ':'quarter','dots':0,'tup':'none','e.dur':'1','dur':4,'voice':1},
        {'e.si':0,'kind':'note','x':12.5,'step':'E','octave':4,'alter':0,
         'typ':'quarter','dots':0,'tup':'none','e.dur':'1','dur':4,'voice':1},
        {'e.si':0,'kind':'rest','x':8,'step':'C','octave':4,'alter':0,
         'typ':'half','dots':0,'tup':'none','e.dur':'2','dur':8,'voice':2}]}}
    xml='''<score-partwise><part id="P1"><measure number="1"><attributes><divisions>4</divisions></attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type><tie type="start"/><accidental>natural</accidental><notations><fermata/><articulations><staccato/></articulations></notations></note>
      <note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>
      <backup><duration>8</duration></backup><forward><duration>8</duration></forward>
      <note><rest/><duration>8</duration><voice>2</voice><type>half</type><tie type="stop"/></note>
      <note print-object="no"><rest/><duration>4</duration><voice>1</voice></note>
      </measure></part></score-partwise>'''
    by_staff,meta=source_saved_events(trace,xml)
    assert len(by_staff[3])==3
    first,chord,rest=by_staff[3]
    assert first.onset==0 and first.dur==Fraction(1) and first.tie
    assert first.accidental=='natural' and set(first.marks)=={'fermata','artic_stacc'}
    assert chord.chord and chord.onset==0 and chord.step=='E'
    assert rest.onset==1 and rest.voice==2 and rest.tie_stop and rest.dur==2
    assert [m['kind'] for m in meta if m['kind']!='event']==['backup','forward']


def test_golden_harp_part_one_measure_two_padding_rest_is_not_returned():
    path=os.path.join(ROOT,'experiments/proposal-rhythm/final-0318d4f06bb9/predictions/1911-s0288-the-golden-harp')
    trace=json.load(open(path+'.trace.json'))
    by_staff,metadata=source_saved_events(trace,open(path+'.musicxml',encoding='utf-8').read())
    m2=[m for m in metadata if m.get('part')==1 and m.get('measure')=='2' and m['kind']=='event']
    assert len(m2)==3
    assert all(m['source_si']>=0 for m in m2)
    assert len([e for events in by_staff.values() for e in events if e.si<0])==0


def test_all_120_saved_musicxml_traces_roundtrip_source_event_ids():
    base=os.path.join(ROOT,'experiments/proposal-rhythm/final-0318d4f06bb9/predictions')
    traces=sorted(glob.glob(os.path.join(base,'*.trace.json')))
    assert len(traces)==120
    for path in traces:
        trace=json.load(open(path,encoding='utf-8'))
        xml=open(path[:-10]+'musicxml',encoding='utf-8').read()
        by_staff,metadata=source_saved_events(trace,xml)
        actual=[event.si for events in by_staff.values() for event in events]
        expected=[int(e['e.si']) for e in trace['writer']['emitted'] if int(e.get('e.si',-1))>=0]
        assert sorted(actual)==sorted(expected),os.path.basename(path)
        assert all(e.si>=0 for events in by_staff.values() for e in events)
