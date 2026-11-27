import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path
import json

from glyph_verifier import verify_head


def blank():
    return Image.new("L", (120, 100), 255)


def notehead_with_stem(direction="up", broken=False):
    im = blank()
    d = ImageDraw.Draw(im)
    # Staff space is 10; head box is approximately one staff space square.
    d.ellipse((49, 44, 61, 56), fill=0)
    if direction == "up":
        d.line((59, 44, 59, 25), fill=0, width=2)
        if broken:
            d.rectangle((58, 33, 60, 35), fill=255)
    else:
        d.line((51, 56, 51, 75), fill=0, width=2)
    return im


def test_detects_real_stem_and_reports_direction():
    out = verify_head(notehead_with_stem(), (49, 44, 62, 57), 10)
    assert out["stem_found"] is True
    assert out["direction"] == "up"
    assert out["stem_x"] is not None
    assert out["stem_score"] > 0


def test_abstains_on_staff_lines_and_tall_half_rest_like_box():
    im = blank()
    d = ImageDraw.Draw(im)
    for y in (30, 40, 50, 60, 70):
        d.line((10, y, 110, y), fill=0, width=1)
    # No vertical mark at this head-sized region.
    out = verify_head(im, (49, 44, 62, 57), 10)
    assert out["stem_found"] is False

    # A generic tall rest glyph is rejected before its vertical stroke is read.
    d.rectangle((54, 25, 57, 75), fill=0)
    rest = verify_head(im, (50, 25, 62, 75), 10)
    assert rest["stem_found"] is False
    assert rest["reason"] == "box_not_head_like"


def test_ignores_barline_at_candidate_edge():
    im = notehead_with_stem()
    ImageDraw.Draw(im).line((61, 20, 61, 80), fill=0, width=2)
    out = verify_head(im, (49, 44, 62, 57), 10, bar_box=(60, 19, 63, 81))
    assert out["stem_found"] is False


def test_tolerates_a_small_scan_break_in_stem():
    out = verify_head(notehead_with_stem(broken=True), (49, 44, 62, 57), 10)
    assert out["stem_found"] is True
    assert out["direction"] == "up"


def test_rejects_nearby_stem_without_head_ink():
    im = blank()
    d = ImageDraw.Draw(im)
    for y in (30, 40, 50, 60, 70):
        d.line((10, y, 110, y), fill=0, width=1)
    # A neighboring note's stem reaches the candidate box, but the box itself
    # contains only staff lines.
    d.line((59, 22, 59, 44), fill=0, width=2)
    out = verify_head(im, (49, 44, 62, 57), 10)
    assert out["stem_found"] is False
    assert out["reason"] == "no_head_ink"


def test_accepts_hollow_head_outline_with_stem():
    im = blank()
    d = ImageDraw.Draw(im)
    d.ellipse((49, 44, 61, 56), outline=0, width=1)
    d.line((59, 44, 59, 25), fill=0, width=2)
    out = verify_head(im, (49, 44, 62, 57), 10)
    assert out["stem_found"] is True
    assert out["direction"] == "up"


def test_accepts_filled_square_head_with_stem():
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle((49, 44, 61, 56), fill=0)
    d.line((59, 44, 59, 25), fill=0, width=2)
    out = verify_head(im, (49, 44, 62, 57), 10)
    assert out["stem_found"] is True
    assert out["head_ink_fraction"] > 0
    assert out["supported_quadrants"] == 4


def test_neighboring_vertical_stems_do_not_turn_staff_rows_into_masking_evidence():
    im = blank()
    d = ImageDraw.Draw(im)
    for y in (30, 40, 50, 60, 70):
        d.line((10, y, 110, y), fill=0, width=1)
    # Filled head with separate neighboring stems entering both 2-space
    # inspection strips. The stems have enough pixels to fool the old test.
    d.rectangle((49, 44, 61, 56), fill=0)
    d.line((47, 25, 47, 75), fill=0, width=2)
    d.line((65, 25, 65, 75), fill=0, width=2)
    d.line((59, 44, 59, 25), fill=0, width=2)
    out = verify_head(im, (49, 44, 62, 57), 10)
    assert out["stem_found"] is True
    assert out["head_ink_fraction"] > .5
    assert out["supported_quadrants"] == 4


def test_neighboring_filled_heads_do_not_mask_a_thick_horizontal_band():
    im = blank()
    d = ImageDraw.Draw(im)
    for y in (30, 40, 50, 60, 70):
        d.line((10, y, 110, y), fill=0, width=1)
    d.rectangle((49, 44, 61, 56), fill=0)
    # Broad neighboring glyph ink fills both exterior strips for many rows.
    d.rectangle((34, 39, 48, 61), fill=0)
    d.rectangle((63, 39, 77, 61), fill=0)
    d.line((59, 44, 59, 25), fill=0, width=2)
    out = verify_head(im, (49, 44, 62, 57), 10)
    assert out["stem_found"] is True
    assert out["head_ink_fraction"] > .5
    assert out["supported_quadrants"] == 4


def test_rejects_sloped_staff_line_without_two_dimensional_head_ink():
    im = blank()
    # A sloped staff stroke crosses the box and both exterior strips, so its
    # pixels cannot be removed by requiring same-row alignment outside it.
    ImageDraw.Draw(im).line((34, 29, 78, 73), fill=0, width=2)
    out = verify_head(im, (49, 44, 62, 57), 10)
    assert out["stem_found"] is False
    assert out["reason"] == "no_head_ink"


def test_source_boxes_containing_only_staff_lines_do_not_verify_as_heads():
    root = Path(__file__).parent
    cases = (
        ("Winter sym313", "1911-Origin-JPK-0048.jpg", "1911-s0048-winter", 313),
        ("Ocean sym706", "1911-Origin-JPK-0232.jpg", "1911-s0232-ocean", 706),
    )
    for label, source_name, trace_name, sym_id in cases:
        image = Image.open(root / "sources" / source_name)
        trace = json.loads((root / "reader-gallery" / "transcriptions" /
                            f"{trace_name}.trace.json").read_text())
        sym = next(s for s in trace["syms"] if s["i"] == sym_id)
        staff = trace["staves"][sym["staff"]]
        bar_id = staff["bars"][sym["bar"]]
        bar = next(s for s in trace["syms"] if s["i"] == bar_id)
        out = verify_head(image, sym["box"], staff["sp"], bar_box=bar["box"])
        assert out["stem_found"] is False, label
        assert out["reason"] == "no_head_ink", label


def test_confirmed_miss_source_heads_retain_ink_and_verify_stems():
    # Coordinates and song identity come from diagnostics/miss-trace/
    # confirmed-misses.json; the scan path comes from reader-gallery/results.json.
    root = Path(__file__).parent
    source = root / "sources" / "1911-Origin-JPK-0224.jpg"
    if not source.exists():
        import pytest
        pytest.skip("cached Repentance source scan is unavailable")
    image = Image.open(source)
    trace = json.loads((root / "reader-gallery" / "transcriptions" /
                        "1911-s0224-repentance.trace.json").read_text())
    for case_id, sym_id in (("M004", 307), ("M011", 740), ("M015", 288)):
        sym = next(s for s in trace["syms"] if s["i"] == sym_id)
        staff = trace["staves"][sym["staff"]]
        bar_id = staff["bars"][sym["bar"]]
        bar = next(s for s in trace["syms"] if s["i"] == bar_id)
        out = verify_head(image, sym["box"], staff["sp"], bar_box=bar["box"])
        assert out["head_ink_fraction"] > .5, case_id
        assert out["supported_quadrants"] == 4, case_id
        assert out["stem_found"] is True, case_id


def test_confirmed_clamanda_half_rests_do_not_verify_as_stems():
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
        out = verify_head(image, box, 31)
        assert out["stem_found"] is False, case_id


def test_adapts_to_faint_stem_on_cream_paper():
    im = Image.new("L", (120, 100), 224)
    d = ImageDraw.Draw(im)
    d.ellipse((49, 44, 61, 56), fill=25)
    d.line((59, 44, 59, 25), fill=174, width=2)
    out = verify_head(im, (49, 44, 62, 57), 10)
    assert out["stem_found"] is True
    assert out["ink_threshold"] > 150


def test_faint_stafflines_and_stroke_on_cream_paper_still_abstain_without_head():
    im = Image.new("L", (120, 100), 224)
    d = ImageDraw.Draw(im)
    for y in (30, 40, 50, 60, 70):
        d.line((10, y, 110, y), fill=174, width=1)
    d.line((59, 22, 59, 44), fill=174, width=2)
    out = verify_head(im, (49, 44, 62, 57), 10)
    assert out["stem_found"] is False
    assert out["reason"] == "no_head_ink"

