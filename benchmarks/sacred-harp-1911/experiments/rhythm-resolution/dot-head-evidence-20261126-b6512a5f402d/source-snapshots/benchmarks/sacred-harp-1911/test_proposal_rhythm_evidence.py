from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from proposal_rhythm_evidence import detached_dot_evidence


def blank():
    return Image.new("L", (140, 100), 255)


def test_synthetic_detached_dot_is_found():
    im = blank(); d = ImageDraw.Draw(im)
    d.ellipse((48, 43, 62, 57), fill=0)
    d.ellipse((70, 47, 73, 50), fill=0)
    out = detached_dot_evidence(im, (48, 43, 63, 58), 14)
    assert out["present"] is True
    assert out["components"][0]["compact_candidate"] is True


def test_staff_line_and_neighboring_stem_are_not_dots():
    im = blank(); d = ImageDraw.Draw(im)
    d.ellipse((48, 43, 62, 57), fill=0)
    for y in (24, 38, 52, 66, 80):
        d.line((5, y, 135, y), fill=0, width=1)
    # A vertical stroke at the next symbol's location is outside the dot-size box.
    d.line((77, 36, 77, 48), fill=0, width=2)
    out = detached_dot_evidence(im, (48, 43, 63, 58), 14)
    assert out["present"] is False


def test_dot_on_staff_line_survives_line_suppression():
    im = blank(); d = ImageDraw.Draw(im)
    d.ellipse((48, 43, 62, 57), fill=0)
    for y in (24, 38, 52, 66, 80):
        d.line((5, y, 135, y), fill=0, width=1)
    d.ellipse((70, 50, 73, 53), fill=0)  # centered on the y=52 staff line
    out = detached_dot_evidence(im, (48, 43, 63, 58), 14)
    assert out["present"] is True
    assert out["staff_rows"]


@pytest.mark.parametrize("case,box,expected", [
    ("M055", (2721.7, 661.7, 2754.2, 691.1), True),
    ("M056", (3609.1, 1019.8, 3641.3, 1052.7), False),
])
def test_greenland_source_controls(case, box, expected):
    root = Path(__file__).parent
    path = root / "sources" / "1911-Origin-JPK-0316.jpg"
    if not path.exists():
        pytest.skip("cached Greenland source scan unavailable")
    out = detached_dot_evidence(Image.open(path), box, 30.625)
    assert out["present"] is expected, (case, out)


def test_clipped_neighbor_head_is_not_a_detached_dot():
    im = blank(); d = ImageDraw.Draw(im)
    d.rectangle((48, 43, 62, 57), fill=0)
    d.ellipse((70, 43, 85, 57), fill=0)
    assert not detached_dot_evidence(im, (48, 43, 63, 58), 14)['present']
