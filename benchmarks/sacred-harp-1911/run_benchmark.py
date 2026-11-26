#!/usr/bin/env python3
"""Prepare, run and score the local 1911 Sacred Harp / 2025 comparison.

Run with the copisteria virtualenv. Default operation scores saved predictions;
--prepare copies references and makes the documented crops, --infer runs CoreML.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.metadata
import json
import platform
import shutil
import statistics
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from compare_musicxml import Parsed, compare, parse_score

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1] / "copisteria"
VARIANTS = {"default": "diagnostics/raw-layout", "clean_layout": "predictions"}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(samples):
    from PIL import Image
    for s in samples:
        source, ref = ROOT / s["source"], Path(s["reference_source"])
        if not source.is_file() or not ref.is_file():
            raise FileNotFoundError(f"Required source missing: {source} or {ref}")
        dest = ROOT / s["reference"]
        dest.parent.mkdir(exist_ok=True, parents=True)
        if not dest.exists():
            shutil.copyfile(ref, dest)
        if s.get("crop"):
            target = ROOT / s["input"]
            target.parent.mkdir(exist_ok=True, parents=True)
            with Image.open(source) as im:
                im.crop(tuple(s["crop"])).save(target)


def infer(samples, force):
    from copisteria.coreml_runtime import run
    for variant, folder in VARIANTS.items():
        out = ROOT / folder
        out.mkdir(parents=True, exist_ok=True)
        for s in samples:
            if not force and all((out / (s["id"] + suffix)).exists()
                                 for suffix in (".musicxml", ".report.json", ".html")):
                continue
            print(f"Running {variant}: {s['title']}", flush=True)
            failure_path = out / (s["id"] + ".failure.json")
            started = time.perf_counter()
            try:
                run(ROOT / s["input"], REPO / "out/coreml", out,
                    units="CPU_ONLY", clean_layout=variant == "clean_layout", four_staff=False)
                collect_outputs(s, out)
            except Exception as exc:
                failure = {"variant": variant, "input": s["input"],
                           "traceback": traceback.format_exc(),
                           "error": f"{type(exc).__name__}: {exc}",
                           "elapsed_seconds": time.perf_counter() - started}
                failure_path.write_text(json.dumps(failure, indent=2) + "\n")
                print(f"Failed {variant}: {s['title']}: {failure['error']}", flush=True)
            else:
                failure_path.unlink(missing_ok=True)


def collect_outputs(sample, out):
    """The runtime names files by input stem; the dataset uses stable song IDs."""
    input_stem = Path(sample["input"]).stem
    if input_stem == sample["id"]:
        return
    for suffix in (".musicxml", ".shapes.musicxml", ".report.json", ".html"):
        source = out / (input_stem + suffix)
        if not source.is_file():
            raise FileNotFoundError(f"Runtime output missing: {source}")
        shutil.copyfile(source, out / (sample["id"] + suffix))


def render_references(samples):
    import verovio
    out = ROOT / "reference/previews"
    out.mkdir(exist_ok=True)
    for s in samples:
        tk = verovio.toolkit()
        tk.setOptions({"pageWidth": 2100, "pageHeight": 2970, "scale": 40,
                       "adjustPageHeight": True, "footer": "none", "header": "auto"})
        if not tk.loadData((ROOT / s["reference"]).read_text()):
            raise RuntimeError(f"Cannot render reference {s['title']}")
        svgs = [tk.renderToSVG(i + 1) for i in range(tk.getPageCount())]
        title = html.escape(s["title"])
        doc = ("<!doctype html><meta charset='utf-8'><title>" + title + " · 2025 reference</title>"
               "<style>body{margin:24px auto;max-width:1100px;background:#f6f6f3;font:16px system-ui}"
               "svg{width:100%;height:auto;background:white}</style><h1>" + title + " · 2025 reference</h1>"
               "<p>Direct Verovio engraving of the supplied MusicXML. The original XML is retained unchanged.</p>"
               + ''.join(svgs))
        (out / (s["id"] + ".html")).write_text(doc)


def score_variant(sample, reference, variant, folder, *, root=None):
    root = root or ROOT
    out = root / folder
    p = out / (sample["id"] + ".musicxml")
    failure_path = out / (sample["id"] + ".failure.json")
    if failure_path.is_file():
        failure = json.loads(failure_path.read_text())
        empty = Parsed(lines={}, summaries=[], rests=0, graces=0, measures=0)
        traceback_lines = failure.get("traceback", "").strip().splitlines()
        error = failure.get("error") or (traceback_lines[-1] if traceback_lines else "Inference failed")
        comparison = compare(reference, empty)
        return {
            "prediction": None, "prediction_sha256": None, "viewer": None,
            "failure": str(failure_path.relative_to(root)), "failed": True,
            "failure_error": error,
            "runtime": {"elapsed_seconds": float(failure.get("elapsed_seconds", 0.0)),
                        "staves": 0, "systems": 0, "detector_size": None, "error": error},
            "prediction_structure": [], "layout_matches_expected_counts": False,
            "comparison": comparison,
        }
    if not p.is_file():
        raise FileNotFoundError(f"Missing prediction {p} and failure artifact {failure_path}")
    report_path = p.with_suffix(".report.json")
    if not report_path.is_file():
        raise FileNotFoundError(f"Missing runtime report {report_path} and failure artifact {failure_path}")
    pred = parse_score(p, line_names=[part["line"] for part in reference.summaries])
    runtime = json.loads(report_path.read_text())
    return {
        "prediction": str(p.relative_to(root)), "prediction_sha256": sha(p),
        "viewer": str(p.with_suffix(".html").relative_to(root)), "failed": False,
        "runtime": runtime, "prediction_structure": pred.summaries,
        "layout_matches_expected_counts": runtime["staves"] == sample["expected_staves"]
            and runtime["systems"] == sample["expected_systems"],
        "comparison": compare(reference, pred),
    }


def score(samples):
    rows = []
    for s in samples:
        row = dict(s)
        row["source_sha256"] = sha(ROOT / s["source"])
        row["input_sha256"] = sha(ROOT / s["input"])
        row["reference_sha256"] = sha(ROOT / s["reference"])
        ref = parse_score(ROOT / s["reference"])
        row["reference_structure"] = ref.summaries
        row["variants"] = {}
        for variant, folder in VARIANTS.items():
            row["variants"][variant] = score_variant(s, ref, variant, folder, root=ROOT)
        rows.append(row)
    aggregates = {}
    for variant in VARIANTS:
        values = [r["variants"][variant] for r in rows]
        totals = [v["comparison"]["totals"] for v in values]
        den = sum(t["pitch_duration_rate_denominator"] for t in totals)
        pitch_edits = sum(t["pitch_edit_distance"] for t in totals)
        pd_edits = sum(t["pitch_duration_edit_distance"] for t in totals)
        aggregates[variant] = {
            "songs": len(rows), "reference_notes": sum(t["reference_notes"] for t in totals),
            "prediction_notes": sum(t["prediction_notes"] for t in totals),
            "pitch_edits": pitch_edits, "pitch_duration_edits": pd_edits, "denominator": den,
            "pitch_error_rate": pitch_edits / den if den else 0,
            "pitch_duration_error_rate": pd_edits / den if den else 0,
            "median_song_pitch_duration_error_rate": statistics.median(
                t["pitch_duration_error_rate"] for t in totals),
            "layout_count_failures": sum(not v["layout_matches_expected_counts"] for v in values),
            "failures": sum(v["failed"] for v in values),
            "total_seconds_including_per_song_setup": sum(v["runtime"]["elapsed_seconds"] for v in values),
        }
    versions = {}
    for package in ("torch", "torchvision", "coremltools", "numpy", "pillow", "scipy", "opencv-python", "verovio"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    model_manifest = json.loads((REPO / "out/coreml/manifest.json").read_text())
    code = ["coreml_runtime.py", "detect.py", "front.py", "read.py", "revise.py", "write.py", "features.py"]
    return {"schema_version": 1, "scored_at_utc": datetime.now(timezone.utc).isoformat(),
            "hardware": {"machine": platform.machine(), "macos": platform.mac_ver()[0],
                         "python": platform.python_version()}, "dependencies": versions,
            "model": {"manifest": str(REPO / "out/coreml/manifest.json"),
                      "manifest_sha256": sha(REPO / "out/coreml/manifest.json"),
                      "detector_parameters": model_manifest["detector"]["parameters"],
                      "precision": model_manifest["precision"], "checkpoints": model_manifest["checkpoints"]},
            "code_sha256": {name: sha(REPO / "src/copisteria" / name) for name in code},
            "scorer_sha256": sha(ROOT / "compare_musicxml.py"),
            "aggregates": aggregates, "samples": rows}


def percent(x):
    return f"{100*x:.1f}%"


def report(result):
    intro = (
        f"Local CoreML comparison of {len(result['samples'])} songs from Original Sacred Harp (1911) "
        "against the project's 2025 MusicXML. All three neural stages use Apple's CoreML runtime "
        "with CPU_ONLY and the existing float32 copista-28m export (28,721,631 detector parameters), "
        "plus evidence-2m. Python handles geometry, ROI sampling and MusicXML decoding. "
        "This is a desktop reader benchmark, not the native Swift/iPhone pipeline."
    )
    method = (
        "The main metric is per-part Levenshtein disagreement on (absolute written chromatic pitch, "
        "notated duration in quarter notes). Its denominator is the sum of max(reference notes, "
        "predicted notes) for corresponding parts; missing/extra parts count. Lower is better. "
        "Parts match in printed order (normally treble, alto, tenor, bass). Generic prediction labels map by physical part position, including three-part layouts. Repeats are not unfolded; no key transposition, "
        "octave correction, arranging, or manual correction is applied. Rests, lyrics, shape semantics, "
        "ties, beams and repeat notation are not scored. JSON also includes pitch-only disagreement "
        "and exact absolute-onset event precision/recall/F1. These metrics are not the upstream OMR-NED metric."
    )
    caution = (
        "The 2025 files are candidate references for the 1911 music, not a fully proofread 1911 ground truth. "
        "Edition changes, encoded repeat structure, alternate endings and engraving differences can contribute to disagreement. "
        "Songs were selected by checking printed titles, not page number alone. The original twenty were retained; "
        "the expansion reviewed evenly spaced scan candidates across the volume, with documented supplementary pages. "
        "Additional songs were screened for complete boundaries, matching key signatures and reference part counts. "
        "A final source audit corrected crops/layout metadata and removed incompatible or incomplete pairings after initial inference; "
        "those runs are retained as diagnostics. Selection did not favor songs with better recognition scores. "
        "This remains a non-random convenience sample filtered for compatible reference editions; no book-wide accuracy claim is supported. "
        "Expected layout counts were checked visually; matching counts alone does not prove correct geometry. "
        "Both settings are reported for every song, without choosing the best setting per song. "
        "Timings include per-song model setup, two detector passes, decoding and viewer generation; "
        "they are single runs, not a controlled latency benchmark."
    )
    lines = ["# 1911 Sacred Harp CoreML benchmark", "", intro, "",
             "Source scans: [Sounding Spirit Digital Library](https://library.soundingspirit.org/volume/1911-Origin-JPK/page/all). "
             "The saved manifest includes every full-resolution download URL.", "", method, "", caution, "",
             "| Song (1911 page) | Default disagreement | Clean-layout disagreement | Default / clean systems |",
             "|---|---:|---:|---:|"]
    htmlrows = []
    detail = []
    for row in result["samples"]:
        a, b = (row["variants"][v] for v in VARIANTS)
        da, db = (v["comparison"]["totals"]["pitch_duration_error_rate"] for v in (a, b))
        systems = (f"{a['runtime']['systems']} / {b['runtime']['systems']} (expected {row['expected_systems']})")
        if a["failed"] or b["failed"]:
            failed_variants = ", ".join(name for name, value in (("default", a), ("clean_layout", b))
                                         if value["failed"])
            systems = f"{a['runtime']['systems']} / {b['runtime']['systems']} systems; " \
                      f"failed: {failed_variants}"
        lines.append(f"| {row['title']} ({row['printed_page_1911']}) | {percent(da)} | {percent(db)} | {systems} |")
        esc = html.escape
        htmlrows.append(f"<tr data-default='{da}' data-clean='{db}'><td><a href='#{row['id']}'>{esc(row['title'])}</a></td><td>{row['printed_page_1911']}</td>"
                        f"<td>{percent(da)}</td><td>{percent(db)}</td><td>{systems}</td></tr>")
        links = [f"<a href='{quote(row['source'])}'>Full scan</a>",
                 f"<a href='{quote(row['input'])}'>Model input</a>",
                 f"<a href='{quote(row['reference'])}'>2025 reference XML</a>"]
        preview = f"reference/previews/{row['id']}.html"
        if (ROOT / preview).exists():
            links.append(f"<a href='{quote(preview)}'>2025 reference score</a>")
        parts = []
        for label, v in (("Default", a), ("Clean layout", b)):
            if v["failed"]:
                links.append(f"<a href='{quote(v['failure'])}'>{label} failure details</a>")
            else:
                links.extend([f"<a href='{quote(v['viewer'])}'>{label} scan/score viewer</a>",
                              f"<a href='{quote(v['prediction'])}'>{label} XML</a>"])
            t = v["comparison"]["totals"]
            p = v["comparison"]["per_line"]
            body = ''.join(f"<tr><td>{esc(k)}</td><td>{q['reference_notes']}</td><td>{q['prediction_notes']}</td>"
                           f"<td>{percent(q['pitch_error_rate'])}</td><td>{percent(q['pitch_duration_error_rate'])}</td></tr>"
                           for k, q in p.items())
            failure_note = (f"<p class='error'>Inference failed: {esc(v['failure_error'])}. "
                            f"See <a href='{quote(v['failure'])}'>failure details</a>.</p>" if v["failed"] else "")
            parts.append(f"<h3>{label}</h3>{failure_note}<p>{v['runtime']['elapsed_seconds']:.2f} s; "
                         f"{v['runtime']['staves']} staves / {v['runtime']['systems']} systems; "
                         f"detector long side {v['runtime']['detector_size']} px; "
                         f"{t['pitch_duration_edit_distance']} edits / {t['pitch_duration_rate_denominator']}.</p>"
                         f"<table><tr><th>Part</th><th>Reference notes</th><th>Predicted notes</th>"
                         f"<th>Pitch disagreement</th><th>Pitch+duration</th></tr>{body}</table>")
        detail.append(f"<section id='{row['id']}'><h2>{esc(row['title'])} · {row['printed_page_1911']}</h2>"
                      f"<p>{' · '.join(links)}</p><p>{esc(row.get('notes', ''))} "
                      f"Crop: {row.get('crop') or 'full page'}. Reference page {row['reference_page_2025']}.</p>"
                      f"<details><summary>Show input scan</summary><img loading='lazy' src='{quote(row['input'])}' alt='{esc(row['title'])}'></details>"
                      + ''.join(parts) + "</section>")
    lines.extend(["", "## Pooled results", ""])
    aggregate_html = []
    for variant, a in result["aggregates"].items():
        text = (f"{variant}: {percent(a['pitch_duration_error_rate'])} pitch+duration disagreement "
                f"({a['pitch_duration_edits']}/{a['denominator']}); {a['layout_count_failures']}/{a['songs']} "
                f"layout count failures; {a['failures']}/{a['songs']} inference failures; "
                f"{a['total_seconds_including_per_song_setup']:.1f} s total.")
        lines.extend([text, ""])
        aggregate_html.append(f"<li>{html.escape(text)}</li>")
    lines.extend(["## Findings", ""])
    findings = []
    for variant in VARIANTS:
        failed = [s["title"] for s in result["samples"]
                  if not s["variants"][variant]["layout_matches_expected_counts"]]
        findings.append(f"{variant} layout-count failures: {', '.join(failed) or 'none'}.")
        errors = [f"{s['title']}: {s['variants'][variant]['failure_error']}" for s in result["samples"]
                  if s["variants"][variant]["failed"]]
        findings.append(f"{variant} inference failures: {'; '.join(errors) or 'none'}.")
    ordered = sorted(result["samples"], key=lambda s: s["variants"]["default"]["comparison"]["totals"]["pitch_duration_error_rate"])
    best = ", ".join(f"{s['title']} ({percent(s['variants']['default']['comparison']['totals']['pitch_duration_error_rate'])})"
                     for s in ordered[:3])
    findings.append(f"Lowest default pitch+duration disagreement: {best}.")
    delta = result["aggregates"]["default"]["pitch_duration_error_rate"] - result["aggregates"]["clean_layout"]["pitch_duration_error_rate"]
    findings.append(f"Cleanup {'lowers' if delta >= 0 else 'raises'} pooled disagreement by {abs(delta)*100:.1f} percentage points. "
                    "Its effect varies by song: it repairs Holy Manna's system grouping, but breaks Idumea and Rochester. "
                    "Even matching staff/system counts do not guarantee correct notes or bar segmentation.")
    for finding in findings:
        lines.extend([finding, ""])
    lines.extend(["## Files and reproduction", "", "`manifest.json` records source URLs, exact song crops and reference files. "
                  "`results.json` records all per-part scores, runtime reports, hashes and dependency versions. "
                  "`index.html` links every scan, output and reference.", "",
                  "From `/Users/mark/code/sh_omr`:", "", "```sh",
                  "copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_benchmark.py",
                  "# Recreate crops/copy references and run any missing predictions:",
                  "copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_benchmark.py --prepare --infer",
                  "# Add --force to rerun saved predictions; CoreML needs Apple's compiler/cache access.",
                  "# Add --render-references to recreate the reference score previews.",
                  "python3 -m unittest discover -s benchmarks/sacred-harp-1911 -p 'test_compare_musicxml.py' -v", "```", "",
                  "1911 page 35 / scan 0045 (Augusta) was downloaded during discovery and excluded because "
                  "modern page 35 is Saints Bound for Heaven. Scan 0044 (Hamilton / Bleeding Saviour) also lacked title matches. "
                  "Peterborough (1911 32b / 2025 452t) was run, then excluded because the scan has four parts and the reference "
                  "only three. Its full results remain in `diagnostics/excluded-peterborough.json`; Liverpool replaces it "
                  f"in the pooled set of {len(result['samples'])} songs. Original scans and all raw outputs are retained.", "",
                  "The final expansion audit exclusions and their original scores are preserved in "
                  "`diagnostics/excluded-expanded-pairs.json`. Review decisions and reasons are in the manifest's "
                  "`excluded_candidates` and the three `review_*.json` files. Outputs from the corrected King of Peace "
                  "crop are retained under `diagnostics/crop-before-final-audit/`. The original twenty-song manifest "
                  "and results remain in `diagnostics/manifest-20.json` and `diagnostics/results-20.json`.", "",
                  "Integrity checks are recorded in `diagnostics/validation-100.json`: 100 unique reference files copied "
                  "unchanged, all reference self-comparisons at zero edits, 200 CPU_ONLY CoreML outputs and 100 reference "
                  "previews present, valid crop bounds, unchanged original twenty-song scores, and no broken local report links. "
                  "The ten scorer/runner unit checks pass.", ""])
    (ROOT / "REPORT.md").write_text('\n'.join(lines))
    doc = ("<!doctype html><html lang='en'><meta charset='utf-8'><title>1911 Sacred Harp benchmark</title>"
           "<style>body{max-width:1100px;margin:40px auto;padding:0 24px;font:16px/1.55 system-ui;background:#faf9f5;color:#202c2c}"
           "h1,h2,h3{line-height:1.2}a{color:#136b70}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}"
           "td,th{padding:9px 13px;border-bottom:1px solid #ddd;text-align:left}th{background:#e6eeeb}"
           "section{margin:55px 0;border-top:2px solid #ddd;padding-top:20px}img{max-width:100%;height:auto}"
           "summary{cursor:pointer}h3{margin-bottom:0}input{padding:9px;font:inherit;width:260px;max-width:80%}"
           "button{font:inherit;background:transparent;border:0;color:inherit;cursor:pointer;text-decoration:underline}"
           "</style><h1>1911 Sacred Harp · local CoreML benchmark</h1>"
           f"<p>{html.escape(intro)}</p><p>{html.escape(method)}</p><p>{html.escape(caution)}</p>"
           "<p><a href='results.json'>Full results JSON</a> · <a href='manifest.json'>Dataset manifest</a> · "
           "<a href='REPORT.md'>Methods and reproduction</a></p><ul>" + ''.join(aggregate_html) + "</ul>"
           "<p><label>Find a song <input id='filter' type='search' placeholder='Title or printed page'></label> "
           "Click an error column to sort.</p><table><thead><tr><th>Song</th><th>1911 page</th>"
           "<th><button data-sort='default'>Default</button></th><th><button data-sort='clean'>Clean layout</button></th>"
           "<th>Systems</th></tr></thead><tbody id='summary-rows'>"
           + ''.join(htmlrows) + "</tbody></table><h2>Findings</h2>"
           + ''.join(f"<p>{html.escape(f)}</p>" for f in findings)
           + "<p>Peterborough was excluded after finding a four-part scan / three-part reference mismatch. "
           "<a href='diagnostics/excluded-peterborough.json'>Retained diagnostic results</a>. "
           f"Liverpool replaces it in the pooled set of {len(result['samples'])} songs. "
           "<a href='diagnostics/excluded-expanded-pairs.json'>Expansion source-audit exclusions and original results</a>.</p>" + ''.join(detail)
           + "<script>const tbody=document.getElementById('summary-rows');let direction=1,last='';"
           "document.getElementById('filter').addEventListener('input',e=>{const q=e.target.value.toLowerCase();"
           "for(const r of tbody.rows)r.hidden=!r.textContent.toLowerCase().includes(q);});"
           "for(const b of document.querySelectorAll('[data-sort]'))b.addEventListener('click',()=>{"
           "const key=b.dataset.sort;direction=key===last?-direction:1;last=key;"
           "[...tbody.rows].sort((a,b)=>direction*(+a.dataset[key]-+b.dataset[key])).forEach(r=>tbody.append(r));});"
           "</script></html>")
    (ROOT / "index.html").write_text(doc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--infer", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--render-references", action="store_true")
    args = parser.parse_args()
    samples = json.loads((ROOT / "manifest.json").read_text())["samples"]
    if args.prepare:
        prepare(samples)
    if args.infer:
        infer(samples, args.force)
    if args.render_references:
        render_references(samples)
    result = score(samples)
    (ROOT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    report(result)
    print(json.dumps(result["aggregates"], indent=2))


if __name__ == "__main__":
    main()
