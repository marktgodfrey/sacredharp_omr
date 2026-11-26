from summarize_source_timing_recovery import validate_bar_cut


def test_bar_cut_matches_its_global_measure():
    assert validate_bar_cut({'bar': 2, 'selected_cut': '3/2'}, ['3', '3/2'])


def test_bar_cut_rejects_membership_in_wrong_measure():
    assert not validate_bar_cut({'bar': 2, 'selected_cut': '3'}, ['3', '3/2'])
