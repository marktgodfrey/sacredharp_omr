"""Opt-in selection of complete staff-bars under a saved source-derived meter.

Candidates use existing neural events and image evidence. Baseline column cuts
are fixed, and selection precedes the writer's tie/beam/slur attachment phase.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager


@contextmanager
def capture_built():
    """Capture each complete writer pass without changing its selected events."""
    from copisteria import write
    original = write.write
    passes = []

    def wrapped(*args, **kwargs):
        snapshot = {}
        requested = kwargs.pop('bar_transform', None)

        def capture(built, opening):
            selected, cuts = requested(built, opening) if requested is not None else (built, None)
            snapshot.update(built=copy.deepcopy(selected), opening=opening,
                            cuts=write._column_lengths(selected) if cuts is None else list(cuts))
            return selected, cuts

        xml = original(*args, **kwargs, bar_transform=capture)
        passes.append({**snapshot, 'xml': xml})
        return xml

    write.write = wrapped
    try:
        yield passes
    finally:
        write.write = original


def same_head(rd, a, b):
    if a.si == b.si:
        return True
    if a.si < 0 or b.si < 0:
        return False
    sa, sb = rd.layout.syms[a.si], rd.layout.syms[b.si]
    if sa.staff != sb.staff or sa.bar != sb.bar:
        return False
    from bar_fitting import _overlap
    sp = rd.layout.staves[sa.staff].sp
    cover, iou = _overlap(sa.box, sb.box)
    return abs(a.x-b.x) <= .35*sp and (cover >= .8 or iou >= .65)


def final_notes(voices, cut):
    from copisteria import write
    return [e for vs in copy.deepcopy(voices).values() for e in write._chop(vs, cut)
            if e.kind == 'note']


def select_candidate(rd, baseline, candidates, cut, verified):
    """Require baseline physical pitches and gain independently verified heads."""
    before = final_notes(baseline, cut)
    best, best_gain, label = baseline, [], 'frozen'
    trials = []
    for name, voices in candidates:
        after = final_notes(voices, cut)
        lost = [e.si for e in before if not any(same_head(rd, e, f)
                and (e.step,e.octave,e.alter) == (f.step,f.octave,f.alter) for f in after)]
        gain = [e.si for e in after if (verified.get(e.si, {}).get('stem_found')
                or verified.get(e.si, {}).get('note_proposal_supported'))
                and not any(same_head(rd, e, f) for f in before)]
        trials.append({'candidate': name, 'lost_physical_notes': lost, 'added_verified_heads': gain})
        if not lost and len(set(gain)) > len(set(best_gain)):
            best, best_gain, label = voices, gain, name
    return copy.deepcopy(best), {'selected': label, 'added_verified_heads': best_gain, 'trials': trials}


def recovery_transform(rd, frozen_pass, verified, decisions):
    """Select full voice sets per staff-bar; retain frozen global column lengths."""
    from copisteria import write
    baseline = frozen_pass['built']
    cuts = frozen_pass['cuts']

    def transform(built, opening):
        if opening != frozen_pass['opening']:
            raise ValueError('Recovery must retain the baseline opening meter')
        if len(built) != len(baseline):
            raise ValueError('Recovery cannot change part planning')
        selected = copy.deepcopy(baseline)
        for p, (measures, old_measures) in enumerate(zip(built, baseline)):
            if len(measures) != len(old_measures):
                raise ValueError('Recovery cannot change bar columns')
            for m, (measure, old_measure) in enumerate(zip(measures, old_measures)):
                for k, (staff, old) in enumerate(zip(measure['staves'], old_measure['staves'])):
                    if staff is None or old is None:
                        if staff is not old:
                            raise ValueError('Recovery cannot change hidden staves')
                        continue
                    if (staff['staff'], staff['bar'], staff['state']) != (old['staff'], old['bar'], old['state']):
                        raise ValueError('Recovery cannot change staff identity, clef, key or meter')
                    cut = cuts[m]
                    if cut is None:
                        continue
                    # Rebuild the entire source staff-bar at the *actual column
                    # cut*, which can be shorter than nominal meter (pickups).
                    sid, bar = staff['staff'], staff['bar']
                    st = rd.layout.staves[sid]
                    system = rd.layout.systems[st.system]
                    columns = system.columns[system.staves.index(sid)]
                    merged = [j for j,c in enumerate(columns) if c == columns[bar]]
                    events = []
                    for j in merged:
                        ev, _, _ = write._events(rd, sid, j, staff['state']['clef'], staff['state']['key'], [])
                        events.extend(ev)
                    candidates = [('verified_meter', staff['voices'])]
                    if events:
                        voices = write._voices(events, st.sp,
                            single_staff_part=len(measure['staves']) == 1, bar_len=cut)
                        candidates.append(('verified_column_cut', voices))
                    voices, detail = select_candidate(rd, old['voices'], candidates, cut, verified)
                    chosen = copy.deepcopy(old if detail['selected'] == 'frozen' else staff)
                    chosen['voices'] = voices
                    selected[p][m]['staves'][k] = chosen
                    decisions.append({'part': p+1, 'measure': m+1, 'staff': sid, 'bar': bar,
                        'cut': str(cut), 'meter': staff['state']['time'], **detail})
        return selected, list(cuts)

    return transform
