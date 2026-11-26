#!/usr/bin/env python3
"""Download public IIIF metadata/rasters and propose title matches for review.

Proposals never enter the scored manifest automatically. Staff counts, complete
song boundaries, duplicate titles and reference compatibility need inspection.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import html
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parent


def fetch(kind, scan):
    ident = f"{scan:04d}"
    if kind == "ocr":
        dest = ROOT / f"sources/ocr/{ident}.json"
        url = f"https://library.soundingspirit.org/iiif/v3/1911-Origin-JPK/annotations/1911-Origin-JPK-{ident}.tiff/ocr"
    else:
        dest = ROOT / f"sources/1911-Origin-JPK-{ident}.jpg"
        url = f"https://iip.readux.io/iiif/2/1911-Origin-JPK-{ident}.tiff/full/full/0/default.jpg"
    if dest.exists():
        return {"scan": ident, "status": "cached", "kind": kind}
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "SacredHarpLocalBenchmark/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        if kind == "ocr":
            json.loads(data)
        temp = dest.with_suffix(dest.suffix + ".partial")
        temp.write_bytes(data)
        temp.replace(dest)
        return {"scan": ident, "status": "downloaded", "bytes": len(data), "kind": kind}
    except Exception as exc:
        return {"scan": ident, "status": "failed", "error": str(exc), "kind": kind}


def normalize(title):
    value = re.sub(r"[^a-z0-9]", "", title.lower()).replace("saviour", "savior")
    return value[3:] if value.startswith("the") else value


def headings(path, width):
    raw = json.loads(path.read_text())
    words = []
    for item in raw["items"]:
        body = item.get("body", [])
        body = body if isinstance(body, list) else [body]
        value = " ".join(html.unescape(re.sub(r"<[^>]+>", "", b.get("value", ""))) for b in body)
        selector = item.get("target", {}).get("selector", {}).get("value", "")
        match = re.search(r"(?:pixel:)?(\d+),(\d+),(\d+),(\d+)", selector)
        if not match:
            continue
        x, y, w, h = map(int, match.groups())
        letters = ''.join(c for c in value if c.isalpha())
        if h >= 32 and letters and letters.upper() == letters and 0.18 * width < x < 0.90 * width:
            words.append({"text": value, "box": [x, y, w, h]})
    lines = []
    for word in sorted(words, key=lambda a: (a["box"][1], a["box"][0])):
        x, y, w, h = word["box"]
        cy = y + h/2
        group = next((line for line in lines if abs(line["cy"] - cy) < .45 * max(h, line["h"])), None)
        if group is None:
            group = {"cy": cy, "h": h, "words": []}
            lines.append(group)
        group["words"].append(word)
    for line in lines:
        line["words"].sort(key=lambda a: a["box"][0])
        line["text"] = ' '.join(w["text"] for w in line["words"])
    return lines


def propose():
    raw_catalog = json.loads((ROOT / "reference_catalog.json").read_text())
    catalog = raw_catalog if isinstance(raw_catalog, list) else raw_catalog["files"]
    lookup = {}
    for entry in catalog:
        title = entry.get("filename_title", entry.get("title", ""))
        lookup.setdefault(normalize(title), []).append(entry)
    volume = json.loads((ROOT / "sources/manifest.json").read_text())
    proposals = []
    for p in sorted((ROOT / "sources/ocr").glob("*.json")):
        scan = int(p.stem)
        canvas = volume["items"][scan-1]
        for line in headings(p, canvas["width"]):
            words = line["words"]
            matches = []
            for a in range(len(words)):
                for b in range(a+1, min(a+9, len(words)+1)):
                    title = ' '.join(w["text"] for w in words[a:b])
                    key = normalize(title)
                    if len(key) < 4 or key not in lookup:
                        continue
                    box = [min(w["box"][0] for w in words[a:b]), min(w["box"][1] for w in words[a:b]),
                           max(w["box"][0]+w["box"][2] for w in words[a:b]),
                           max(w["box"][1]+w["box"][3] for w in words[a:b])]
                    if not (0.30 * canvas["width"] < (box[0] + box[2])/2 < 0.70 * canvas["width"]):
                        continue
                    if box[3] - box[1] < 45:
                        continue
                    matches.append({"ocr_title": title, "normalized_title": key, "heading_box": box,
                                    "references": lookup[key]})
            # Prefer the longest matching name on a heading line; keep ambiguity explicit.
            if matches:
                best = max(matches, key=lambda a: len(a["normalized_title"]))
                proposals.append({"scan_id": p.stem, "printed_page_estimate": scan-10,
                                  "width": canvas["width"], "height": canvas["height"],
                                  "ocr_line": line["text"], **best})
    (ROOT / "candidate_titles.json").write_text(json.dumps(proposals, indent=2) + "\n")
    print(f"Proposed {len(proposals)} heading matches on {len(set(s['scan_id'] for s in proposals))} pages", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("ocr", "image"))
    parser.add_argument("--scans", help="comma-separated scan ordinals")
    parser.add_argument("--propose", action="store_true")
    args = parser.parse_args()
    if args.kind:
        scans = [int(n) for n in args.scans.split(',')]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(lambda n: fetch(args.kind, n), scans):
                print(json.dumps(result), flush=True)
    if args.propose:
        propose()


if __name__ == "__main__":
    main()
