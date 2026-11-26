# Sacred Harp OMR handoff

Updated 2026-11-26. Start a new session in `/Users/mark/code/sh_omr` and read this file first.

## Current task and stopping point

The latest work, **“resolve Lenox/Ragan and the remaining rhythm failures next,”** has reached a validated **handoff checkpoint** at `benchmarks/sacred-harp-1911/experiments/rhythm-resolution/final-a17498fc863d/REPORT.md`. The user asked to get to a handoff place and start a fresh chat. **The stage remains opt-in, and broad enablement is NOT ready.** Production defaults and the gallery remain unchanged. All120 predictions were generated with frozen code before reference scoring; the end-of-generation hash guard passed.

**Main results:** Lenox, Ragan and Duane Street have zero overflowing shared columns (20/10/18 columns). This is a capacity check, not complete source adjudication. Unresolved columns fall **157 → 87 /2104**; unresolved voice decisions **327 → 153**. **Fourteen** remaining columns are Ninety-Third Psalm’s printed meter/value conflict. The user explicitly chose **“Preserve printed3/4 and flag the irregular bars.”** Keep3/4, retain its six-quarter source values, and never silently normalize it to3/2. The other **73 columns** require source review. Weeping Savior `1911-33t-weeping-savior` correctly preserves source4/4 after rejecting a weak two-staff3/4 template fallback.

**Scores and regressions:** PD disagreement **3500 → 3333 edits** (development100:2840 → 2712; diagnostic20:660 → 621); **67 better /41 tie /12 worse** against source-timing. Time-aware F1 .6426 → .6640 and .5783 → .6637. There are **26 timing regressions;30 songs** in the union of metric regressions. All remain included. Lenox19 → 15PD, F1 .029 → .957; Ragan27 → 22, .335 → .890; Duane56 → 52, .088 → .834. Ragan still has **+1 PD** against the earlier proposal-rhythm parent21, despite fixing its overflowing bars. All120 songs are development/diagnostic and reference editions differ; disagreement is not pure accuracy.

**Validation:** **188 tests pass**. All18 original recovered physical heads remain; all17 adjudicated durations match. ProtectionM033 remains unadjudicated. All8334 part-measures match their selected common cut; no retained physical heads are clipped. Two prior pitched objects are now rejected by positive source evidence: **Ocean555 is a beam segment; Duane519 is an empty box**. All other prior pitched ID/pitch sets remain. Four duplicate serialized copies and232 note/rest interpretations of already emitted heads are removed; this is not a count of newly recovered source notes. Source geometry/staff identity, local accidentals/marks and normalized XML/trace durations pass. Prior proposal-rhythm399 and source-timing372 artifact hashes/file sets are unchanged. Five opening-meter checks, Primrose/Greenland transitions, Vermont/Weary controls, Golden P1M2 and Salem pass.

**Recommended next work:** audit the largest timing regressions using `regression-audit-queue.json` **before** broader enablement. Start with Done With The World (opening cut2 → 3.5), Elder (6 → 7), Jackson (4 → 5), The Midnight Cry (2 → 3), Primrose (4 → 4.5). Source-backed duration repairs retained in otherwise unresolved voices can expand a shared cut and shift later onsets. Review the source values/dots, missing events and bar boundaries together; do not repair scores by clipping heads or changing printed meter. Causes for these regressions remain unadjudicated. Then use `residual-source-inventory.json` for73 other source-review columns; Alabama has6, Newburgh/Providence/Fillmore/Harmony/Vermont3 each. Defer Holy Manna’s unusual layout as previously requested. **Alternative:** keep the stage quarantined and narrow the next experiment to the Lenox/Ragan fixes.

**Files:** `run_rhythm_resolution.py` creates the frozen/provenance-bound batch; `source_rhythm_resolution.py`, `attached_stem_evidence.py`, `beam_region_evidence.py` supply source-only constraints. `source_bar_fit.py` refines clocks/fallback with opt-in `refine_timing`; `run_source_timing_recovery.recover(...,rhythm_resolution=True)` enables the policy. The default is false. `summarize_rhythm_resolution.py` validates/scorers/regressions; `verify_source_timing_cases.py` validates source cases/user meter decision and parent manifests. No title/case IDs or reference counts enter prediction rules. Diagnostic source review and the Ragan321 local detector probe are saved; the probe favors eighth for a matching refined box but was **not used in prediction**, and the exact source value is not yet adjudicated. Full generation uses cached recognition/source pixels, without new neural inference. A diagnostic CoreML source-crop check ran separately with CPU_ONLY.

The final directory contains all120 XML/trace pairs, generation provenance/code snapshots/templates, results, validation, tests, source cases, source controls, residual/regression queues and the final artifact manifest. Earlier rhythm-resolution pilots/full/guarded/candidate/resolved are diagnostic only; some have rejected overbroad rules or mid-run code changes. Never overwrite them. Scratch history is `diagnostics/rhythm-resolution/WORKING.md`; a copyable next-chat prompt is `diagnostics/rhythm-resolution/NEXT_CHAT.md`. Use **`copisteria/.venv/bin/python`** and exact `run_local_recovery.samples()` input paths.

### Previous source meter propagation and shared bar lengths

The latest request, **“fix source meter propagation and shared bar lengths,”** is implemented as an **opt-in replay**, with a complete 120-song experiment at `benchmarks/sacred-harp-1911/experiments/source-timing/final-0eaa4b28dd55/REPORT.md`. Production defaults and the gallery remain unchanged. This corrects the propagation and fragment-length mechanisms; **157 / 2104 shared columns still have unresolved rhythm fits**, and broad enablement remains deferred.

**Confirmed source checks:** all five audited opening meters now match on every part (Ninety-Third Psalm 3/4, Fillmore 4/4, Alabama 6/8, Saint’s Delight 4/4, Duane Street 4/4). Primrose Hill explicitly writes 6/8 → 3/4 → 6/8 at measures 1, 11, 16. Greenland’s real changes and the Vermont/Weary Pilgrim negative controls pass. Golden Harp P1M2 spans two quarters with quarter + eighth + eighth and no extra hidden rest. Salem’s reviewed heads 260/393 now share a four-quarter bar (new measure 10), with false cuts 2641.4/2792.8 absent. Fillmore uses 10 + 9 source candidate bars, retaining every old head; exact source counts are not fully adjudicated. Farewell’s thin fragments are removed.

**Results and limits:** pitch-duration disagreement falls **3650 → 3500 edits** (development100: 2984 → 2840; diagnostic20: 666 → 660), with **16 better / 102 ties / 2 worse**. The two PD regressions remain included: Christian’s Hope +1, Ragan +6. Timing F1 rises in aggregate (development .5743 → .6426; diagnostic .5700 → .5783), but **16 songs regress in timing**, 17 songs in the union of the two metrics. Ragan’s five changed heads are visibly filled squares; its inherited dots/tuplets and other rhythms need further source review. Scores are edition disagreement, not pure accuracy; all 120 are development/diagnostic examples. Both candidate and parent are freshly scored with the same parser after the entire prediction batch is saved.

**Validation:** **172 tests pass**. All prior physical pitched IDs and pitches remain; non-measure geometry/staff identity, local accidentals and note marks remain; XML pitches and normalized durations match traces. All **8334 part-measures** have an encoded span equal to the selected common cut, with no unequal parallel spans. All 18 earlier recovered heads still emit; all 17 resolved reviewed durations match; Protection M033 remains unresolved. Stemless Newburgh/Chambers whole controls remain. The parent experiment’s 399 artifact hashes and file set are unchanged. Over-nominal **part-measures** rise 361 → 591 because unresolved common overflow is now shared across all parts; this is not an independent source-error count or a claim that all bars are rhythmically fixed.

New code: `source_meter_state.py` keeps raw source glyph values despite context relabeling and ignores inactive old measure heads. `source_meter_ink.py` uses source-template fallback only when opening consensus is absent (Saint’s Delight’s correct high-confidence head reading must not be overridden by a weaker template). `source_saved_events.py` reconstructs selected events from XML/trace, preserving source-local note marks. `source_bar_grid.py` rebuilds shared ink boundaries while retaining firm short bars and physical heads. `source_bar_fit.py` fits one common bar without copied fragment cuts; fitting selected onsets remain, and trailing forward time makes opening/repeat serialization honor the common cut. Impossible fits retain notes and expose overflow. `source_duration_options.py` narrowly supports filled-square corrections and separate beam/dot evidence, preserving hollow/stemless controls. `source_timing_trace.py` records actual selected cuts, clipping and final XML inventory; old `fixed_*` fields are explicitly prior input metadata.

Entry points: `run_source_timing_recovery.py`, `summarize_source_timing_recovery.py`, `verify_source_timing_cases.py`. The final directory contains results, validation, source-case checks, test checks, source reviews, code/input/template provenance and hashes. Earlier pilots/full trial remain diagnostic, including a withdrawn trial that lost local accidental/fermata marks; use only the final path above.

**Recommended next step:** audit Lenox/Ragan and the remaining unresolved source durations, tuplets and bar boundaries before broad enablement. **Alternative:** run a narrower meter-only experiment while keeping the current production baseline.

### Previous bar/meter audit

The latest request, **“audit remaining bar and meter errors first,”** is complete as a read-only audit. Start with `benchmarks/sacred-harp-1911/diagnostics/bar-meter-audit/REPORT.md` and `confirmed-findings.json`. The all-120 machine inventory is `inventory-99c1964edd6b/inventory.json` under that audit directory. No recognition policy, prediction, model or gallery was changed; the proposal/rhythm stage remains opt-in. No neural inference or reference-transcription scoring was performed.

Source review confirms **five wrong opening meters**: Ninety-Third Psalm prints 3/4 but emits 3/2; Fillmore 4/4 → 4/2; Alabama 6/8 → 3/2; Saint’s Delight 4/4 → 3/2; Duane Street 4/4 → 3/2. The last two had no eligible high-confidence opening-glyph consensus and were found by manually inspecting all 17 such cases. Primrose Hill additionally loses its lower-system **3/4 → 6/8** transitions, emitting only opening 6/8. Because both meters occupy three quarter notes, a duration-span check cannot catch that omission.

There are source-confirmed geometry/timing problems in **nine songs** overall (ten category records; Fillmore has two). Fillmore retains two bar boxes per staff per system despite many printed barlines; the source segmenter proposes 10 + 9, but these are candidate counts, not certified source totals. Its earlier segmentation candidate was rejected after losing 21 prior heads. Farewell To All has 2.1- and 0.9-pixel-wide bar fragments. Salem has false cuts through blank staff space and a notehead; three fragments map to column 10, and two nonempty fragments carry 4 + 4 quarters, producing an 8-quarter XML bar under 4/4. Golden Harp part 1 measure 2 reads a correct quarter plus two eighths (2 quarters), then adds an invisible quarter rest, making the encoded 2/4 bar span 3 quarters. Source crops and exact trace coordinates are saved. Exact complete source bar counts for Farewell/Salem are not adjudicated; earlier guessed source-cut positions were withdrawn.

Full screening: **43/120 songs** have irregular encoded spans (361 over-nominal, 32 unmarked short and 2 unknown-meter **part-measures**, not independent source bars). Another 58 implicit pickups and 160 short terminal/repeat candidates are separated rather than called errors. Of the 361 over-nominal part-measures, 195 contain invisible padding. Source-boundary screening finds candidates in 18 songs (17 missing-boundary candidates, 25 current cuts not reproduced), across 188 three/four-staff systems. These flags require source review and are not an accuracy/error-rate estimate. The raw meter inventory has 435 detections using all 120 exact recognition inputs; raw labels are not source truth. Greenland’s genuine changes and low-confidence false labels in Vermont/Weary Pilgrim are documented controls.

Important mechanisms: `local_write` locks the saved opening meter after installing the printed-meter consensus wrapper, so current consensus 4/4 in Fillmore and 6/8 in Alabama cannot take effect. Meter changes depend on measure-head state; meter glyph values are reduced to a boolean mark in `_events`. `segment_source_bars` clears later time/key/clef values and does not recover source-positioned transitions. Primrose already lacked those decoded changes before splitting; do not attribute its whole failure solely to the clearing step. `reflow_transform` pre-chops old voices and sums inherited fragment cuts when columns merge. The saved final trace fields `fixed_column_cuts`/`fixed_opening_meter` are **stale input metadata** after reflow/segmentation; there is no serialized final selected-cut vector. The audit therefore measures XML spans directly, including backup/forward/chord time. Add final timing provenance before the next correction.

Audit implementation: new `audit_bar_meter.py` plus three targeted XML-parser tests (`test_audit_bar_meter.py`, **3 passed**). Production code and historical artifacts remain intact. A mistakenly generated thumbnail-only worker attempt was moved outside the prediction experiment into `diagnostics/bar-meter-audit/archived-thumbnail-only-attempt`; it is withdrawn, not source evidence. The authoritative raw file is `meter-worker/meter-glyphs-all120.json`.

### Previous rhythm/regression correction

The latest request, **“fix those rhythms and regressions before enabling broadly,”** is implemented and tested. The authoritative experiment is `benchmarks/sacred-harp-1911/experiments/proposal-rhythm/final-0318d4f06bb9/REPORT.md`, with all 120 XML/trace pairs, source decisions, validation, code snapshots and artifact hashes. **Protection M034 is now an undotted quarter; Greenland M056 is now an undotted quarter. All 18 recovered heads still emit; all 17 resolved source-reviewed durations match.** Protection M033 remains unresolved; pitches/parts of every reviewed note have not been fully audited. The stage remains opt-in; no gallery or broad/default pipeline enablement occurred.

| Dataset | Before proposals | Previous proposals | Current edits | Denominator | Disagreement | Better / tie / worse vs previous proposals |
|---|---:|---:|---:|---:|---:|---|
| Development 100 | 4496 | 3945 | 2984 | 19695 | 15.15% | 17 / 83 / 0 |
| Diagnostic 20 | 1190 | 1076 | 666 | 4298 | 15.50% | 2 / 18 / 0 |

Total edits fall **5021 → 3650**, saving **1371** versus the previous proposal run (2036 versus before proposals). **No song regresses against either baseline.** The five previous regressions now improve beyond before proposals: Clamanda 248 → 249 → **13**; The Golden Harp 82 → 90 → **41**; Monroe 196 → 198 → **39**; Farewell To All 183 → 189 → **38**; Salem 189 → 194 → **56**. Denominators change with corrected part placement. These remain 1911/2025 edition disagreement metrics on development/diagnostic songs, not pure accuracy or independent validation.

The major regression cause was source layout: parallel staves had been serialized into incorrect systems/parts. `source_systems.py` groups only complete source opening clef cadences G2/G2/G2/F4 with glyph confidence ≥.8 near the staff opening; it leaves three-part/ambiguous cases alone. All nine eligible songs are repaired without score/title filtering: the five above, Weeping Savior (`1911-33t-weeping-savior`), Fillmore, Primrose Hill and Harmony. Root whole-page source inspection confirms normal four-part systems in all nine. `source_reflow.py` moves selected, clipped voices with their physical staff, retaining note values and inherited cuts. Collapsed bars with separate confident beat-zero readings additionally try source ink segmentation; a candidate must retain every previously emitted physical head. Clamanda and Primrose Hill pass that guard. Clamanda's source bar boundaries also remove its artificial tuplet. Other bar boundaries, meter changes and inherited irregular lengths can still be wrong; this does not resolve all existing rhythms.

`proposal_rhythm_policy.py` narrowly restores a filled quarter from a faster duration when its direct visual conditional posterior is ≥.85 and context confidence <.9. It does not change open-head values or introduce faster values without separate stem/flag evidence. Weak contextual dots (<.9) require direct visual no-dot support ≥.9 plus no compact detached ink in `proposal_rhythm_evidence.py`. Actual Greenland M055 dot and M057 eighth controls are preserved. Rhythm changes that would remove an old physical head are rolled back in the affected source bar; one change is rejected in the final run. There are 26 applied token-level rhythm actions, not a count of source-verified new notes.

Source inspection rejected the earlier broader trial `proposal-rhythm/full-23f851c20f08`: its raw visual posterior incorrectly shortened stemless whole heads in Newburgh 727 and Chambers 568 to halves. Preserve that trial and the rejected-source review; **do not use it as final**. This motivated the generic filled-quarter-only rule, rather than song exclusions. The initial incomplete `full-63452c113c48` stopped when an Edgefield rhythm change clipped a prior head; that led to the loss guard. All diagnostic trials remain saved.

Validation: **139 tests pass**. All 120 previous proposal XML/event streams replay exactly. Every previously emitted physical head remains; notehead IDs, boxes and staff identity are unchanged; every XML pitched event and normalized duration matches its trace. Duration search/options respect the new constraints. Source-supported system/bar repairs deliberately change part counts, bar assignments, meter or measure counts, so these are no longer frozen invariants in this stage. No new neural inference was needed. The full prediction batch was saved before reference scoring; hashes and snapshots verify code, recognition inputs, parent outputs and parent-bound selection metadata.

New entry points: `run_proposal_rhythm_recovery.py` and `summarize_proposal_rhythm_recovery.py`. They consume the immutable previous proposal experiment and replay the latest note/rest baseline. Use a new tag for another experiment; do not overwrite older artifacts.

### Previous missing-proposal stage

The latest request, **“address the 18 reviewed heads that still lack note proposals,”** is implemented as an opt-in experiment. **All 18 now have source-linked note proposals and emit notes.** The authoritative result is `benchmarks/sacred-harp-1911/experiments/missing-proposals/final-d190393b6a83/REPORT.md`, with all 120 XML/trace pairs, results, validation, source reviews, code snapshots and artifact hashes. Historical outputs and the published gallery remain unchanged.

| Dataset | Previous note/rest baseline edits | New proposal edits | New denominator | Disagreement | Better / tie / worse |
|---|---:|---:|---:|---:|---|
| Development 100 | 4496 | 3945 | 20165 | 19.56% | 84 / 11 / 5 |
| Diagnostic 20 | 1190 | 1076 | 4439 | 24.24% | 16 / 4 / 0 |

This saves **665 pitch+duration edits** across 120 songs. Both sets are now development/diagnostic examples for this correction; the 2025 reference also differs in edition from the scans, so these are disagreement scores, not pure accuracy. The purposeful 95-head audit now emits 57 heads (previous combined correction: 35; frozen: 9). All 18 proposal-gap heads are physically printed notes, but recovery does not establish correct pitch, duration or part. Source duration review covers 17: 15 match, two remain wrong, and Protection M033 is unresolved. Protection M034 is a triangular **fa**, correcting the old audit's la label; it emits an eighth instead of the source quarter. Greenland M056 emits a spurious dot on a quarter. Never Part M095 is a hollow square **half** note with a short stem stub, not a whole note.

The generic method nominates head-sized rest/measure-rest observations with no nearby note interpretation, probes unedited source crops at 16/20/24 pixels per staff space, and retains full note-family posteriors at natural peaks and forced local cells. Refined boxes must match the same physical head. Source ink constrains filled/open duration families. `read_layout()` decodes appended proposals while retaining original layout and token readings. Independent image/context support admits proposals through complete staff-bar recovery. A supported voice-one note suppresses an incompatible voice-one whole-measure rest in the same staff/bar; this resolves the final Greenland omission. Raw probabilities are retained separately from the uncalibrated `.51` admission floor. No case IDs, target note counts, reference pitch or reference transcription enter prediction.

Across the batch there are 1595 proposals, 1059 supported proposals, 771 new emitted note events and six whole-measure-rest conflicts removed. These are activity counts, not precision estimates. Four visually confirmed shallow Clamanda half rests remain excluded; Winter 313 and Ocean 706 still fail head-ink checks. Do not use detector rest labels as source truth: several square Clamanda notes were labelled measure rests by the detector. See `negative-controls.json` and JPG. All 40 new proposal locations in the five regressing songs are printed noteheads, but their pitch, part and rhythm need review. Regressions versus the previous combined baseline: Clamanda +1, The Golden Harp +8, Monroe +2, Farewell To All +6, Salem +5. None were excluded.

Validation: **121 tests pass**; all 120 latest baseline XML/event streams replay exactly; every baseline physical pitch is retained; old symbol IDs/geometry, staff/bar assignments, meter and measure counts are retained; all final XML pitched events match emitted traces; proposal duration alternatives respect source constraints. Writer clipping can still shorten open-note values. Predictions were saved before batch reference scoring, with model/input/cache/code provenance verified. Relevant code: `forced_visual_probe.py`, `missing_note_proposals.py`, `head_morphology.py`, `run_missing_note_proposals.py`, `summarize_missing_note_proposals.py`, and the additive `copisteria/src/copisteria/read.py::read_layout`. Proposal and duration-constraint arguments in `run_local_recovery.py` default off.

### Previous masking/bar/note-rest baseline

The latest requests are **“fix the verifier’s staff-line masking first, then test bar-level recovery for clipping losses”**, followed by **“then work on Notes emitted as rests.”** These three stages are implemented and tested. The final saved-reading ablation is `benchmarks/sacred-harp-1911/experiments/local-recovery/final-0996d2a689dc/REPORT.md`, with `results.json`, `validation.json`, all 360 new XML/trace pairs, and structured source snapshots. No fresh neural inference or publication was performed; frozen outputs and the hosted gallery remain unchanged.

| Dataset | Frozen | Masking | + local bar recovery | + note/rest evidence |
|---|---:|---:|---:|---:|
| Development 100: pitch+duration edits | 4701 | 4604 | 4534 | 4496 |
| Diagnostic 20: pitch+duration edits | 1230 | 1218 | 1190 | 1190 |

Combined disagreement rates are 22.34% (4496/20122) and 26.86% (1190/4431), saving 245 edits overall. All 120 historical frozen XML/event streams replay exactly. All 360 new XML pitched sequences match their emitted traces. The local variants retain every frozen physical note/pitch and retain emitted meter and measure counts; no final guard fallback was needed. Tests: 105 passed across the benchmark suite and `copisteria/tests/test_front_write.py`. There are three small combined development regressions: Farewell To All +1, Fillmore +3, Salem +3; no diagnostic-20 regression. Source review confirms the added glyphs are printed notes, but these songs have existing system/part grouping failures; pitch/duration/part assignment still need review. Do not remove them or call the 20 independent validation for this correction.

At this earlier stage the reviewed-head audit emitted 35/95 heads (was 9), with false rests reduced from 38 to 27; 19 of the 33 confirmed final-clipping cases were recovered. Those are purposeful five-song diagnostic counts, not population accuracy, and retention does not verify pitch/duration. Note/rest short-stem evidence adds 38 net edit savings beyond local recovery on the 100; 19 songs improve versus bar recovery, 101 tie across all 120, none worsen. Eight newly recovered source crops in Newburgh, Sherburne and New Lebanon were visually confirmed as notes: `note-rest-source-review.jpg` and JSON in the full experiment. The 18 reviewed rest-only heads still lacked emitted notes at that stage; the new proposal experiment above addresses them.

Implementation: `glyph_verifier.py` now requires horizontal exterior ink coverage and a thin row run before masking staff lines, plus a connected head-ink component spanning both axes. `bar_recovery.py` selects complete staff-bar voice sets at frozen column cuts. The additive opt-in `bar_transform` callback in `copisteria/src/copisteria/write.py` runs before ties/beams/slurs attach; its default path is unchanged. `note_rest_evidence.py` supplies narrow, connected short-stem evidence; `run_local_recovery.py` requires a credible existing neural note and staff position before applying it. Local recovery and note/rest selection are opt-in through this separate runner, not enabled in the gallery generator.

An earlier full trial (`full-017276b0990b`) exposed false promotions in Winter symbol 313 and Ocean symbol 706: empty boxes containing staff-line fragments passed quadrant counting. The generic connected-component guard fixes both; all final combined pitches/durations/onsets in these two songs match frozen readings. Both source negatives are regression tests. The final experiment includes generation-key hashes for selection/audit metadata and the holdout observation helper, verifies reference hashes only after generation, and saves structured code snapshots. `checks.json` records the 105-test command and code hashes.

The initial error investigation (before these corrections) is documented in `benchmarks/sacred-harp-1911/diagnostics/common-errors/REPORT.md` and `inventory.json`, reproduced by `audit_common_errors.py`. It checks all 120 frozen XML totals, revisits the 95 prior visually confirmed heads, and exactly replays the four selected fallback outputs containing admitted-but-missing reviewed notes. All 33 such heads are lost in final clipping; 38 reviewed heads emit false rests, 18 lack a note token, and only 9/95 emit notes in those frozen outputs. The categories overlap and the purposeful audit is not a population estimate. Three source crops reproduce verifier staff-row masking that erases real head ink. Actual XML exposes nine part-count discrepancies. Supplication's frozen trace chooses rest 285 over note 240; this is a wrong winning alternative, not grouping the separate printed heads 240 and 302 together. The new correction restores quarter note 240, but 302 remains a half rather than the source quarter; Supplication's edits are 38 versus frozen39 and prior verified37. Frozen outputs and the gallery remain unchanged.

User preferences:

- Always give a clearly labelled **Recommended** next step and at least one **Alternative**.
- Main model handles planning, ambiguous decisions, integration and review. Delegate bounded work to `gpt-6-luna` only when useful; at most two workers concurrently; workers should not spawn others. Persistent instructions: `/Users/mark/.codex/AGENTS.md`.
- Prioritize note/rest verification, shape-note detection, rhythm decoding and clipping. User asked to defer the earlier first-priority rare errors and to ignore Holy Manna's unusual layout for now; do not make that layout the main project again.
- Shared gallery should contain all 100 songs, be shareable with a hosted link and ZIP, and avoid references/comparisons to the original implementation in its presentation.

## Where to start

All paths below are relative to `benchmarks/sacred-harp-1911/` unless stated otherwise.

| Purpose | Authoritative artifact |
|---|---|
| Latest validated rhythm checkpoint (opt-in, regressions pending) | `experiments/rhythm-resolution/final-a17498fc863d/{REPORT.md,validation.json,source-case-checks.json,checks.json}` |
| Remaining rhythm/regression audit queues | `experiments/rhythm-resolution/final-a17498fc863d/{residual-source-inventory,regression-audit-queue}.json` |
| Latest checkpoint120 predictions | `experiments/rhythm-resolution/final-a17498fc863d/predictions/` |
| Latest source meter/shared timing replay | `experiments/source-timing/final-0eaa4b28dd55/{REPORT.md,validation.json,source-case-checks.json,checks.json}` |
| Latest experimental 120 predictions | `experiments/source-timing/final-0eaa4b28dd55/predictions/` |
| Previous bar/meter audit and priorities | `diagnostics/bar-meter-audit/REPORT.md`, `confirmed-findings.json`, `validation.json` |
| All-120 bar/meter screening and code snapshots | `diagnostics/bar-meter-audit/inventory-99c1964edd6b/inventory.json`, `SCREENING.md`, `source-snapshots/` |
| All-120 meter glyphs / opening comparison | `diagnostics/bar-meter-audit/meter-worker/meter-glyphs-all120.json`, `opening-meter-audit.json` |
| Latest rhythm/regression recovery and checks | `experiments/proposal-rhythm/final-0318d4f06bb9/REPORT.md`, `results.json`, `validation.json`, `checks.json`, `artifact-sha256.json` |
| Latest 120 predictions | `experiments/proposal-rhythm/final-0318d4f06bb9/predictions/` |
| Latest source reviews | `experiments/proposal-rhythm/final-0318d4f06bb9/{source-layout-review,rhythm-changes,rejected-open-duration-review}.json` and source contact sheets |
| Previous proposal correction and all checks | `experiments/missing-proposals/final-d190393b6a83/REPORT.md`, `results.json`, `validation.json`, `checks.json`, `artifact-sha256.json` |
| Previous proposal 120 predictions | `experiments/missing-proposals/final-d190393b6a83/predictions/` |
| Reviewed 18 heads and regression/negative controls | `experiments/missing-proposals/final-d190393b6a83/{source-review,regression-source-review,negative-controls}.json` and corresponding JPGs (`recovered-18.jpg` for the 18) |
| Previous correction ablation and all checks | `experiments/local-recovery/final-0996d2a689dc/REPORT.md`, `results.json`, `validation.json`, `checks.json` |
| Previous three variants, 120 songs each | `experiments/local-recovery/final-0996d2a689dc/{masking,bar_recovery,note_rest}/` |
| Final development-100 results and method | `experiments/bar-fitting/REPORT.md` |
| Development-100 per-song metrics | `experiments/bar-fitting/per-song.csv`, `summary.json` |
| Development-100 final result records | `experiments/reader-v2/replay_bar_fit/results.json` |
| Development-100 final XML and emitted traces | `experiments/reader-v2/replay_bar_fit/verification_rhythm/` |
| Development-100 checks | `experiments/bar-fitting/validation.json` |
| Independent-20 report and per-song metrics | `experiments/bar-fitting/unused20/REPORT.md`, `per-song.csv` |
| Independent-20 selection, crops, hashes, exclusions | `experiments/bar-fitting/unused20/manifest.json` |
| Independent-20 results and integrity checks | `experiments/bar-fitting/unused20/results.json`, `validation.json` |
| Independent-20 final XML and traces | `experiments/bar-fitting/unused20/frozen_bar_fit/` |
| Independent-20 prior-policy XML and traces | `experiments/bar-fitting/unused20/verification_rhythm/` |
| Independent-20 inference baseline | `experiments/bar-fitting/unused20/baseline/` |
| Prior notehead miss audit | `diagnostics/miss-trace/REPORT.md`, `confirmed-misses.json`, `index.html` |
| Earlier verification/detection experiments | `experiments/reader-v2/REPORT.md` |

**Do not confuse old root-level `results.json`, `REPORT.md` or `index.html` with the latest results.** They preserve earlier benchmarks. `reader-gallery/` is the saved original 100-song input reading/baseline, not the corrected published gallery.

## Results

Pitch + duration disagreement is per-part sequence edit distance divided by the summed per-part maximum sequence lengths. It is weighted over positions, not an average of song percentages. Reference files are from the 2025 edition, so edition differences contribute; this is not pure recognition accuracy.

| Dataset | Reader baseline | Verification + rhythm | Frozen bar fit |
|---|---:|---:|---:|
| Development 100 | 5360 / 20101 = 26.67% | 5003 / 20111 = 24.88% | 4701 / 20113 = 23.37% |
| Independent 20 | 1332 / 4424 = 30.11% | 1276 / 4427 = 28.82% | 1230 / 4429 = 27.77% |

Development 100: bar fitting saves 302 edits versus verification + rhythm; 57 songs improve, 40 tie, 3 worsen by one edit each (Save, Mighty Lord; Mount Zion; The Grieved Soul). The earlier regressions in Sawyer's Exit, The American Star and Elder are fixed beyond baseline. There are 19 conservative fallbacks: 10 to the previous verified reader and 9 to the original reading. All 19 emitted traces match the previous v2 outputs exactly.

Independent 20: bar fitting saves 46 edits versus verification + rhythm; 10 improve, 9 tie, 1 worsens. Selection was fixed before inference using source completeness, matching key signatures/voice counts and normal layouts. All 20 predictions were saved before scoring opened reference XML. This was a source-screened convenience sample, not a random book sample. It was disjoint from the 100 by title and reference file. A status interruption stopped inference after 13 saved songs; the remaining seven resumed from checkpoints. No policy changes or song replacements followed scoring.

The 20 are Detroit, Primrose Hill, Supplication, Old Hundred, Weeping Sinners, The Traveler, The Last Words of Copernicus, Chambers, The Dying Minister, The Promised Land, Morality, Jubilee, Jefferson, Duane Street, Cowper, Harmony, Ragan, Vermont, Schenectady and Alabama. Invitation was excluded **before inference** for a source/reference key-signature mismatch and replaced by Old Hundred. Exact selection evidence is retained in the manifest and `selection-candidates.json`.

### Concrete remaining regression

Supplication: previous policy 37 edits, frozen policy 39; all +2 are in the bass. In measure 3 the previous output emits two E3 quarter notes, source symbol IDs 240 and 302. Frozen fitting emits one E3 half note (302), omitting 240. A visual source review confirms two separate square quarter-note heads with separate stems. Evidence: `experiments/bar-fitting/unused20/supplication-bass-regression.jpg`, and `validation.json`. The output difference is established; the precise search/clipping mechanism still needs investigation. **Do not describe it as proven physical-glyph grouping without tracing the code path.**

Two layout errors remain in every independent-20 variant: Primrose Hill has 8 output parts / 1 system instead of 4 parts / 2 systems; Harmony has 5 parts instead of 4. They remain included in every reported aggregate. Do not remove difficult songs after seeing their scores.

### Prior confirmed miss audit

95 visually confirmed missing physical notes in five deliberately selected difficult songs: 81 square las, 8 fas, 5 sols, 1 mi. Stage counts: 39 rejected note candidates, 35 accepted notes later clipped, 18 rest-only proposals, 3 notes suppressed by the conflict rule. These are **not population proportions**; completely undetected heads are unmeasured. Current verification/bar fitting retains 9 audited heads in XML; retention alone does not establish correct pitch or duration.

Extra guided detection crops had no net score gain versus replay on 20 tested development songs. Ovalizing noteheads regressed on the five development songs and remains disabled. See the earlier reader-v2 report before repeating either experiment.

## Frozen policy and relevant code

Historical frozen SHA-256: `c13bea28e451f0aaf8888b8a3af6243e9241c3527b7b6ee9d534af9647ae1694`. The working verifier now contains the new masking correction, so this hash describes the snapshot, not the current working policy.
This hashes, in order: `reader_policy.py`, `glyph_verifier.py`, `guided_detection.py`, `run_reader_v2.py`, `bar_fitting.py`. Exact copies are in `experiments/reader-v2/source-snapshots/<hash>/`.
Independent-20 manifest SHA-256: `d6761e4b097eb125925fcfee3cae533d57fbeae8b710af15143f7b653d190cf6`.

- `bar_fitting.py`: opt-in joint alternatives for same-glyph note/rest readings, weak-event omission on overflowing bars, detector-observed durations and image-verified shared-stem chords. Printed numeric meter consensus anchors only confident agreeing first-system signatures. Normalized odds supply candidate priors. One score vote per staff-bar keeps meter comparisons aligned.
- `run_reader_v2.py`: `write_variant()` applies verification/rhythm/fitting and conservative fallback, saves writer traces. Near-certain original stem-verified notes are protected; unsafe fitting falls back to previous v2, then original if v2 itself is unsafe.
- `reader_policy.py`, `glyph_verifier.py`: image-based stems, note/rest admission, duration evidence. An admission value `.51` is **not** a newly calibrated model probability; retain original probabilities for scoring.
- `experiment_reader.py`, `detection_crops.py`, `layout_selection.py`, `symbol_conflicts.py`: full-page + staff-16 crop detection, structural source-image layout choice, original conflict resolution. Layout choice uses no reference score.
- `copisteria/src/copisteria/write.py`: actual event decoding, onset assignment, clipping, serialization. The original clipping function was left unchanged by the opt-in bar-fitting fix.
- `reader_trace.py`, `replay_writer_trace.py`: capture and reconstruct readings. `writer.emitted` is authoritative for final output; `rhythm_search_decisions` includes speculative paths/meter hypotheses.
- `compare_musicxml.py`, `run_reader_v2.conventional_score()`: offline scoring. Normalize part names by printed vocal order before comparison; reference instrument names can be misleading (e.g. Bass Trombone).
- `validate_frozen_policy.py`: independent-20 runner, separate `infer` and `score` phases; checks the frozen policy fingerprint.

Join by **song ID**, never title (there are two Weeping Savior entries). Trace `dur` is raw MusicXML duration units; use divisions to compare across scores. `e.dur` is quarter-note duration for ordinary emitted events; inspect actual XML for whole-measure/generated padding rests. Do not infer final emission from token `real.p`, `cand` or `synthetic` alone.

Keep the frozen outputs and checks intact. New corrections should use a distinct experiment/version and output directory. Include relevant runtime/writer/scorer hashes in its provenance; the five-file policy fingerprint alone does not cover the entire pipeline. Existing runners reuse cached records, so changing shared helper code without changing cache provenance can produce stale comparisons. Once these 20 are used to tune a correction, they are development examples for that correction; use further unused songs for independent validation.

## Runtime and reproduction

Use **`/Users/mark/code/sh_omr/copisteria/.venv/bin/python`**, not system Python or the root `.venv`. It has Pillow, numpy, pytest and Verovio. Local models are in `copisteria/out/coreml/`, run with `CPU_ONLY`; `PinnedInputs` keeps CoreML input buffers alive. The actual detector is Copisteria 28M (28,721,631 parameters), initially called 26M in the conversation, plus its evidence model. CoreML execution and scan downloads may require sandbox escalation.

From `/Users/mark/code/sh_omr`:

```sh
# Read-only source/XML bar-meter audit and its targeted parser checks.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/audit_bar_meter.py
copisteria/.venv/bin/python -m pytest -q benchmarks/sacred-harp-1911/test_audit_bar_meter.py

# Latest checks: 172 passed.
copisteria/.venv/bin/python -m pytest -q benchmarks/sacred-harp-1911 copisteria/tests/test_front_write.py copisteria/tests/test_read_layout.py

# Source meter/shared timing replay in a distinct keyed directory; opt-in.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_source_timing_recovery.py --tag newtag
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/summarize_source_timing_recovery.py benchmarks/sacred-harp-1911/experiments/source-timing/final-0eaa4b28dd55
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/verify_source_timing_cases.py benchmarks/sacred-harp-1911/experiments/source-timing/final-0eaa4b28dd55

# New rhythm/system replay in a distinct keyed directory; no neural inference.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_proposal_rhythm_recovery.py --tag newtag

# Validate/summarize the latest completed 120-song run.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/summarize_proposal_rhythm_recovery.py benchmarks/sacred-harp-1911/experiments/proposal-rhythm/final-0318d4f06bb9

# New proposal run in a distinct provenance-keyed directory, reusing raw multiscale probes.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_missing_note_proposals.py --tag newtag --probe-cache benchmarks/sacred-harp-1911/experiments/missing-proposals/full-5bd1fc22b566/probes

# Validate/summarize the latest proposal experiment without new inference.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/summarize_missing_note_proposals.py benchmarks/sacred-harp-1911/experiments/missing-proposals/final-d190393b6a83

# New ablations in a distinct provenance-keyed output directory.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_local_recovery.py --tag final

# Validate/summarize the completed 120-song experiment without regenerating predictions.
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/summarize_local_recovery.py benchmarks/sacred-harp-1911/experiments/local-recovery/final-0996d2a689dc
```

Do not run the old `run_reader_v2.py --phase replay --bar-fit` against its historical default output directory with the changed working verifier: it can overwrite frozen records. `validate_frozen_policy.py` deliberately rejects the changed working fingerprint. The new runner loads historical policy snapshots and checks exact frozen replay while writing every correction into its own directory.

Scoring regenerates `unused20/REPORT.md`; its additional final diagnostic section was appended after scoring. The machine-readable evidence remains in `validation.json`. Avoid unnecessary regeneration that drops those notes.

Source scans are cached in `sources/`, with exact crop inputs recorded in manifests. Full-resolution URL pattern: `https://iip.readux.io/iiif/2/1911-Origin-JPK-0037.tiff/full/full/0/default.jpg`. Reference source directory: `/Users/mark/sacredharp/code/sh_chords/SH2025 MusicXML Files 2026-04-09`. Earlier related project: `/Users/mark/code/sh_parse`.

The workspace root has no Git repository. `copisteria/` is a separate repository with pre-existing modified/untracked work (including writer, CoreML, shape-note and iOS work). Do not reset or discard it. `sites/sacred-harp-reader-1911/` is a separate Git checkout and was clean at handoff. All benchmark work is on disk, but do not assume it is committed just because the Site is committed.

## Published gallery

- Public URL: https://sacred-harp-1911-reader-gallery.colobus-veggies-01.chatgpt.site/
- ZIP: https://sacred-harp-1911-reader-gallery.colobus-veggies-01.chatgpt.site/downloads/sacred-harp-gallery.zip
- Site project ID: `appgprj_6afd3893a0288191b336d3b44779081b`.
- Published version: 2; source commit `3c85b335304a9e4cf069edd9175bea985310ff41`.
- Deployment returned `succeeded`; ID `appgdep_6afe93bf3cec8191882b7b88728798a1`.
- Checkout: `/Users/mark/code/sh_omr/sites/sacred-harp-reader-1911`; static directory `dist`.
- Generator: `build_corrected_gallery.py`; generated source: `experiments/bar-fitting/gallery-source/`.
- Packager: `package_reader_gallery.py`; supports per-sample `artifact_root`.
- Gallery contains the corrected **development 100**, not 120. The independent 20 are separately documented locally.
- All 100 packaged XML/comparison pairs exactly match the frozen outputs. All 803 local HTML links were checked, ZIP integrity and all 100 archived scores verified; ZIP size 22,130,427 bytes. Public search and Elder viewer/overlay were checked. The overlay marks **source-linked emitted notes/rests**; generated padding rests have no source boxes.

Local generation (no publication):

```sh
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/build_corrected_gallery.py
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/package_reader_gallery.py --results benchmarks/sacred-harp-1911/experiments/bar-fitting/gallery-source/results.json
```

For future hosted changes, read the Sites skill and use its current-source opening, packaging and native publish workflow. Preserve this project's identity and public audience; refresh credentials through the connector, never save tokens. Do not create a second Site. The generated gallery does not need new deployment until outputs or presentation are deliberately changed.

Earlier computer-use access to the local `file://` gallery was explicitly blocked. Do not work around that block by serving the same content through localhost. Public hosted browser checks and direct local artifact/image checks were used instead.

## Recommended continuation

**Recommended:** implement source-positioned meter state and final timing provenance first, then repair collapsed/false fragment bars and inherited cut aggregation. Use the five opening-meter errors, Primrose transitions, Fillmore, Salem/Farewell and Golden Harp's extra-rest case as source regression checks; retain the physical-head guard. Re-run all 120 with meter-sequence, span/padding and note-event checks before unused-song validation or broad enablement.

**Alternative:** start with a narrowly scoped reflow fix that stops adding full copied cuts for fragments of one source bar, then handle source meter changes. Keep the stage opt-in and every difficult song included. M033 remains unresolved; open-note duration changes still need separate stem evidence.
