#!/usr/bin/env python3
"""Replay image-structure layout choice over saved Sacred Harp benchmark outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from layout_selection import choose_layout


HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "results.json"
DEFAULT_OUTPUT = HERE / "experiments/reader-v1/layout-selection-evaluated.json"
DEFAULT_REPORT = HERE / "experiments/reader-v1/layout-selection.md"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def relpath(path):
    try:
        return path.relative_to(HERE).as_posix()
    except ValueError:
        return str(path)


def aggregate_rows(subset):
    n = len(subset)
    d_edit = sum(r["default"]["pitch_duration_edit_distance"] for r in subset)
    s_edit = sum(r["selected"]["pitch_duration_edit_distance"] for r in subset)
    denom = sum(r["default"]["denominator"] for r in subset)
    selected_denom = sum(r["selected"]["denominator"] for r in subset)
    d_pitch = sum(r["default"]["pitch_edit_distance"] for r in subset)
    s_pitch = sum(r["selected"]["pitch_edit_distance"] for r in subset)
    pitch_denom = sum(r["default"]["pitch_denominator"] for r in subset)
    selected_pitch_denom = sum(r["selected"]["pitch_denominator"] for r in subset)
    return {"songs": n, "pooled_denominator": denom, "selected_pooled_denominator": selected_denom,
            "default_pitch_edits": d_pitch, "selected_pitch_edits": s_pitch,
            "pitch_pooled_denominator": pitch_denom, "selected_pitch_pooled_denominator": selected_pitch_denom,
            "default_pitch_pooled_error_rate": d_pitch / pitch_denom if pitch_denom else 0,
            "selected_pitch_pooled_error_rate": s_pitch / selected_pitch_denom if selected_pitch_denom else 0,
            "default_pitch_duration_edits": d_edit,
            "selected_pitch_duration_edits": s_edit,
            "default_pooled_error_rate": d_edit / denom if denom else 0,
            "selected_pooled_error_rate": s_edit / selected_denom if selected_denom else 0,
            "default_layout_mismatches": sum(not r["default"]["layout_matches_expected_counts"] for r in subset),
            "selected_layout_mismatches": sum(not r["selected"]["layout_matches_expected_counts"] for r in subset),
            "switched": sum(r["switched"] for r in subset),
            "better": sum(r["comparison"] == "better" for r in subset),
            "equal": sum(r["comparison"] == "equal" for r in subset),
            "worse": sum(r["comparison"] == "worse" for r in subset)}


def evaluate(results_path=DEFAULT_INPUT, output_path=DEFAULT_OUTPUT, report_path=DEFAULT_REPORT):
    results_path = Path(results_path).resolve()
    data = json.loads(results_path.read_text())
    source_hashes = {
        "results": {"path": relpath(results_path), "sha256": sha256(results_path)},
        "evaluate_layout_selection.py": {"path": relpath(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "layout_selection.py": {"path": relpath(HERE / "layout_selection.py"), "sha256": sha256(HERE / "layout_selection.py")},
        "songs": {},
    }
    rows = []
    for sample in data["samples"]:
        variants = sample["variants"]
        candidates, paths = [], {}
        # Selection sees only variant name, saved runtime structure and saved MusicXML.
        for name in ("default", "clean_layout"):
            variant = variants[name]
            xml_path = (HERE / variant["prediction"]).resolve()
            paths[name] = xml_path
            xml_text = xml_path.read_text()
            candidates.append((name, variant["runtime"], xml_text))
        selected_name, scores = choose_layout(candidates)
        source_hashes["songs"][sample["id"]] = {
            "input_source_sha256": sample.get("input_sha256", sample.get("source_sha256")),
            "variants": {name: {"path": relpath(paths[name]), "sha256": sha256(paths[name])}
                         for name in ("default", "clean_layout")}}

        # Reference-derived scores and expected-count flags are read only after selection.
        default = variants["default"]
        selected = variants[selected_name]
        dt = default["comparison"]["totals"]
        st = selected["comparison"]["totals"]
        rows.append({
            "id": sample["id"], "title": sample["title"], "chosen_variant": selected_name,
            "switched": selected_name != "default",
            "penalties": {score["name"]: score["penalty"] for score in scores},
            "default": {"pitch_edit_distance": dt["pitch_edit_distance"],
                        "pitch_denominator": dt["pitch_rate_denominator"],
                        "pitch_duration_edit_distance": dt["pitch_duration_edit_distance"],
                        "denominator": dt["pitch_duration_rate_denominator"],
                        "pitch_duration_error_rate": dt["pitch_duration_error_rate"],
                        "layout_matches_expected_counts": default["layout_matches_expected_counts"]},
            "selected": {"variant": selected_name,
                         "pitch_edit_distance": st["pitch_edit_distance"],
                         "pitch_denominator": st["pitch_rate_denominator"],
                         "pitch_duration_edit_distance": st["pitch_duration_edit_distance"],
                         "denominator": st["pitch_duration_rate_denominator"],
                         "pitch_duration_error_rate": st["pitch_duration_error_rate"],
                         "layout_matches_expected_counts": selected["layout_matches_expected_counts"],
                         "viewer": selected["viewer"], "xml": selected["prediction"]},
            "comparison": ("better" if st["pitch_duration_error_rate"] < dt["pitch_duration_error_rate"] else
                           "worse" if st["pitch_duration_error_rate"] > dt["pitch_duration_error_rate"] else "equal"),
        })


    non_holy = [r for r in rows if r["title"].casefold() != "holy manna"]
    output = {"schema_version": 1, "selection_inputs": ["variant name", "saved runtime", "saved MusicXML"],
              "reference_used_for_selection": False, "code_source_sha256": source_hashes,
              "aggregates": {"all100": aggregate_rows(rows), "excluding_holy_manna": aggregate_rows(non_holy)},
              "songs": rows}
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n")
    md = ["# Saved-output layout selection replay", "",
          "This is a development benchmark replay over saved outputs, not held-out proof. The selector receives only the variant name, saved runtime structure, and saved MusicXML for each candidate. It does not receive reference XML, expected counts, or note scores.", "",
          "The rule prefers a candidate with zero structural penalty; raw wins ties. If both candidates are invalid, it falls back to raw/default.", "",
          "| Scope | Songs | Default edits / denominator | Selected edits / denominator | Default rate | Selected rate | Layout mismatches (default → selected) | Switched | Better / equal / worse |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for label, key in (("All 100", "all100"), ("Excluding Holy Manna", "excluding_holy_manna")):
        a = output["aggregates"][key]
        md.append(f"| {label} | {a['songs']} | {a['default_pitch_duration_edits']} / {a['pooled_denominator']} | {a['selected_pitch_duration_edits']} / {a['selected_pooled_denominator']} | {a['default_pooled_error_rate']:.4%} | {a['selected_pooled_error_rate']:.4%} | {a['default_layout_mismatches']} → {a['selected_layout_mismatches']} | {a['switched']} | {a['better']} / {a['equal']} / {a['worse']} |")
    md += ["", f"Machine-readable per-song results and SHA-256 provenance: `{relpath(output_path)}`.", ""]
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(md))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    result = evaluate(args.input, args.output, args.report)
    print(json.dumps(result["aggregates"], indent=2))


if __name__ == "__main__":
    main()
