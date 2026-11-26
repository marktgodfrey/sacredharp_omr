# Sacred Harp OMR handoff

Updated 2026-11-26. Start a new session in `/Users/mark/code/sh_omr` and read this file first.

## Current task and stopping point

The latest work, **“resolve Lenox/Ragan and the remaining rhythm failures next,”** has reached a validated **handoff checkpoint** at `benchmarks/sacred-harp-1911/experiments/rhythm-resolution/final-a17498fc863d/REPORT.md`. The user asked to get to a handoff place and start a fresh chat. **The stage remains opt-in, and broad enablement is NOT ready.** Production defaults and the gallery remain unchanged. All 120 predictions were generated with frozen code before reference scoring; the end-of-generation hash guard passed.

**Main results:** Lenox, Ragan and Duane Street have zero overflowing shared columns (20/10/18 columns). This is a capacity check, not complete source adjudication. Unresolved columns fall **157 → 87 / 2104**; unresolved voice decisions **327 → 153**. **Fourteen** remaining columns are Ninety-Third Psalm’s printed meter/value conflict. The user explicitly chose **“Preserve printed 3/4 and flag the irregular bars.”** Keep 3/4, retain its six-quarter source values, and never silently normalize it to 3/2. The other **73 columns** require source review. Weeping Savior `1911-33t-weeping-savior` correctly preserves source 4/4 after rejecting a weak two-staff 3/4 template fallback.

**Scores and regressions:** PD disagreement **3500 → 3333 edits** (development 100: 2840 → 2712; diagnostic 20: 660 → 621); **67 better / 41 tie / 12 worse** against source-timing. Time-aware F1 .6426 → .6640 and .5783 → .6637. There are **26 timing regressions; 30 songs** in the union of metric regressions. All remain included. Lenox 19 → 15 PD, F1 .029 → .957; Ragan 27 → 22, .335 → .890; Duane 56 → 52, .088 → .834. Ragan still has **+1 PD** against the earlier proposal-rhythm parent 21, despite fixing its overflowing bars. All 120 songs are development/diagnostic and reference editions differ; disagreement is not pure accuracy.

**Validation:** **188 tests pass**. All 18 original recovered physical heads remain; all 17 adjudicated durations match. Protection M033 remains unadjudicated. All 8334 part-measures match their selected common cut; no retained physical heads are clipped. Two prior pitched objects are now rejected by positive source evidence: **Ocean 555 is a beam segment; Duane 519 is an empty box**. All other prior pitched ID/pitch sets remain. Four duplicate serialized copies and 232 note/rest interpretations of already emitted heads are removed; this is not a count of newly recovered source notes. Source geometry/staff identity, local accidentals/marks and normalized XML/trace durations pass. Prior proposal-rhythm 399 and source-timing 372 artifact hashes/file sets are unchanged. Five opening-meter checks, Primrose/Greenland transitions, Vermont/Weary controls, Golden P1M2 and Salem pass.

**Recommended next work:** audit the largest timing regressions using `regression-audit-queue.json` **before** broader enablement. Start with Done With The World (opening cut 2 → 3.5), Elder (6 → 7), Jackson (4 → 5), The Midnight Cry (2 → 3), Primrose (4 → 4.5). Source-backed duration repairs retained in otherwise unresolved voices can expand a shared cut and shift later onsets. Review the source values/dots, missing events and bar boundaries together; do not repair scores by clipping heads or changing printed meter. Causes for these regressions remain unadjudicated. Then use `residual-source-inventory.json` for 73 other source-review columns; Alabama has 6, Newburgh/Providence/Fillmore/Harmony/Vermont 3 each. Defer Holy Manna’s unusual layout as previously requested. **Alternative:** keep the stage quarantined and narrow the next experiment to the Lenox/Ragan fixes.

**Files:** `run_rhythm_resolution.py` creates the frozen/provenance-bound batch; `source_rhythm_resolution.py`, `attached_stem_evidence.py`, `beam_region_evidence.py` supply source-only constraints. `source_bar_fit.py` refines clocks/fallback with opt-in `refine_timing`; `run_source_timing_recovery.recover(...,rhythm_resolution=True)` enables the policy. The default is false. `summarize_rhythm_resolution.py` validates outputs and reports scores/regressions; `verify_source_timing_cases.py` validates source cases/user meter decision and parent manifests. No title/case IDs or reference counts enter prediction rules. Diagnostic source review and the Ragan 321 local detector probe are saved; the probe favors eighth for a matching refined box but was **not used in prediction**, and the exact source value is not yet adjudicated. Full generation uses cached recognition/source pixels, without new neural inference. A diagnostic CoreML source-crop check ran separately with CPU_ONLY.

The final directory contains all 120 XML/trace pairs, generation provenance/code snapshots/templates, results, validation, tests, source cases, source controls, residual/regression queues and the final artifact manifest. Earlier rhythm-resolution pilots/full/guarded/candidate/resolved are diagnostic only; some have rejected overbroad rules or mid-run code changes. Never overwrite them. Scratch history is `diagnostics/rhythm-resolution/WORKING.md`; a copyable next-chat prompt is `diagnostics/rhythm-resolution/NEXT_CHAT.md`. Use **`copisteria/.venv/bin/python`** and exact `run_local_recovery.samples()` input paths.

## Timing regression audit follow-up (2026-11-26)

The five largest timing-regression songs have now been source-reviewed in
`benchmarks/sacred-harp-1911/diagnostics/timing-regression-audit-2026-11-26/REPORT.md`
with reproducible extraction/checks in `audit.py` and source-bound `audit.json`.
Five of six affected bars have local source explanations: Done With The World's
repeat dot 394 and inherited false dot on half 397; Elder column 2's false dot on
half 7 beside a stain; Jackson's false head 256; Midnight Cry's repeat dot
misassigned to half 102; Primrose's beam 243. Retain the valid half restorations.
**Elder column 8 remains ambiguous:** 361 has a real dot and 365 is a visible
stemless filled head; do not delete that head or remove the real dot to fit six.

No prediction rules, frozen artifacts, defaults, or gallery were changed. Input
hashes, 352 audited part-measure spans, 18 protected heads / 17 reviewed durations,
and current/previous/proposal artifact manifests pass read-only checks. Twenty-one
timing-regression songs remain unaudited; Holy Manna stays deferred.

**Recommended:** fix general repeat-dot, inherited-dot, and false-head evidence
gaps under the opt-in policy, preserving the unresolved Elder bar; then freeze
code and use a new batch tag. **Alternative:** continue source review with The
Promised Land, Burdette, New Prospect, Parting Hand, and Ocean.

## Essential safeguards

- Use exact recognition inputs from `run_local_recovery.samples()`, not guessed scan filenames or crops. Join by song ID, not title: there are two Weeping Savior songs.
- Keep prior experiments/hash manifests immutable. Use a new tag/output directory. Never replay an old default output directory with changed code.
- Finish code/test edits before generation, then freeze every benchmark/copisteria Python file until all predictions are complete. The runner checks this before opening references. No references, target counts, title filters or case IDs in prediction rules.
- Protect true hollow counters even when a staff line makes their centers dark (Wells controls). Do not promote an existing half to whole without separate stem evidence. Never Part 522 has a real short stem stub and remains half; Newburgh 727 and Chambers 568 remain whole.
- All original 18 recovered heads stay protected. Greenland M055 has a real dot, M057 a real eighth, M056 is undotted quarter; Protection M034 is quarter. Protection M033 remains unresolved. Do not fix meter fits by shortening or dropping printed notes.
- No broad/default enablement or gallery publication has been authorized for these new stages. Keep Holy Manna’s rare layout deferred.
- The workspace root is now the `sacredharp_omr` Git repository. `copisteria/` is a pinned submodule; the writer, CoreML, shape-note and iOS work is committed on its `sacred-harp` branch. Source is versioned in Git; complete historical data and model builds are preserved in the `workspace-2026-11-26` snapshot release. See `README.md` for clone/restore instructions. Do not reset or discard local work.

## Reproduction and prior artifacts

From `/Users/mark/code/sh_omr`, use **`copisteria/.venv/bin/python`**, not system Python or the root `.venv`:

```sh
# Checks: 188 passed at this checkpoint.
copisteria/.venv/bin/python -m pytest -q benchmarks/sacred-harp-1911 copisteria/tests/test_front_write.py copisteria/tests/test_read_layout.py

# New opt-in experiment; always choose a new tag. Full batch precedes scoring.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_rhythm_resolution.py --tag NEW_TAG

# Validation writes reports/manifests: run on the new directory, preserving final artifacts.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/summarize_rhythm_resolution.py NEW_DIRECTORY
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/verify_source_timing_cases.py NEW_DIRECTORY
```

All paths below are relative to `benchmarks/sacred-harp-1911/`:

| Purpose | Path |
|---|---|
| Current checkpoint | `experiments/rhythm-resolution/final-a17498fc863d/` |
| Immediate comparison, 3500 PD, 157 unresolved | `experiments/source-timing/final-0eaa4b28dd55/` |
| Reconstruction parent, 3650 PD | `experiments/proposal-rhythm/final-0318d4f06bb9/` |
| 18-head review/proposal provenance | `experiments/missing-proposals/final-d190393b6a83/` |
| Masking/bar/note-rest ablation | `experiments/local-recovery/final-0996d2a689dc/` |
| Prior meter/bar audit | `diagnostics/bar-meter-audit/REPORT.md` |
| Prior 95-head source audit | `diagnostics/miss-trace/REPORT.md` |

Trace `writer.emitted` is final emission; `e.dur` is quarter duration, while `dur` is raw XML units. Inspect XML for measure rests/generated padding. `final_timing` contains actual selected cuts; old `fixed_*` data are input metadata. A fitting bar does not certify pitches, parts, completeness or source note values.

Models are in `copisteria/out/coreml/`; detector is 28M (28,721,631 parameters) plus evidence model. Use CPU_ONLY and PinnedInputs. CoreML compilation or scan downloads may need sandbox escalation. No new inference is needed for saved-reading replay. Current source scans and exact crop inputs are recorded in sample manifests. Reference directory is `/Users/mark/sacredharp/code/sh_chords/SH2025 MusicXML Files 2026-04-09`.

The full earlier handoff, historical metrics/reproduction and gallery identity are preserved in [HANDOFF_HISTORY_2026-11-26.md](diagnostics/rhythm-resolution/HANDOFF_HISTORY_2026-11-26.md). The published 100-song gallery remains unchanged. If gallery work is later requested, read that archive and the Sites skill first; do not create a second Site or work around the earlier local-file browser block by serving it through localhost.

## Suggested next-chat prompt

> Read `/Users/mark/code/sh_omr/HANDOFF.md` and the current checkpoint’s regression-audit-queue.json. Audit the largest timing regressions first, then the remaining ordinary-layout source rhythm failures. Keep the stage opt-in, preserve Ninety-Third Psalm’s printed 3/4 with flagged irregular bars, and protect the 18 recovered heads and 17 reviewed durations. Continue toward source-correct rhythm recovery before broad enablement.

**Recommended:** start a fresh chat with that prompt. **Alternative:** remain in this chat for a narrowly scoped regression source review.
