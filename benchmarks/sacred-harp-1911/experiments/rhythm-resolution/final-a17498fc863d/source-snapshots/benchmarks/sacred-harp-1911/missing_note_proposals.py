"""Opt-in note alternatives from unedited pixels at rest-like physical heads.

Keep the visual note mass and conditional duration distribution separate. The
context model consumes symbolic observations, not pixels; its output cannot
replace the independent visual check. Existing layout and tokens stay intact.
"""
from __future__ import annotations

from glyph_verifier import verify_head
from note_rest_evidence import short_stem_evidence
from reader_policy import near_head
from head_morphology import head_morphology

OPEN_NOTES = {'note_half', 'note_whole', 'note_breve', 'note_long'}


def duration_posterior(record, site):
    """Filled ink rules out open-head durations; retain actual visual weights."""
    morph = site.get('head_morphology', {})
    hollow = morph.get('hollow_head', False)
    filled = (not hollow and (site.get('head_evidence', {}).get('head_ink_fraction', 0) >= .55
                             or morph.get('central_ink_fraction', 0) >= .45))
    return {k: p for k, p in record['class_probabilities'].items()
            if k.startswith('note_') and not (filled and k in OPEN_NOTES)
            and not (hollow and k not in OPEN_NOTES)}


def proposal_sites(rd, image):
    """Find head-sized rest observations with no note interpretation nearby.

    This selection has no reviewed case IDs, reference score or target count.
    Weak sites remain diagnostics until visual/context evidence supports them.
    """
    sites = []
    for s in rd.layout.syms:
        r = rd.tok.get(s.i, {})
        cls = r.get('cls', {}).get('v', '')
        if (s.staff < 0 or s.bar < 0 or s.fam not in ('rest', 'mRest')
                or not (cls.startswith('rest_') or cls == 'mRest_measure')):
            continue
        st = rd.layout.staves[s.staff]
        if any(n.staff == s.staff and n.bar == s.bar
               and rd.tok.get(n.i, {}).get('cls', {}).get('v', '').startswith('note_')
               and near_head(n.box, s.box, st.sp) for n in rd.layout.syms):
            continue
        # Ordinary half/whole rests are shallow rectangles. Retain only boxes
        # with both dimensions comparable to a printed shape-note head.
        w, h = s.box[2]-s.box[0], s.box[3]-s.box[1]
        if not (.65 <= w/st.sp <= 1.65 and .65 <= h/st.sp <= 1.65 and .6 <= w/h <= 1.65):
            continue
        evidence = verify_head(image, s.box, st.sp, rd.layout.bar_box(s.staff, s.bar))
        if evidence['reason'] in ('no_head_ink', 'invalid_image', 'box_not_head_like'):
            continue
        short = short_stem_evidence(image, s.box, st.sp, rd.layout.bar_box(s.staff, s.bar))
        sites.append({'anchor_id': s.i, 'box': list(s.box), 'staff': s.staff, 'bar': s.bar,
                      'staff_space': st.sp, 'geometry_position': round((st.mid-s.cy)*2/st.sp),
                      'head_morphology': head_morphology(image, s.box, evidence['ink_threshold']),
                      'head_evidence': evidence, 'short_stem_evidence': short})
    return sites


def visual_alternative(probe, site):
    """Choose a visual alternative within .42 staff spaces of this head centre."""
    sp = site['staff_space']
    box = site['box']
    choices = []
    for r in probe['records']:
        refined = r['refined_source_xyxy']
        w, h = refined[2]-refined[0], refined[3]-refined[1]
        if (not near_head(box, refined, .6*sp)
                or not (.45*sp <= w <= 1.9*sp and .4*sp <= h <= 1.9*sp)):
            continue
        # Retain raw objectness times *all* note-class mass, before conditioning
        # on the note family. Do not turn tiny runner-ups into confident notes.
        score = r['objectness_probability'] * sum(duration_posterior(r, site).values())
        # A closed outline independently identifies an open head. The visual
        # network's note-family mass supports object type; its duration scores
        # remain conditional on that image measurement, rather than pretending
        # a filled-duration mistake is evidence for an actual filled head.
        if site.get('head_morphology', {}).get('hollow_head'):
            score = r['objectness_probability'] * r['note_family_mass']
        compatible = 1.
        if 'geometry_position' in site:
            pos = site['geometry_position']
            compatible = sum(p for k, p in r['attributes'].get('staff_position', {}).items()
                             if k.lstrip('-').isdigit() and abs(int(k)-pos) <= 1)
        choices.append((score*compatible, score, r))
    if not choices:
        return None
    selection, score, record = max(choices, key=lambda v: v[0])
    return {'visual_note_probability': score, 'position_weighted_selection_score': selection, 'record': record}


def append_alternative(rd, site, alternative):
    """Append a note-family hypothesis, preserving its visual prior explicitly."""
    from copisteria.front import Sym
    from copisteria.vocab import CLS_ID
    r = alternative['record']
    allowed = duration_posterior(r, site)
    note_p = {CLS_ID[k]: p for k, p in allowed.items()}
    mass = sum(note_p.values())
    if mass <= 0:
        raise ValueError('No visual note-class probability')
    post = {k: v/mass for k, v in note_p.items()}
    attrs = {k: max(v, key=v.get) for k, v in r['attributes'].items()}
    ap = {k: float(v[attrs[k]]) for k, v in r['attributes'].items()}
    i = len(rd.layout.syms)
    s = Sym(i, max(allowed, key=allowed.get), post, alternative['visual_note_probability'], 1,
            tuple(site['box']), attrs, ap, r['attributes'], site['staff'], site['bar'],
            det=-1, cand=True)
    rd.layout.syms.append(s)
    return i


def decode_appended(rd, ids, model):
    """Decode on fixed geometry and copy back only the newly appended tokens."""
    from copisteria.read import read_layout
    context = read_layout(rd.layout, model, attention=False)
    for i in ids:
        rd.tok[i] = context.tok[i]
    return {i: context.tok[i] for i in ids}


def suppress_measure_rest_conflicts(rd, supported_ids):
    """A whole-measure rest cannot occupy the voice of a verified new note.

    This is only an experimental candidate reading. The local writer still
    compares the complete bar with baseline and protects every baseline pitch.
    Ordinary rests and other staff-bars/voices are untouched.
    """
    bars = {(rd.layout.syms[i].staff, rd.layout.syms[i].bar)
            for i in supported_ids if rd.tok[i]['real']['p'] >= .5
            and rd.tok[i]['cls']['v'].startswith('note_')
            and rd.tok[i].get('voice', {}).get('v', 1) == 1}
    decisions = []
    for s in rd.layout.syms:
        r = rd.tok.get(s.i, {})
        if ((s.staff, s.bar) in bars and r.get('cls', {}).get('v') == 'mRest_measure'
                and r['real']['p'] >= .5):
            old = r['real']['p']
            r['real']['proposal_original_p'] = old; r['real']['p'] = 0
            decisions.append({'sym_id': s.i, 'staff': s.staff, 'bar': s.bar, 'old_p': old,
                              'action': 'whole_measure_rest_conflicts_with_verified_note'})
    return decisions
