#!/usr/bin/env python3
"""Combine explicit visual reviews with the preserved original twenty samples."""
import json
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def build(primary_only=False):
    manifest = json.loads((ROOT / "diagnostics/manifest-20.json").read_text())
    candidates = {r["key"]: r for r in json.loads((ROOT / "candidate_review_inputs.json").read_text())}
    reviews = {}
    supplemental_keys = set()
    for name in ("review_early.json", "review_late.json", "review_supplement.json"):
        if primary_only and name == "review_supplement.json":
            continue
        if (ROOT / name).exists():
            for key, value in json.loads((ROOT / name).read_text()).items():
                if key in reviews:
                    raise ValueError(f"Duplicate visual review: {key}")
                reviews[key] = value
                if name == "review_supplement.json":
                    supplemental_keys.add(key)
    samples = manifest["samples"]
    used = {s["reference_source"] for s in samples}
    excluded = manifest["excluded_candidates"]
    for key, review in sorted(reviews.items(), key=lambda item: (item[0] in supplemental_keys, item[0])):
        candidate = candidates[key]
        if not review["accepted"]:
            excluded.append({"candidate_key": key, "scan_id": candidate["scan_id"],
                             "title": candidate["ocr_title"], "reason": review["reason"]})
            continue
        refs = candidate["references"]
        filename = review.get("chosen_reference")
        if filename:
            ref = next(r for r in refs if r["filename"] == filename)
        elif len(refs) == 1:
            ref = refs[0]
        else:
            raise ValueError(f"Ambiguous reference needs explicit choice: {key}")
        if ref["path"] in used:
            excluded.append({"candidate_key": key, "title": candidate["ocr_title"],
                             "reason": "Duplicate reference tune already in sample; not counted twice."})
            continue
        if len(samples) >= 100:
            continue
        used.add(ref["path"])
        scan = candidate["scan_id"]
        title = re.sub(r"([’'])([A-Z])\b", lambda m: m[1] + m[2].lower(), ref["title"].title())
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip('-')
        ident = f"1911-s{scan}-{slug}"
        crop = review.get("crop", candidate["suggested_crop"])
        if crop == [0, 0, candidate["width"], candidate["height"]]:
            crop = None
        source = f"sources/1911-Origin-JPK-{scan}.jpg"
        samples.append({"id": ident, "title": title,
                        "printed_page_1911": review["printed_page"], "reference_page_2025": ref["page"],
                        "scan_id": scan, "source": source,
                        "source_url": f"https://iip.readux.io/iiif/2/1911-Origin-JPK-{scan}.tiff/full/full/0/default.jpg",
                        "input": f"inputs/{ident}.png" if crop else source, "crop": crop,
                        "expected_staves": review["expected_staves"], "expected_systems": review["expected_systems"],
                        "reference_source": ref["path"], "reference": "reference/" + ref["filename"],
                        "notes": review["reason"], "candidate_key": key,
                        "reference_preflight_parts": ref["parts_count"],
                        "reference_preflight_key": ref["first_key"]})
    manifest["description"] = (f"{len(samples)} unique songs from {len(set(s['source'] for s in samples))} scan pages; "
                               "original 20 retained; expansion uses evenly spaced scan candidates across the 1911 volume "
                               "plus documented supplements, with visual title/boundary/key/part-count screening and a final source audit.")
    manifest["selection"] = {"original_sample_size": 20, "expansion_candidate_scans": "48 through 548 inclusive, step 4",
                             "supplement_candidate_scans": "50 through 206 inclusive, step 4",
                             "review_files": [name for name in ("review_early.json", "review_late.json", "review_supplement.json")
                                              if (ROOT / name).exists()],
                             "selection_note": "Accept primary systematic scan candidates across volume first, then fill remaining slots from supplementary candidates in scan order. Final source audit removed incompatible/incomplete pairings after initial inference, retaining their results as diagnostics; no selection favoring better recognition scores."}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Manifest: {len(samples)} samples; {len(excluded)} exclusions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-only", action="store_true")
    build(parser.parse_args().primary_only)
