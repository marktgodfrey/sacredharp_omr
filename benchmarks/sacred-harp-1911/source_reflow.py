"""Reflow saved staff-bar voices after a source-supported system repair.

Ordinary reflow preserves selected event values and inherited bar lengths. Only
collapsed bars with repeated confident beat-zero readings try ink segmentation;
that candidate is accepted only if every previously emitted physical head stays.
"""
from __future__ import annotations

import copy
from collections import defaultdict
from fractions import Fraction
import numpy as np


def emitted_head_ids(writer):
    return {e['e.si'] for e in writer['emitted'] if e['kind'] == 'note' and e['e.si'] >= 0}


def collapsed_bar_evidence(rd):
    evidence = []
    for k, st in enumerate(rd.layout.staves):
        for j, bi in enumerate(st.bars):
            b = rd.layout.syms[bi].box
            zero = sorted(s.cx for s in rd.layout.syms if s.staff == k and s.bar == j
                and rd.tok.get(s.i, {}).get('real', {}).get('p', 0) >= .5
                and rd.tok.get(s.i, {}).get('cls', {}).get('v', '').startswith('note_')
                and rd.tok[s.i].get('onset_p', 0) >= .9
                and abs(rd.tok[s.i].get('onset', 99) or 0) < .03)
            separate = []
            for x in zero:
                if not separate or x-separate[-1] > 2*st.sp:
                    separate.append(x)
            if (b[2]-b[0])/st.sp > 12 and len(separate) >= 2:
                evidence.append({'staff': k, 'bar': j, 'width_staff_spaces': (b[2]-b[0])/st.sp,
                                 'separate_confident_beat_zero_x': separate})
    return evidence


def segment_source_bars(rd, image):
    """Use existing front-end ink voting on already repaired source systems."""
    from copisteria import front
    L = rd.layout
    oldbars = [list(st.bars) for st in L.staves]
    oldboxes = {i: L.syms[i].box for bs in oldbars for i in bs}
    oldtok = copy.deepcopy(rd.tok)
    gray = front.ink_mask(np.asarray(image.convert('L')))
    for sy in L.systems:
        front._segment(L.syms, L.staves, sy, gray)
        sy.columns = [list(range(len(L.staves[k].bars))) for k in sy.staves]
    for k, st in enumerate(L.staves):
        for j, i in enumerate(st.bars):
            b = L.syms[i].box
            old = max(oldbars[k], key=lambda z: min(oldboxes[z][2], b[2])-max(oldboxes[z][0], b[0]))
            rd.tok[i] = copy.deepcopy(oldtok[old])
            L.syms[i].staff, L.syms[i].bar = k, j
            if j:
                for a in ('key', 'time', 'clef'):
                    rd.tok[i][a] = {'v': None, 'p': 1.}
            else:
                from source_systems import _opening_clef
                clef = _opening_clef(L, k)
                if clef:
                    rd.tok[i]['clef'] = {'v': clef[5:], 'p': 1., 'source_opening_clef': True}
        for s in L.syms:
            if s.staff == k and s.fam != 'measure':
                s.bar = min(range(len(st.bars)), key=lambda j: max(
                    L.syms[st.bars[j]].box[0]-s.cx, s.cx-L.syms[st.bars[j]].box[2], 0))
    return {'old_bar_counts': [len(v) for v in oldbars],
            'new_bar_counts': [len(st.bars) for st in L.staves]}


def source_meter(rd, fallback):
    votes = [s.cls[len('meterSig_'):].replace('_', '/') for s in rd.layout.syms
             if s.cls.startswith('meterSig_') and s.cls != 'meterSig_x' and s.p >= .8]
    return votes[0] if len(votes) >= 2 and len(set(votes)) == 1 else fallback


def reflow_transform(rd, original_pass, original_layout, decisions):
    """Move selected voices with their physical staff, keeping prior durations.

    Inconsistent systems previously serialized parallel staves sequentially.
    Reflow changes part/column placement, not the notes' values. Inherited cuts
    are kept conservatively, including existing segmentation errors.
    """
    from copisteria import write
    sources = defaultdict(lambda: defaultdict(list))
    lengths = {}
    for measures in original_pass['built']:
        for m, measure in enumerate(measures):
            cut = original_pass['cuts'][m]
            if cut is None:
                continue
            for row in measure['staves']:
                if row is None:
                    continue
                sid = row['staff']
                for voice, events in row['voices'].items():
                    current_bar = row['bar']
                    for event in write._chop(copy.deepcopy(events), cut):
                        if event.si >= 0:
                            current_bar = original_layout.syms[event.si].bar
                        sources[sid, current_bar][voice].append(event)
                        lengths[sid, current_bar] = cut

    def transform(built, opening):
        selected = copy.deepcopy(built)
        cuts = [Fraction(0) for _ in range(max((len(p) for p in selected), default=0))]
        for measures in selected:
            for m, measure in enumerate(measures):
                for row in measure['staves']:
                    if row is None:
                        continue
                    sid, j = row['staff'], row['bar']
                    st = rd.layout.staves[sid]
                    sy = rd.layout.systems[st.system]
                    cols = sy.columns[sy.staves.index(sid)]
                    merged = [z for z, col in enumerate(cols) if col == cols[j]]
                    voices = defaultdict(list)
                    length = Fraction(0)
                    for z in merged:
                        for voice, events in sources[sid, z].items():
                            voices[voice].extend(copy.deepcopy(events))
                        length += lengths.get((sid, z), Fraction(0))
                    # Refresh pitch only under the source staff's actual clef/key.
                    pitched = {}
                    for z in merged:
                        ev, _, _ = write._events(rd, sid, z, row['state']['clef'], row['state']['key'], [])
                        pitched.update({e.si: e for e in ev if e.kind == 'note'})
                    for events in voices.values():
                        for e in events:
                            if e.kind == 'note' and e.si in pitched:
                                p = pitched[e.si]
                                if (e.step, e.octave, e.alter) != (p.step, p.octave, p.alter):
                                    decisions.append({'action': 'source_staff_pitch', 'sym_id': e.si,
                                        'from': [e.step, e.octave, e.alter], 'to': [p.step, p.octave, p.alter],
                                        'clef': row['state']['clef'], 'key': row['state']['key']})
                                    e.step, e.octave, e.alter = p.step, p.octave, p.alter
                    row['voices'] = dict(voices)
                    cuts[m] = max(cuts[m], length)
        return selected, [c or original_pass['cuts'][0] for c in cuts]
    return transform
