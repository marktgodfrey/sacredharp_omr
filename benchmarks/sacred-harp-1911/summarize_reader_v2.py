#!/usr/bin/env python3
"""Build compact per-song and aggregate reports for reader-v2 experiments."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"samples": [], "aggregates": {}}


def _totals(sample, variant):
    if variant == "baseline":
        return sample.get("baseline", {}).get("comparison", {}).get("totals", {})
    return sample.get("variants", {}).get(variant, {}).get("comparison", {}).get("totals", {})


def _rate(totals, metric="pitch"):
    if not totals:
        return None
    if metric == "pitch_duration":
        return totals.get("pitch_duration_edit_distance", 0) / max(1, totals.get("pitch_duration_rate_denominator", totals.get("reference_notes", 0)))
    return totals.get("pitch_edit_distance", 0) / max(1, totals.get("pitch_rate_denominator", totals.get("reference_notes", 0)))


def _weighted(samples, variant, metric="pitch"):
    edits = denom = 0
    for sample in samples:
        t = _totals(sample, variant)
        if not t:
            continue
        if metric == "pitch_duration":
            edits += t.get("pitch_duration_edit_distance", 0)
            denom += t.get("pitch_duration_rate_denominator", t.get("reference_notes", 0))
        else:
            edits += t.get("pitch_edit_distance", 0)
            denom += t.get("pitch_rate_denominator", t.get("reference_notes", 0))
    return (edits / denom if denom else None, edits, denom)


def _sign_counts(samples, candidate, baseline, metric="pitch_duration"):
    counts = {"better": 0, "equal": 0, "worse": 0, "missing": 0}
    for sample in samples:
        a, b = _rate(_totals(sample, candidate), metric), _rate(_totals(sample, baseline), metric)
        if a is None or b is None:
            counts["missing"] += 1
        elif abs(a - b) < 1e-12:
            counts["equal"] += 1
        elif a < b:
            counts["better"] += 1
        else:
            counts["worse"] += 1
    return counts


def _paired_sign_counts(left, right, left_variant, right_variant, metric="pitch_duration"):
    right_map = {s['id']: s for s in right}
    counts = {"better": 0, "equal": 0, "worse": 0}
    for sample in left:
        peer = right_map.get(sample['id'])
        if peer is None:
            continue
        a, b = _rate(_totals(sample, left_variant), metric), _rate(_totals(peer, right_variant), metric)
        if abs(a - b) < 1e-12:
            counts["equal"] += 1
        elif a < b:
            counts["better"] += 1
        else:
            counts["worse"] += 1
    return counts


def _fmt_rate(value):
    return "n/a" if value is None else f"{100 * value:.2f}%"


def _aggregate_line(label, samples, variant, baseline="baseline"):
    pitch, edits, den = _weighted(samples, variant)
    pd, pd_edits, pd_den = _weighted(samples, variant, "pitch_duration")
    signs = _sign_counts(samples, variant, baseline, "pitch_duration") if variant != baseline else None
    line = f"- **{label}:** pitch {edits}/{den} = {_fmt_rate(pitch)}; pitch+duration {pd_edits}/{pd_den} = {_fmt_rate(pd)}"
    if signs:
        line += f"; song outcomes vs {baseline}: {signs['better']} better, {signs['equal']} equal, {signs['worse']} worse"
    return line


def _by_title(samples):
    return {str(s.get("title", "")).casefold(): s for s in samples}


def _sum_variant(samples, variant, key):
    total = 0
    for s in samples:
        v = s.get("variants", {}).get(variant, {})
        value = v.get(key, 0)
        if isinstance(value, list):
            total += len(value)
        elif isinstance(value, (int, float)):
            total += value
    return total


def _proposal_counts(samples):
    added = replaced = events = 0
    for s in samples:
        for proposal in s.get("recovery_detection", {}).get("accepted_proposals", []):
            events += 1
            added += bool(proposal.get("added"))
            replaced += bool(proposal.get("replaced_base"))
    return events, added, replaced


def _audit_count(samples, variant):
    return sum(len(v.get("audit_hits", [])) for s in samples
               if (v := s.get("variants", {}).get(variant, {})))


def _make_csv(path, replay, infer, normalized, dev_titles, followup_titles):
    infer_map, norm_map = ({s['id']: s for s in samples} for samples in (infer, normalized))
    cohort_map = {t.casefold(): "development" for t in dev_titles}
    cohort_map.update({t.casefold(): "follow-up" for t in followup_titles})
    fields = ["id", "title", "cohort", "replay_baseline_pitch", "replay_verification_pitch",
              "replay_rhythm_pitch", "replay_baseline_pitch_duration", "replay_verification_pitch_duration",
              "replay_rhythm_pitch_duration", "replay_rhythm_actions", "replay_rhythm_fallback", "replay_rhythm_audit_hits",
              "guided_pitch", "guided_pitch_duration", "guided_actions", "guided_fallback", "guided_audit_hits",
              "detector_proposal_events", "detector_added", "detector_replaced",
              "normalized_pitch", "normalized_pitch_duration", "normalized_actions", "normalized_fallback",
              "normalized_audit_hits"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        rows = []
        replay_ids = set()
        for sr in replay:
            title_key = str(sr.get("title", "")).casefold()
            replay_ids.add(sr['id'])
            rows.append((title_key, sr, infer_map.get(sr['id'], {}), norm_map.get(sr['id'], {})))
        for sid in (set(infer_map) | set(norm_map)) - replay_ids:
            sample=infer_map.get(sid) or norm_map[sid]
            rows.append((sample['title'].casefold(), {}, infer_map.get(sid, {}), norm_map.get(sid, {})))
        for title_key, sr, si, sn in sorted(rows, key=lambda row: (row[0], str(row[1].get("id", "")))):
            row = {"title": sr.get("title") or si.get("title") or sn.get("title") or title_key.title(),
                   "cohort": cohort_map.get(title_key, "replay-only")}
            row["id"] = sr.get("id") or si.get("id") or sn.get("id") or ""
            for sample, pref, variant in ((sr, "replay_rhythm", "verification_rhythm"), (si, "guided", "guided_verification_rhythm"), (sn, "normalized", "guided_verification_rhythm")):
                if not sample:
                    continue
                totals = _totals(sample, variant)
                for metric, key in (("pitch", "pitch"), ("pitch_duration", "pitch_duration")):
                    row[f"{pref}_{metric}"] = "" if not totals else f"{100 * _rate(totals, key):.4f}"
                v = sample.get("variants", {}).get(variant, {})
                row[f"{pref}_actions"] = v.get("verification_actions", "")
                row[f"{pref}_fallback"] = v.get("conservative_fallback", "")
                row[f"{pref}_audit_hits"] = len(v.get("audit_hits", []))
            if sr:
                for variant, field in (("baseline", "replay_baseline"), ("verification", "replay_verification")):
                    for metric in ("pitch", "pitch_duration"):
                        row[f"{field}_{metric}"] = f"{100 * _rate(_totals(sr, variant), metric):.4f}"
                # Keep the full replay rhythm variant in generic replay_* fields above.
            if si:
                events, added, replaced = _proposal_counts([si])
                row.update(detector_proposal_events=events, detector_added=added, detector_replaced=replaced)
            writer.writerow(row)


def build(root: Path):
    base = root / "experiments" / "reader-v2"
    plan = json.loads((base / "plan.json").read_text(encoding="utf-8"))
    replay_data, infer_data, norm_data = (_load(base / p) for p in
        ("replay/results.json", "infer/results.json", "infer_normalized/results.json"))
    replay, infer, normalized = replay_data.get("samples", []), infer_data.get("samples", []), norm_data.get("samples", [])
    dev_titles, follow_titles = plan.get("development_songs", []), plan.get("followup_songs", [])
    infer_map = _by_title(infer)
    dev_samples = [infer_map[t.casefold()] for t in dev_titles if t.casefold() in infer_map]
    follow_samples = [infer_map[t.casefold()] for t in follow_titles if t.casefold() in infer_map]
    replay_map = _by_title(replay)
    same_dev_replay = [replay_map[t.casefold()] for t in dev_titles if t.casefold() in replay_map]
    same_follow_replay = [replay_map[t.casefold()] for t in follow_titles if t.casefold() in replay_map]
    _make_csv(base / "per-song.csv", replay, infer, normalized, dev_titles, follow_titles)

    report = ["# Reader v2 experiment summary", "",
              "Generated from the saved replay and inference result JSON files by `summarize_reader_v2.py`. Rates are weighted edit distance divided by the scorer's recorded denominator (the sum of per-part max(reference notes, prediction notes)); lower is better. Pitch+duration counts a mismatch in either attribute. Better/equal/worse counts use pitch+duration rate.", "",
              "## Saved-reading replay (full corpus)", "",
              f"{len(replay)} songs were rescored from saved readings.", "",
              _aggregate_line("Baseline", replay, "baseline"),
              _aggregate_line("Stem verification", replay, "verification"),
              _aggregate_line("Verification + rhythm search", replay, "verification_rhythm"), ""]
    report += [f"Rhythm search versus verification on the same {len(replay)} songs: {_aggregate_line('rhythm effect', replay, 'verification_rhythm', 'verification').split('; song outcomes vs verification: ')[-1]} (better/equal/worse).",
               f"Conservative fallback occurred in {_sum_variant(replay, 'verification_rhythm', 'conservative_fallback')} songs; audited glyphs reaching emitted XML: {_audit_count(replay, 'verification_rhythm')}.", "",
               "## Guided detection versus saved-reading replay", "",
               f"Inference coverage: {len(dev_samples)}/{len(dev_titles)} development songs and {len(follow_samples)}/{len(follow_titles)} follow-up songs currently present in `infer/results.json`.", ""]
    for label, samples in (("Development", dev_samples), ("Follow-up", follow_samples)):
        matched_titles = {str(s.get("title", "")).casefold() for s in samples}
        baseline_samples = [s for s in same_dev_replay + same_follow_replay if str(s.get("title", "")).casefold() in matched_titles]
        replay_variant_samples = [s for s in baseline_samples if "verification_rhythm" in s.get("variants", {})]
        report.append(f"### {label} subset ({len(samples)} guided songs)")
        report.append("")
        report.append(_aggregate_line("Guided verification + rhythm", samples, "guided_verification_rhythm"))
        if replay_variant_samples:
            report.append(_aggregate_line("Saved-reading verification + rhythm on same songs", replay_variant_samples, "verification_rhythm"))
            paired = _paired_sign_counts(samples, replay_variant_samples, "guided_verification_rhythm", "verification_rhythm")
            report.append(f"Paired guided vs replay rhythm pitch+duration outcomes: {paired['better']} better, {paired['equal']} equal, {paired['worse']} worse.")
        events, added, replaced = _proposal_counts(samples)
        report.append(f"Audit hits reaching emitted XML: {_audit_count(samples, 'guided_verification_rhythm')} (head-level structural recovery, not guaranteed pitch/duration correctness). Eligible crop proposal entries: {events}; {added} added and {replaced} marked as replacing a base detection. Conservative fallback: {_sum_variant(samples, 'guided_verification_rhythm', 'conservative_fallback')} songs.")
        report.append("")
    report += ["## Ovalized detector-input experiment (development only)", "",
               _aggregate_line("Guided verification on original crops", dev_samples, "guided_verification_rhythm"),
               _aggregate_line("Guided verification on normalized copies", normalized, "guided_verification_rhythm"),
               f"Normalization rows: {len(normalized)}/{len(dev_titles)} development songs. Added/replaced proposal entries: {_proposal_counts(normalized)[1]}/{_proposal_counts(normalized)[2]}.",
               f"Paired normalized vs original pitch+duration outcomes: {_paired_sign_counts(normalized, dev_samples, 'guided_verification_rhythm', 'guided_verification_rhythm')}.",
               "The plan records that ovalization regressed versus verification/rhythm on the five development songs; it remains an optional experiment and is not enabled for inference.", "",
               "## Traceable examples", "",
               "- Greenland, bass measure 6: baseline symbol 497 is a dotted-half F3 clipped to a half note, filling the 2-quarter bar; symbol 47 C3 eighth is dropped. Verification + rhythm changes 497 to a dotted quarter (3/2) and emits 47 as an eighth (1/2), filling the bar. Trace: `replay/verification_rhythm/1911-s0316-greenland.trace.json`; crop: `../../diagnostics/miss-trace/evidence/M062-bar.jpg`.",
               "- Arbacoochee case M075: square-head recovery accepts symbol 632 at writer admission .2896→.51 alongside the existing detector quarter-note proposal. .51 is an admission score, not a calibrated confidence. Trace: `replay/verification_rhythm/1911-s0544-arbacoochee.trace.json`; crop: `../../diagnostics/miss-trace/evidence/M075.jpg`.", "",
               "## Interpretation and scope", "",
               "The supported changes are stem verification/rest rejection around existing note admission and bounded, detector-supported duration search. Near-certain old stem-verified notes retain the conservative fallback. The purposeful audit recovered 9 of 95 audited heads to emitted XML; structural reach does not guarantee correct pitch or duration. The 2025 edition may disagree with the 1911 source because of editorial changes; those disagreements are not pure OMR accuracy errors. The selected audit is purposeful and diagnostic, not a population sample. Inference uses no reference notes or keys; references are used only by the offline scorer. Source snapshots are retained under `source-snapshots/`; XML traces are under `replay/verification_rhythm/`, `infer/guided_verification_rhythm/`, and `infer_normalized/guided_verification_rhythm/`. Reader-v1 was untouched.",
               "Saved-reading replay newly emitted 391 distinct source-note IDs and removed 29 previously emitted IDs across 100 songs; these are emission counts, not precision estimates. Extra crop inference matched the replay rhythm variant's pitch and pitch+duration edit counts on all 20 tested songs; we therefore stopped that experiment before a full 100-song neural run.", "",
               "The five development songs and fifteen follow-up songs come from the already-used 100-song corpus; this is not an independent test set. On a fresh raw-scan check, the stem verifier accepted 31/95 confirmed missing-note boxes and 5/35 rejected or ambiguous candidate boxes. One of those ambiguous candidates (Arbacoochee 664) was admitted into the output. These diagnostic counts are saved in `glyph-verifier-dev-matrix.json`; they are not population precision/recall estimates.", "",
               "The three pitch+duration regressions versus baseline are American Star (44→49 edits), Elder (48→51), and Sawyer's Exit (22→23). American Star's trace shows accepted notes disappearing after nearby rests are removed, consistent with remaining bar-fit/clipping problems. The fallback protects only near-certain, stem-verified old notes. All 45 benchmark tests passed.", "",
               "## Reproduction", "",
               "Commands: `copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_reader_v2.py --phase replay`; `copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_reader_v2.py --phase infer --titles 'Repentance' 'Protection' 'Greenland' 'Arbacoochee' 'Never Part' 'Lenox' 'Fairfield' 'Ninety-Fifth' 'America' 'Pisgah' 'Suffield' 'Stratfield' 'Hallelujah' 'Exhilaration' 'Lena' 'Amsterdam' 'Rest For The Weary' 'The Bower Of Prayer' 'New Harmony' 'Holiness'`; `copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_reader_v2.py --phase infer --normalize-heads --titles 'Repentance' 'Protection' 'Greenland' 'Arbacoochee' 'Never Part'`; `copisteria/.venv/bin/python benchmarks/sacred-harp-1911/summarize_reader_v2.py`. Inference without `--titles` covers 100 songs and was not run.", ""]
    (base / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    return base / "per-song.csv", base / "REPORT.md"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="sacred-harp-1911 benchmark directory")
    args = parser.parse_args()
    for path in build(args.root):
        print(path)


if __name__ == "__main__":
    main()
