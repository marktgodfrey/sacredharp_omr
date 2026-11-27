from pathlib import Path
import sys

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from head_morphology import head_morphology


BOX = (20, 20, 60, 60)


def test_filled_square_is_not_hollow():
    image = Image.new("L", (80, 80), 255)
    ImageDraw.Draw(image).rectangle(BOX, fill=0)

    result = head_morphology(image, BOX, threshold=180)

    assert result["central_ink_fraction"] == 1.0
    assert not result["hollow_square"]
    assert result["largest_hole_pixels"] == 0
    assert not result["hollow_head"]


def test_hollow_outlined_square_has_four_edge_coverage():
    image = Image.new("L", (80, 80), 255)
    ImageDraw.Draw(image).rectangle(BOX, outline=0, width=2)

    result = head_morphology(image, BOX, threshold=180)

    assert result["central_ink_fraction"] <= .25
    assert all(value >= .7 for value in result["edge_coverage"].values())
    assert result["hollow_square"]
    assert result["largest_hole_pixels"] >= .05 * (BOX[2] - BOX[0]) * (BOX[3] - BOX[1])
    assert result["hollow_head"]


def test_staff_lines_and_unrelated_vertical_stroke_do_not_form_hollow_square():
    staff = Image.new("L", (80, 80), 255)
    draw = ImageDraw.Draw(staff)
    for y in (20, 30, 40, 50, 60):
        draw.line((5, y, 75, y), fill=0, width=1)
    staff_result = head_morphology(staff, BOX, threshold=180)
    assert not staff_result["hollow_square"]
    assert not staff_result["hollow_head"]

    vertical = Image.new("L", (80, 80), 255)
    ImageDraw.Draw(vertical).line((21, 5, 21, 75), fill=0, width=2)
    vertical_result = head_morphology(vertical, BOX, threshold=180)
    assert not vertical_result["hollow_square"]
    assert not vertical_result["hollow_head"]


def test_closed_counter_outside_candidate_is_not_its_head_hole():
    image = Image.new('L', (70, 70), 255)
    ImageDraw.Draw(image).rectangle((38, 24, 42, 36), outline=0, width=1)
    result = head_morphology(image, (20, 20, 40, 40), threshold=180)
    assert result['largest_hole_pixels'] == 0
    assert not result['hollow_head']


@pytest.mark.parametrize("threshold", [177, 180])
def test_m095_saved_source_reports_measurements_at_recorded_thresholds(threshold):
    source = ROOT / "sources" / "1911-Origin-JPK-0308.jpg"
    if not source.exists():
        pytest.skip("cached M095 source scan is unavailable")
    result = head_morphology(Image.open(source), (1604.1, 946.8, 1638.7, 985.8), threshold)
    assert result["central_ink_fraction"] == pytest.approx(.3)
    assert all(value >= .7 for value in result["edge_coverage"].values())
    # The oversized half-note box has a stem stub that pushes the central
    # ink fraction above the strict square threshold, but leaves an enclosed
    # white head hole. Keep the two measurements distinct.
    assert not result["hollow_square"]
    assert result["largest_hole_pixels"] >= .05 * (1638.7 - 1604.1) * (985.8 - 946.8)
    assert result["hollow_head"]
