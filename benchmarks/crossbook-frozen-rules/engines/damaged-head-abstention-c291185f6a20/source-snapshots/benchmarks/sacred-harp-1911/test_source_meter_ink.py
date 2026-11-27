import copy
import json

from PIL import Image, ImageDraw

from run_local_recovery import ROOT, samples
from replay_writer_trace import _reading
from source_meter_ink import build_meter_templates, opening_meter_from_ink


def _sample(title):
    return next(s for s in samples() if s["title"] == title)


def _load_reading(sample):
    image = Image.open(ROOT / sample["input"]).convert("L")
    trace = json.loads((ROOT / sample["baseline_trace"]).read_text())
    return image, trace, _reading(trace, image)


def test_duane_street_opening_meter_is_found_without_a_meter_glyph_read():
    all_samples = samples()
    bank, provenance = build_meter_templates(all_samples)
    assert provenance["source_samples"] == 120
    assert {"3/4", "6/8"} <= set(bank)

    sample = _sample("Duane Street")
    image, trace, rd = _load_reading(sample)
    assert not any(s["cls"].startswith("meterSig_") for s in trace["syms"])
    before = copy.deepcopy(rd.tok)
    evidence = opening_meter_from_ink(rd, image, bank)
    assert evidence and evidence["meter"] == "4/4"
    assert evidence["consensus_staff_count"] >= 2
    assert rd.tok == before


def test_repeat_dots_and_notehead_shapes_do_not_create_meter_consensus():
    bank, _ = build_meter_templates(samples())
    sample = _sample("Duane Street")
    image, trace, rd = _load_reading(sample)
    fake_meter_area = image.copy()
    draw = ImageDraw.Draw(fake_meter_area)
    for sid in rd.layout.systems[0].staves:
        staff = rd.layout.staves[sid]
        cy = (staff.y0 + staff.y1) / 2
        x = 650
        # Clear the actual opening region, then place either two repeat dots or
        # a notehead at the same x on every staff, creating a deliberate false cue.
        draw.rectangle((615, staff.y0 - staff.sp / 3, 750, staff.y1 + staff.sp / 3), fill=255)
        if sid % 2:
            rr = max(2, int(round(staff.sp * .07)))
            draw.ellipse((x - rr, cy - .24 * staff.sp - rr, x + rr, cy - .24 * staff.sp + rr), fill=0)
            draw.ellipse((x - rr, cy + .24 * staff.sp - rr, x + rr, cy + .24 * staff.sp + rr), fill=0)
        else:
            draw.ellipse((x - .22 * staff.sp, cy - .10 * staff.sp,
                          x + .22 * staff.sp, cy + .10 * staff.sp), fill=0)
    assert opening_meter_from_ink(rd, fake_meter_area, bank) is None


def test_raw_three_four_and_six_eight_templates_remain_distinguishable():
    bank, _ = build_meter_templates(samples())
    for expected, title in (("3/4", "Prospect"), ("6/8", "The Christian’s Hope")):
        image, _, rd = _load_reading(_sample(title))
        evidence = opening_meter_from_ink(rd, image, bank)
        assert evidence and evidence["meter"] == expected
