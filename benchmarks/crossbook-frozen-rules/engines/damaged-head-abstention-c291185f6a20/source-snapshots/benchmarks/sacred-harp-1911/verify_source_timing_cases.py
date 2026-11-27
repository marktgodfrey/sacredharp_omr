"""Check source-reviewed meter/bar cases after a complete timing replay."""
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET
from run_local_recovery import ROOT, read, save, sha
from run_source_timing_recovery import PARENT
from audit_bar_meter import xml_inventory


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('experiment',type=Path)
    out=parser.parse_args().experiment.resolve();rows=read(out/'results.json')['samples'];by_title={r['title']:r for r in rows}
    def trace(title):return read((ROOT/by_title[title]['prediction']).with_suffix('.trace.json'))
    findings=read(ROOT/'diagnostics/bar-meter-audit/confirmed-findings.json')['cases'];checked=[]
    for case in findings:
        if case['category']!='wrong_opening_meter':continue
        t=trace(case['title']);assert t['final_timing']['opening_meter']==case['source_meter']
        assert all(p['meter_changes'][0]['meter']==case['source_meter'] for p in t['final_timing']['xml_inventory']['parts'])
        checked.append({'title':case['title'],'opening_meter':case['source_meter'],'all_parts':True})
    controls={}
    for title,expected in [('Primrose Hill',['6/8','3/4','6/8']),('Greenland',['2/4','6/8','3/4']),
                           ('Vermont',['4/4']),('Weary Pilgrim',['6/4'])]:
        t=trace(title);actual=[r['meter'] for r in t['source_meter_state']['transitions']];assert actual==expected,(title,actual)
        positions=[];offset=0
        for i,system in enumerate(t['systems']):
            positions += [(offset+e['column']+1,e['meter']) for e in t['source_meter_state']['transitions'] if e['system']==i]
            offset+=1+max(max(c) for c in system['columns'] if c)
        for part in t['final_timing']['xml_inventory']['parts']:
            assert all(any(x['measure']==m and x['meter']==meter for x in part['meter_changes']) for m,meter in positions)
        controls[title]={'sequence':actual,'xml_positions':positions}
    golden=trace('The Golden Harp');golden_bar=next(m for m in golden['final_timing']['xml_inventory']['measures'] if (m['part'],m['measure'])==(1,2))
    assert golden_bar['encoded_span_quarters']=='2' and golden_bar['invisible_padding_quarters']=='0'
    xml=ET.parse(ROOT/by_title['The Golden Harp']['prediction']).getroot()
    measure=xml.find('part').findall('measure')[1];divisions=int(xml.findtext('part/measure/attributes/divisions'))
    assert [Fraction(int(n.findtext('duration')),divisions) for n in measure.findall('note') if n.find('pitch') is not None]==[1,Fraction(1,2),Fraction(1,2)]
    salem=trace('Salem');bars={salem['syms'][i]['bar'] for i in (260,393)};assert len(bars)==1
    bar_no=next(iter(bars));assert salem['final_timing']['selected_cuts'][bar_no]=='4'
    assert all(abs(x-bad)>10 for x in salem['source_bar_grid'][0]['cuts'] for bad in (2641.4,2792.8))
    fillmore=trace('Fillmore');assert all(d['new_bar_count']>max(d['old_bar_counts']) for d in fillmore['source_bar_grid'])
    farewell=trace('Farewell To All')
    assert all(farewell['syms'][i]['box'][2]-farewell['syms'][i]['box'][0]>=st['sp'] for st in farewell['staves'] for i in st['bars'])
    columns=part_measures=0
    for r in rows:
        t=read((ROOT/r['prediction']).with_suffix('.trace.json'));inventory=xml_inventory((ROOT/r['prediction']).read_text());cuts=t['final_timing']['selected_cuts']
        assert not inventory['columns_with_unequal_part_spans'],r['id']
        for bar in inventory['measures']:
            assert Fraction(bar['encoded_span_quarters'])==Fraction(cuts[bar['measure']-1]),(r['id'],bar)
        columns+=len(cuts);part_measures+=len(inventory['measures'])
        for title,i in [('Newburgh',727),('Chambers',568)]:
            if r['title']!=title:continue
            old=read(PARENT/'predictions'/f"{r['id']}.trace.json")
            a=[(e['typ'],e['e.dur']) for e in old['writer']['emitted'] if e['kind']=='note' and e['e.si']==i]
            b=[(e['typ'],e['e.dur']) for e in t['writer']['emitted'] if e['kind']=='note' and e['e.si']==i]
            assert a==b,(title,i,a,b)
    historical=read(PARENT/'artifact-sha256.json')
    assert all(sha(PARENT/name)==digest for name,digest in historical.items())
    actual={str(f.relative_to(PARENT)) for f in PARENT.rglob('*') if f.is_file() and 'source-snapshots' not in f.parts and f.name!='artifact-sha256.json'}
    assert actual==set(historical),'historical artifact file set changed'
    result={'opening_meters':checked,'meter_transition_controls':controls,
        'golden_harp_p1_m2':golden_bar,'salem_previous_fragment_heads':[260,393],
        'salem_new_measure':bar_no+1,'salem_shared_quarters':'4',
        'fillmore_source_candidate_counts':[d['new_bar_count'] for d in fillmore['source_bar_grid']],
        'fillmore_exact_source_counts_adjudicated':False,'farewell_thin_fragments_removed':True,
        'songs':len(rows),'shared_columns':columns,'part_measures_with_exact_common_span':part_measures,
        'stemless_whole_controls_preserved':True,'historical_artifact_hashes_and_file_set_verified':len(historical)}
    if all('rhythm_resolution_details' in trace(title) and trace(title)['rhythm_resolution_details']['enabled']
           for title in ('Lenox','Ragan')):
        rhythm_checks={}
        for title in ('Lenox','Ragan','Duane Street'):
            t=trace(title);unresolved=[d['column'] for d in t['source_bar_fit_decisions'] if not d['resolved']]
            assert not unresolved,(title,'remaining overflow',unresolved)
            rhythm_checks[title]={'unresolved_columns':unresolved,'columns':len(t['source_bar_fit_decisions'])}
        weeping=next(r for r in rows if r['id']=='1911-33t-weeping-savior')
        t=read((ROOT/weeping['prediction']).with_suffix('.trace.json'))
        assert t['final_timing']['opening_meter']=='4/4'
        assert all(p['meter_changes'][0]['meter']=='4/4' for p in t['final_timing']['xml_inventory']['parts'])
        rhythm_checks[weeping['id']]={'source_opening_meter':'4/4','all_parts':True,
            'rejected_template_probe':t['source_opening_ink_probe']}
        t=trace('Ninety-Third Psalm')
        irregular=[{'column':d['column'],'selected_cut':d['selected_cut'],'nominal_quarters':d['nominal_quarters']}
                   for d in t['source_bar_fit_decisions'] if not d['resolved']]
        assert t['final_timing']['opening_meter']=='3/4' and irregular
        rhythm_checks['Ninety-Third Psalm']={'printed_meter_preserved':'3/4',
            'user_decision':'Preserve printed 3/4 and flag the irregular bars',
            'irregular_bars':irregular,'source_value_meter_conflict_resolved':False}
        previous=ROOT/'experiments/source-timing/final-0eaa4b28dd55'
        manifest=read(previous/'artifact-sha256.json')
        assert all(sha(previous/name)==digest for name,digest in manifest.items())
        actual={str(f.relative_to(previous)) for f in previous.rglob('*') if f.is_file()
                and 'source-snapshots' not in f.parts and f.name!='artifact-sha256.json'}
        assert actual==set(manifest)
        result['rhythm_resolution_checks']=rhythm_checks
        result['previous_source_timing_artifacts_unchanged']=len(manifest)
    save(out/'source-case-checks.json',result);print(result)

if __name__=='__main__':main()
