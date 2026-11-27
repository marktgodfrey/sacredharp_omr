import numpy as np
from PIL import Image, ImageDraw

from notehead_normalization import normalize_verified_heads


BOX = (49, 44, 62, 57)
EVIDENCE = {"stem_found": True, "stem_x": 59, "direction": "up"}


def image_with_head(style):
    im = Image.new("L", (120, 100), 245)
    d = ImageDraw.Draw(im)
    if style == "hollow":
        d.ellipse((49, 44, 61, 56), outline=20, width=1)
    else:
        d.rectangle((49, 44, 61, 56), fill=20)
    d.line((59, 25, 59, 45), fill=20, width=2)
    d.line((10, 50, 110, 50), fill=30, width=1)
    return im


def one_head(box=BOX, evidence=EVIDENCE):
    return [{"box": box, "staff_space": 10, "evidence": evidence}]


def test_source_and_pixels_outside_head_box_are_unchanged():
    source = image_with_head("solid")
    before = np.asarray(source).copy()
    result, audit = normalize_verified_heads(source, (0, 0), one_head())
    assert audit["normalized"] == 1
    assert np.array_equal(np.asarray(source), before)
    after = np.asarray(result)
    outside = np.ones(before.shape, dtype=bool)
    outside[44:57, 49:62] = False
    assert np.array_equal(after[outside], before[outside])


def test_hollow_head_stays_hollow_and_solid_head_stays_solid():
    hollow, hollow_audit = normalize_verified_heads(image_with_head("hollow"), (0, 0), one_head())
    solid, solid_audit = normalize_verified_heads(image_with_head("solid"), (0, 0), one_head())
    assert hollow_audit["items"][0]["style"] == "hollow"
    # Check an unoccupied center pixel away from the preserved staff row.
    assert np.asarray(hollow)[49, 55] > 200
    assert solid_audit["items"][0]["style"] == "solid"
    assert np.asarray(solid)[50, 55] < 100


def test_unverified_and_outside_crop_heads_are_ignored():
    source = image_with_head("solid")
    unverified = {"stem_found": False}
    result, audit = normalize_verified_heads(source, (0, 0), one_head(evidence=unverified))
    assert audit["items"][0]["reason"] == "unverified_stem"
    assert np.array_equal(np.asarray(result), np.asarray(source))

    outside_box = (149, 144, 162, 157)
    result, audit = normalize_verified_heads(source, (0, 0), one_head(box=outside_box))
    assert audit["items"][0]["reason"] == "head_outside_crop"
    assert np.array_equal(np.asarray(result), np.asarray(source))


def test_isolated_marks_beside_head_do_not_preserve_a_false_staff_row():
    source = Image.new("L", (120, 100), 245)
    d = ImageDraw.Draw(source)
    d.ellipse((49, 44, 61, 56), outline=20, width=1)
    d.line((59, 25, 59, 45), fill=20, width=2)
    # An interior blemish row plus isolated exterior marks should not count as
    # a continuous staff rule extending beyond both sides of the head.
    d.line((49, 47, 61, 47), fill=20, width=1)
    d.point((35, 47), fill=20)
    d.point((77, 47), fill=20)
    result, audit = normalize_verified_heads(source, (0, 0), one_head())
    assert audit["normalized"] == 1
    assert np.asarray(result)[47, 49] > 200
