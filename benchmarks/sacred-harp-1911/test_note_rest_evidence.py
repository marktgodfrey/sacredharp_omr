from pathlib import Path

from PIL import Image, ImageDraw

from note_rest_evidence import short_stem_evidence


def canvas():
    return Image.new("L", (120, 100), 255)


def head_with_short_stem(hollow=False, direction="up", broken=False):
    im = canvas()
    d = ImageDraw.Draw(im)
    if hollow:
        d.ellipse((49, 44, 61, 56), outline=0, width=1)
    else:
        d.ellipse((49, 44, 61, 56), fill=0)
    if direction == "up":
        d.line((59, 44, 59, 35), fill=0, width=2)
        if broken:
            d.rectangle((58, 39, 60, 39), fill=255)
    else:
        d.line((51, 56, 51, 65), fill=0, width=2)
        if broken:
            d.rectangle((50, 61, 52, 61), fill=255)
    return im


def test_accepts_short_stems_on_filled_and_hollow_heads():
    for hollow in (False, True):
        for direction, expected in (("up", "up"), ("down", "down")):
            out = short_stem_evidence(head_with_short_stem(hollow, direction),
                                      (49, 44, 62, 57), 10)
            assert out["found"] is True
            assert out["direction"] == expected
            assert out["stem_x"] in range(49, 62)
            assert out["score"] >= .7


def test_tolerates_one_small_scan_gap_in_short_stem():
    out = short_stem_evidence(head_with_short_stem(broken=True), (49, 44, 62, 57), 10)
    assert out["found"] is True


def test_rejects_staff_lines_without_head_and_stem_unrelated_to_head():
    im = canvas()
    d = ImageDraw.Draw(im)
    for y in (30, 40, 50, 60, 70):
        d.line((10, y, 110, y), fill=0, width=1)
    d.line((59, 31, 59, 42), fill=0, width=2)
    out = short_stem_evidence(im, (49, 44, 62, 57), 10)
    assert out["found"] is False
    assert out["reason"] == "no_head_ink"

    im = canvas()
    d = ImageDraw.Draw(im)
    d.ellipse((49, 44, 61, 56), fill=0)
    d.line((65, 35, 65, 47), fill=0, width=2)
    out = short_stem_evidence(im, (49, 44, 62, 57), 10)
    assert out["found"] is False


def test_excludes_supplied_barline_and_tall_structural_strokes():
    im = head_with_short_stem()
    d = ImageDraw.Draw(im)
    d.line((61, 20, 61, 80), fill=0, width=2)
    out = short_stem_evidence(im, (49, 44, 62, 57), 10,
                              bar_box=(60, 19, 63, 81))
    assert out["found"] is False


def test_confirmed_clamanda_half_rest_boxes_abstain():
    root = Path(__file__).parent
    source = root / "sources" / "1911-Origin-JPK-0052.jpg"
    if not source.exists():
        import pytest
        pytest.skip("cached Clamanda source scan is unavailable")
    image = Image.open(source)
    boxes = (
        ("ID117", (620.5, 592.0, 662.4, 608.6)),
        ("ID19", (619.8, 907.3, 662.4, 924.2)),
        ("ID70", (620.3, 1133.6, 662.4, 1149.2)),
        ("ID139", (619.6, 1449.0, 662.5, 1465.1)),
    )
    for case_id, box in boxes:
        out = short_stem_evidence(image, box, 31)
        assert out["found"] is False, case_id

