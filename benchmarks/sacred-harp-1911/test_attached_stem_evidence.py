import json
from pathlib import Path

from PIL import Image, ImageDraw

from attached_stem_evidence import attached_stem_evidence


def _head(stem=None, hollow=False, detached=False):
    image = Image.new("L", (80, 80), 255)
    draw = ImageDraw.Draw(image)
    draw.ellipse((30, 30, 40, 40), fill=255 if hollow else 0, outline=0, width=1)
    if stem == "up":
        draw.line((39, 20 if detached else 30, 39, 12), fill=0, width=1)
    elif stem == "down":
        draw.line((31, 40, 31, 58), fill=0, width=1)
    return image


def test_attached_long_stem_is_measured():
    result = attached_stem_evidence(_head("up"), (30, 30, 41, 41), 10)
    assert result["visible"] is True
    assert result["long_stem"] is True
    assert result["max_up_staff_spaces"] >= 1.2


def test_detached_vertical_stroke_does_not_count():
    result = attached_stem_evidence(_head("up", detached=True), (30, 30, 41, 41), 10)
    assert result["visible"] is True
    assert result["max_up_staff_spaces"] < .35
    assert result["long_stem"] is False


def test_hollow_head_without_stem_has_no_continuation():
    result = attached_stem_evidence(_head(hollow=True), (30, 30, 41, 41), 10)
    assert result["visible"] is True
    assert result["short_stub"] is False


def test_attached_short_stub_is_visible_but_not_long_stem():
    image = _head()
    ImageDraw.Draw(image).line((31, 39, 31, 44), fill=0, width=1)
    result = attached_stem_evidence(image, (30, 30, 41, 41), 10)
    assert result["short_stub"] is True
    assert result["long_stem"] is False


def test_cached_source_controls():
    from run_local_recovery import samples

    root = Path(__file__).resolve().parent
    experiment = root / "experiments/source-timing/final-0eaa4b28dd55"
    by_id = {sample["id"]: sample for sample in samples()}
    controls = {
        "1911-Origin-JPK-0050": (398, 402, 431, 472),
        "1911-s0192-newburgh": (727,),
        "1911-holdout-s0130-chambers": (568,),
        "1911-s0308-never-part": (522,),
    }
    for sample_id, indices in controls.items():
        trace = json.loads((experiment / "predictions" / f"{sample_id}.trace.json").read_text())
        image = Image.open(root / by_id[sample_id]["input"]).convert("L")
        for index in indices:
            symbol = trace["syms"][index]
            staff_space = trace["staves"][symbol["staff"]]["sp"]
            evidence = attached_stem_evidence(image, symbol["box"], staff_space)
            if sample_id == "1911-s0308-never-part":
                assert evidence["short_stub"] is True
                assert evidence["long_stem"] is False
            else:
                assert evidence["short_stub"] is False
                assert evidence["long_stem"] is False
