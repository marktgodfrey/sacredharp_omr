#!/usr/bin/env python3
"""Extract source-level output changes between guarded prior/current run stages.

This is an analysis-only utility. It reads only a run manifest, completion
guards, and JSON traces, and writes ``changed-source-decisions.json`` under
the supplied run directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def removal_identity(entry: dict[str, Any]) -> str:
    # Recomputed pixel measurements on an already-rejected object are not a
    # new physical rejection. Preserve multiplicity separately with a Counter.
    return canonical({key:entry.get(key) for key in ('staff','sym_id','kind','voice','reason','note_kept')})


def completion_cases(run: Path, stage: str, expected: set[tuple[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    path = run / f"{stage}-complete.json"
    if not path.is_file():
        raise ValueError(f"Missing {stage} completion guard: {path}")
    guard = read_json(path)
    if guard.get("hash_guard_passed") is not True:
        raise ValueError(f"{stage} completion guard is not hash-guarded: {path}")
    cases = guard.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{stage} completion guard has no cases list: {path}")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for case in cases:
        key = (case.get("id"), case.get("variant"))
        if key in by_key:
            raise ValueError(f"Duplicate {stage} completion case: {key}")
        by_key[key] = case
    if set(by_key) != expected:
        missing, extra = sorted(expected - set(by_key)), sorted(set(by_key) - expected)
        raise ValueError(f"{stage} guard coverage mismatch; missing={missing}, extra={extra}")
    return by_key


def emitted_source_events(trace: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group emitted events by source symbol while preserving occurrence order."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in trace.get("writer", {}).get("emitted", []):
        source_id = event.get("e.si")
        if source_id is None:
            continue
        grouped.setdefault(str(source_id), []).append({
            "typ": event.get("typ"),
            "dots": event.get("dots"),
            "duration": event.get("e.dur", event.get("dur")),
            "pitch": {
                "step": event.get("step"),
                "octave": event.get("octave"),
                "alter": event.get("alter"),
            },
        })
    return grouped


def compare(run: Path) -> dict[str, Any]:
    if (run / "artifact-manifest.json").exists():
        raise ValueError(f"Refusing to write into sealed run containing artifact-manifest.json: {run}")
    manifest_path = run / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Missing run manifest: {manifest_path}")
    manifest = read_json(manifest_path)
    samples = manifest.get("samples")
    variants = manifest.get("variants")
    if not isinstance(samples, list) or not isinstance(variants, list):
        raise ValueError("Manifest must contain samples and variants lists")
    sample_by_id = {sample["id"]: sample for sample in samples}
    if len(sample_by_id) != len(samples):
        raise ValueError("Manifest contains duplicate sample IDs")
    expected = {(sample["id"], variant) for sample in samples for variant in variants}

    # Validate both complete guards and full configuration coverage before opening traces.
    stages = {stage: completion_cases(run, stage, expected) for stage in ("prior", "current")}
    configurations: list[dict[str, Any]] = []
    duration_diffs: list[dict[str, Any]] = []
    new_removals: list[dict[str, Any]] = []
    cut_diffs: list[dict[str, Any]] = []

    for sample_id, variant in sorted(expected, key=lambda item: (item[1], item[0])):
        sample = sample_by_id[sample_id]
        item: dict[str, Any] = {
            "id": sample_id,
            "variant": variant,
            "input": sample.get("input"),
            "stage_failures": {},
            "trace_status": {},
        }
        loaded: dict[str, dict[str, Any]] = {}
        for stage in ("prior", "current"):
            case = stages[stage][(sample_id, variant)]
            if case.get("failed"):
                item["stage_failures"][stage] = {
                    "failed": True,
                    "error": case.get("error"),
                    "traceback": case.get("traceback"),
                }
                item["trace_status"][stage] = "stage_failed"
                continue
            trace_path = run / stage / variant / f"{sample_id}.trace.json"
            if not trace_path.is_file():
                item["stage_failures"][stage] = {"failed": True, "error": f"missing trace: {trace_path.relative_to(run)}"}
                item["trace_status"][stage] = "trace_missing"
                continue
            data = trace_path.read_bytes()
            expected_hash = case.get("trace_sha256")
            actual_hash = hashlib.sha256(data).hexdigest()
            if expected_hash and actual_hash != expected_hash:
                item["stage_failures"][stage] = {
                    "failed": True,
                    "error": "trace_sha256_mismatch",
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                }
                item["trace_status"][stage] = "trace_hash_mismatch"
                continue
            loaded[stage] = json.loads(data)
            item["trace_status"][stage] = "ok"

        if "prior" not in loaded or "current" not in loaded:
            configurations.append(item)
            continue
        prior, current = loaded["prior"], loaded["current"]
        syms = {sym.get("i"): sym for sym in current.get("syms", [])}

        old_emitted = emitted_source_events(prior)
        new_emitted = emitted_source_events(current)
        for source_id in sorted(
            set(old_emitted) | set(new_emitted),
            key=lambda value: (0, int(value)) if value.isdigit() else (1, value),
        ):
            old_list, new_list = old_emitted.get(source_id, []), new_emitted.get(source_id, [])
            if old_list != new_list:
                sym = syms.get(int(source_id)) if source_id.isdigit() else None
                duration_diffs.append({
                    "id": sample_id,
                    "variant": variant,
                    "input": sample.get("input"),
                    "symbol_id": int(source_id) if source_id.isdigit() else source_id,
                    "staff": sym.get("staff") if sym else None,
                    "box": sym.get("box") if sym else None,
                    "prior_occurrences": old_list,
                    "current_occurrences": new_list,
                })

        prior_removed = prior.get("rhythm_resolution_details", {}).get("duplicate_serialized_events_removed", [])
        prior_removed_keys = Counter(removal_identity(entry) for entry in prior_removed)
        for entry in current.get("rhythm_resolution_details", {}).get("duplicate_serialized_events_removed", []):
            key=removal_identity(entry)
            if prior_removed_keys[key]:
                prior_removed_keys[key]-=1
                continue
            sym_id = entry.get("sym_id")
            sym = syms.get(sym_id, {})
            new_removals.append({
                "id": sample_id,
                "variant": variant,
                "input": sample.get("input"),
                "symbol_id": sym_id,
                "staff": entry.get("staff", sym.get("staff")),
                "box": sym.get("box"),
                "kind": entry.get("kind"),
                "voice": entry.get("voice"),
                "reason": entry.get("reason"),
                "source_geometry_evidence": entry.get("source_geometry_evidence"),
            })

        old_cuts = prior.get("final_timing", {}).get("selected_cuts", [])
        new_cuts = current.get("final_timing", {}).get("selected_cuts", [])
        if len(old_cuts) != len(new_cuts):
            cut_diffs.append({
                "id": sample_id,
                "variant": variant,
                "input": sample.get("input"),
                "status": "unequal_cut_array_lengths",
                "prior_length": len(old_cuts),
                "current_length": len(new_cuts),
                "prior_cuts": old_cuts,
                "current_cuts": new_cuts,
            })
        else:
            for index, (old_cut, new_cut) in enumerate(zip(old_cuts, new_cuts)):
                if old_cut != new_cut:
                    cut_diffs.append({
                        "id": sample_id,
                        "variant": variant,
                        "input": sample.get("input"),
                        "status": "changed_cut",
                        "index": index,
                        "prior_cut": old_cut,
                        "current_cut": new_cut,
                    })
        item["comparison_status"] = "compared"
        configurations.append(item)

    return {
        "schema_version": 1,
        "run": str(run),
        "comparison_basis": {
            "prior": "prior/{variant}/{id}.trace.json",
            "current": "current/{variant}/{id}.trace.json",
            "input_paths_from_manifest": True,
            "configurations_expected": len(expected),
        },
        "counts": {
            "configurations": len(configurations),
            "compared": sum(c.get("comparison_status") == "compared" for c in configurations),
            "configurations_with_stage_failures": sum(bool(c["stage_failures"]) for c in configurations),
            "new_removal_occurrences": len(new_removals),
            "sources_with_emitted_event_list_differences": len(duration_diffs),
            "cut_changes_or_length_flags": len(cut_diffs),
        },
        "new_removals": new_removals,
        "emitted_source_event_differences": duration_diffs,
        "changed_cuts": cut_diffs,
        "configurations": configurations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="run directory containing manifest.json and completion guards")
    args = parser.parse_args()
    run = args.run.resolve()
    result = compare(run)
    output = run / "changed-source-decisions.json"
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing diagnostic: {output}")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = result["counts"]
    print(
        "configurations={configurations} compared={compared} stage_failures={configurations_with_stage_failures} "
        "new_removals={new_removal_occurrences} emitted_source_differences={sources_with_emitted_event_list_differences} "
        "cut_changes_or_length_flags={cut_changes_or_length_flags}".format(**counts)
    )


if __name__ == "__main__":
    main()
