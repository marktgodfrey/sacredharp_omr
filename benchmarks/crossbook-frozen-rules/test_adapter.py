import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('crossbook_frozen_adapter',Path(__file__).with_name('run_frozen_rules.py'))
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)


def test_baseline_parity_ignores_date_but_detects_musical_changes(tmp_path):
    left=tmp_path/'left.xml';right=tmp_path/'right.xml'
    xml='<score-partwise><identification><encoding><encoding-date>{}</encoding-date></encoding></identification><part><measure><note><duration>{}</duration></note></measure></part></score-partwise>'
    left.write_text(xml.format('2026-01-01',1));right.write_text(xml.format('2026-11-26',1))
    assert adapter.same_score_xml(left,right)
    right.write_text(xml.format('2026-11-26',2))
    assert not adapter.same_score_xml(left,right)


def test_pooled_metrics_weight_event_counts_instead_of_averaging_songs():
    def row(edits,denom,matches,pred,ref):
        return {'totals':{'pitch_duration_edit_distance':edits,'pitch_duration_rate_denominator':denom,
                          'prediction_notes':pred,'reference_notes':ref},
                'time_aware_exact_event_multiset':{'matches':matches}}
    result=adapter.pooled([row(1,2,1,2,2),row(0,98,98,98,98)])
    assert result['pd_rate']==.01 and result['time_aware_f1']==.99


def test_generation_fingerprints_no_reference_transcriptions():
    manifest,inputs=adapter.sealed_inputs()
    assert len(manifest['samples'])==14
    assert all('/reference/' not in name for name in inputs)
    assert {s['book'] for s in manifest['samples']}=={'1870-Sacred-MTS','1911-Sacred-EMU'}


def test_score_changes_track_pitch_duration_and_timing_independently():
    from score_results import change_counts
    rows=[{'pd_change_current_vs_prior':-1,'f1_change_current_vs_prior':0},
          {'pd_change_current_vs_prior':0,'f1_change_current_vs_prior':.001},
          {'pd_change_current_vs_prior':1,'f1_change_current_vs_prior':-.01}]
    assert change_counts(rows)=={'pd_better':1,'pd_tied':1,'pd_worse':1,
                                 'f1_better':1,'f1_tied':1,'f1_worse':1}
