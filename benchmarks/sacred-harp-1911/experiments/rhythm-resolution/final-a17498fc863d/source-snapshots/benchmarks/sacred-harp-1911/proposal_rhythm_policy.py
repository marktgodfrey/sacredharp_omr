"""Opt-in rhythm constraints from saved visual posteriors and source ink.

The evidence model consumes symbols. A confident direct pixel reading is kept
when symbolic context changes its duration; weak dot additions also need ink.
"""
from __future__ import annotations

import copy
from missing_note_proposals import duration_posterior, OPEN_NOTES
from proposal_rhythm_evidence import detached_dot_evidence


def constrain_proposal_rhythms(rd, additions, image, constraints):
    decisions = []
    for a in additions:
        i = a.get('proposal_id')
        if i is None or a.get('decision') != 'visual_context_supported':
            continue
        r = rd.tok[i]
        if not r['cls']['v'].startswith('note_'):
            continue
        visual = a['visual_alternative']['record']
        allowed = duration_posterior(visual, a)
        mass = sum(allowed.values())
        if mass:
            best = max(allowed, key=allowed.get)
            confidence = allowed[best] / mass
            # A normalized duration posterior is conditional on note admission,
            # not a new calibrated probability that the physical object is real.
            # Shape-note runner-ups do not reliably distinguish a stemless
            # whole head from a half, or independently establish a new flag.
            # Keep this repair narrow: undo a weak fast reading only when the
            # direct pixels strongly identify a filled quarter. Existing open
            # and faster durations require separate stem/flag evidence.
            if (best == 'note_quarter' and r['cls']['v'] not in OPEN_NOTES
                    and confidence >= .85 and r['cls'].get('p', 1) < .9
                    and best != r['cls']['v']):
                decisions.append({'sym_id': i, 'action': 'direct_visual_duration',
                    'before': copy.deepcopy(r['cls']), 'after': best,
                    'conditional_visual_probability': confidence})
                r['cls'] = {'v': best, 'p': confidence, 'source_visual_constraint': True}
                constraints[i] = {best.split('_', 1)[1]}
        dots = visual.get('attributes', {}).get('dots', {})
        no_dot = dots.get('<na>', dots.get('0', 0))
        if r.get('dots', {}).get('v', 0) > 0 and r['dots'].get('p', 1) < .9 and no_dot >= .9:
            evidence = detached_dot_evidence(image, a['box'], a['staff_space'],
                threshold=a['head_evidence'].get('ink_threshold') or 175)
            decisions.append({'sym_id': i, 'action': 'check_context_dot',
                'before': copy.deepcopy(r['dots']), 'visual_no_dot_probability': no_dot,
                'source_dot_evidence': evidence})
            if evidence['visible'] and not evidence['present']:
                r['dots'] = {'v': 0, 'p': no_dot, 'source_visual_constraint': True}
                decisions[-1]['action'] = 'reject_unsupported_context_dot'
    return decisions


def restore_lossy_rhythm_bars(rd, before, constraints, prior_constraints, decisions, lost_ids):
    """Abstain from rhythm edits that would remove an already recovered head."""
    bars = {(rd.layout.syms[i].staff, rd.layout.syms[i].bar) for i in lost_ids}
    active = [d for d in decisions if d['action'] != 'check_context_dot' and not d.get('rejected')]
    affected = [d for d in active if (rd.layout.syms[d['sym_id']].staff,
                rd.layout.syms[d['sym_id']].bar) in bars]
    # A cross-bar writer dependency can make the affected bar indirect. In that
    # case abstain from all remaining edits instead of permitting silent loss.
    if not affected:
        affected = active
    for d in affected:
        i = d['sym_id']
        for key in ('cls', 'dots'):
            rd.tok[i][key] = copy.deepcopy(before.tok[i][key])
        constraints[i] = set(prior_constraints[i])
        d.update(rejected=True, rejection='would_remove_previous_physical_head',
                 lost_physical_head_ids=list(lost_ids))
    return len(affected)
