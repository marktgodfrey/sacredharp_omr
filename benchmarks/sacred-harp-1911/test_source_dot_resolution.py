"""Source pixel checks for inherited and repeat-column dots."""
import json
from types import SimpleNamespace as NS

import numpy as np
from PIL import Image,ImageDraw

from run_local_recovery import ROOT, samples
from replay_writer_trace import _reading
from source_saved_events import source_saved_events
from source_rhythm_resolution import resolved_duration_options,_repeat_dot_column
from source_dot_evidence import diffuse_dot_mark,component_is_repeat


PREDICTIONS = ROOT / 'experiments/rhythm-resolution/final-a17498fc863d/predictions'


def _options(song_id):
    sample = next(s for s in samples() if s['id'] == song_id)
    image = Image.open(ROOT / sample['input']).convert('L')
    trace = json.loads((PREDICTIONS / f"{song_id}.trace.json").read_text())
    rd = _reading(trace, image)
    events, _ = source_saved_events(trace, (PREDICTIONS / f"{song_id}.musicxml").read_text())
    return resolved_duration_options(rd, np.asarray(image), events)


def _dot_values(options, sid):
    return {o['dots'] for o in options[sid]['options']}


def test_visible_empty_region_clears_inherited_dots_and_repeat_columns_veto_notes():
    done = _options('1911-s0098-done-with-the-world')
    assert _dot_values(done, 397) == {0}
    assert done[397]['evidence']['source_dot_resolution']['force_no_dot']

    elder = _options('1911-s0464-elder')
    assert _dot_values(elder, 7) == {0}
    # The separate, compact printed dot on the half at 361 remains.
    assert _dot_values(elder, 361) == {1}

    midnight = _options('1911-s0124-the-midnight-cry')
    assert _dot_values(midnight, 102) == {0}
    assert midnight[102]['evidence']['source_dot_resolution']['separate_vertical_repeat_dot_column']


def test_real_dot_and_repeat_controls_are_preserved():
    greenland = _options('1911-s0316-greenland')
    # M055 is the source-bound hollow head with a genuine augmentation dot.
    assert _dot_values(greenland, 829) == {1}

    duane = _options('1911-holdout-s0174-duane-street')
    # Existing source controls include genuine augmentation dots and ordinary
    # notes adjacent to repeat columns.
    assert _dot_values(duane, 247) == {0}
    assert _dot_values(duane, 219) == {0}


def test_two_dot_repeat_requires_middle_spaces_and_boundary():
    image=Image.new('L',(140,140),255);d=ImageDraw.Draw(image)
    for y in (50,70):d.ellipse((61,y-4,69,y+4),fill=0)
    sym=NS(box=(20,40,40,60),staff=0,bar=0)
    staff=NS(sp=20,y0=20,y1=100)
    rd=NS(layout=NS(syms=[],staves=[staff]))
    assert _repeat_dot_column(rd,sym,20,np.asarray(image)) is None
    rd.layout.syms.append(NS(i=0,cls='barLine_single',p=1,staff=0,bar=0,box=(78,20,82,100)))
    repeat=_repeat_dot_column(rd,sym,20,np.asarray(image))
    assert repeat and len(repeat['pixel_components'])==2
    # A separate true augmentation dot to the left of a repeat column survives.
    assert not component_is_repeat({'box':(44,44,52,52)},repeat,rd,20)


def test_diffuse_mark_exclusion_preserves_compact_and_dark_marks():
    staff=NS(sp=20,y0=10,y1=90);box=(20,40,40,60)
    image=Image.new('L',(120,120),230);d=ImageDraw.Draw(image)
    d.ellipse(box,outline=30,width=4)
    d.ellipse((42,34,57,47),fill=175)
    assert diffuse_dot_mark(np.asarray(image),box,staff)['diffuse_non_dot_mark']
    d.rectangle((42,33,58,50),fill=230);d.ellipse((45,42,51,48),fill=175)
    assert not diffuse_dot_mark(np.asarray(image),box,staff)['diffuse_non_dot_mark']
    d.ellipse((42,34,57,47),fill=30)
    assert not diffuse_dot_mark(np.asarray(image),box,staff)['diffuse_non_dot_mark']


def test_three_augmentation_dots_on_chord_are_not_a_repeat_column():
    image=Image.new('L',(140,160),255);d=ImageDraw.Draw(image)
    for y in (30,50,70):d.ellipse((61,y-4,69,y+4),fill=0)
    sym=NS(box=(20,40,40,60),staff=0,bar=0)
    heads=[NS(i=i,cls='note_quarter',p=.9,staff=0,bar=0,box=(38,y-8,56,y+8),cx=47,cy=y)
           for i,y in enumerate((30,50,70))]
    rd=NS(layout=NS(syms=heads,staves=[NS(sp=20,y0=20,y1=100)]))
    assert _repeat_dot_column(rd,sym,20,np.asarray(image)) is None
