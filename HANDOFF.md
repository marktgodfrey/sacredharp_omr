# Sacred Harp OMR handoff

Updated 2026-11-27. Start a new session in `/Users/mark/code/sh_omr` and read this file first.

## Latest task complete: plain-language project overview and accuracy explanation

Start with [the eight-page project overview](output/pdf/sacred-harp-omr-project-overview.pdf)
for a high-level explanation of what Copisteria supplies, what this project
adds, which improvements have helped, and what still prevents dependable
four-shape transcription. It includes a process diagram, a progress chart,
and enlarged examples of a recovered square and a missed damaged triangle.
The original six-page technical report remains available in `output/pdf/`.

The user asked for the accuracy explanation to follow the progress chart.
The final order is: overview (1), Copisteria (2), improvements/progress chart
(3), what 3,312 disagreements means (4), scan examples (5), other books (6),
problems/next work (7), interpretation/evidence links (8). Page references and
`output/pdf/README.md` match this order. All eight final pages were rendered
and visually checked; page count, order and accuracy text were checked.

**Readiness:** the project produces MusicXML drafts, but substantial human
correction is still needed. There is no established complete-song accuracy
rate or defensible percentage complete. These results mainly improve the use
of existing pretrained models; they do not demonstrate a newly trained
four-shape recognition model.

**Explain the denominator whenever quoting 3,312:** at the b651 dot/head
checkpoint, the 120 development/diagnostic songs have **3,312 pitch-duration
comparison edits out of 23,988 note entries, or 13.8% disagreement**. The
100-song cohort contributes 2,694 / 19,693; the diagnostic 20 contributes
618 / 4,295. Each voice part uses max(reference notes, predicted notes) in
the denominator. An edit inserts a missing note, deletes an extra note, or
changes a pitch/duration pair. This is about 14 edits per 100 comparison
entries, or 27.6 per song on average, not an estimate of actual proofreading
time. Twenty-two songs have under 5% disagreement, 72 have 5% to under 20%,
and 26 have at least 20%; none has zero pitch-duration disagreement.

**Do not call this 86.2% accurate.** The historical scans and 2025 references
can legitimately differ, and this metric does not fully check timing,
lyrics, repeats, ties or shape semantics. These are development/diagnostic
songs, not a fresh independent test. The chart's 5,931 -> 3,312 (about 44%
fewer edits) starts at an earlier research checkpoint, not raw Copisteria,
and ends at b651, before the c291 conservative safeguard. Cross-book and
severe-damage limitations below remain applicable.

`output/pdf/overview-accuracy-data.json` records the counts and SHA-256 of
the saved b651 `results.json`. `overview-verification.json` records PDF/source
hashes and the final layout checks. `build_project_overview.py` rebuilds the
PDF with ReportLab, Pillow, pypdf, the bundled example crops and macOS
Arial/Georgia fonts; source-hash collection also needs the local archived
reports restored. No recognition rules, models, defaults or gallery changed
during this documentation work.

**Recommended:** proofread 10-20 complete tunes against the same source scans
and measure actual musical errors and correction time. Develop system
grouping and duplicate handling separately, then test frozen changes on
newly selected pages. **Alternative:** use the current output as drafts and
record corrections during normal proofreading, or expand the independently
reviewed frozen challenge set before changing the models.

## Latest task complete: severe damage and all four shapes, rules frozen

Source review, lock, fresh CPU_ONLY capture, both frozen policy replays and
failure reporting are complete. Read
`benchmarks/crossbook-frozen-rules/runs/severe-four-shape-holdout-20261127/REPORT.md`
and `checks.json` first. No rule/model/template/threshold, crop or primary label
changed after inference. Defaults/gallery unchanged. All 16 captures and 32
policy outputs completed with guards; older 534/737/1334/594-artifact seals
were reverified unchanged.

All 300 declared 1850 native pages were screened, yielding no qualifying heads.
The local 1884 book was excluded for seven shapes. The addendum's first 80
available Southern Harmony music pages were screened; printed 31-32 are absent.
The public PDF is Internet Archive's Oberlin item `southernharmonym0000walk`,
catalogued 1835, discovered through IMSLP. A checksum-identical copy is at
`/Users/mark/sacredharp/books/Walker - Southern Harmony (1835) - Oberlin IA.pdf`.
Layered PDF images required the predeclared fixed 300 dpi composite rendering;
all input crops preserve those pixels without enhancement or rescaling.

Eight complete tunes on six pages were locked before inference. Primary
severe coverage is triangle 2, oval 2, square 3, diamond 3. Only **6/10 severe
heads serialize as notes** in baseline/prior/current, both layouts: triangle
1/2, oval 2/2, square 1/3, diamond 2/3. Two severe squares have matched but
unserialized baseline candidates; a fragmented triangle and diamond have no
match under the predeclared rule. All 19 primary damaged heads yield 13 notes;
38 intact controls yield 29 notes. Five ambiguous cases remain separate.
No premarked baseline-emitted head is newly lost, but **no premarked head
exercises the revised abstention**, so these are not predeclared rescues.

The 15 unique abstention candidates (30 paired observations) are exploratory:
main source review supports six possible genuine-head recoveries, while the
independent reviewer supports presence for only two and disputes/cannot judge
four. Six clear new shifted duplicate/artifact notes are retained; two other
mislocalized associations remain uncertain; one duplicate already existed in
prior. Preserve both reviews and disagreements. No pitch/duration/voice
correctness is established by candidate survival. Current has no new removal
versus prior. Two unchanged narrow empty-box removals lose baseline IDs but
nearby actual heads remain emitted; unchanged duplicate-rest removal retains
the source note. Prior/current XML differs in 12/16 configurations, with 28
source-event differences and six cut expansions (Salem 6→7.5 and 6→7;
Devotion 9→11, each layout). These are not claimed timing improvements.

**Failures:** all individual staves detected, but six of eight tunes have
incorrect system grouping in both layouts. Dublin has 36 unequal-part-span
columns in both versions/layouts. Other invariant passes can be vacuous after
one-staff splitting. **Missing coverage:** third severe oval/triangle slots,
all moderate diamonds, several intact-control cells and severe fill/shape
combinations. The lock disclosed inability to certify globally first-three
eligible-head ordering; Converted Thief is an extra control-only page. This
weakens strict preregistration. No post-inference substitution or tuning.

Source materials/lock are under
`source-sets/severe-four-shape-holdout-20261126/` in the crossbook benchmark.
New `run_damage_coverage.py` and `review_damage_coverage.py` retain all failures
and guard inputs/engines. The report and 1,325-hash artifact manifest bind this observed
run. These scans are now development-observed material, not a fresh holdout
for any future revision. Shared repertoire and unknown training provenance
also limit independence.

**Recommended:** keep the rule experimental; develop recognition/system
grouping and duplicate handling separately, then validate any revision on a
new source-first holdout. **Alternative:** keep both engines frozen and expand
independently adjudicated missing shape/fill coverage.

## Latest task complete: source-first damaged heads from the 1850 printing

The user requested a fresh damaged-head sample from another printing, using
the unchanged frozen rules without tuning. The public VEMP/Auburn scan is
catalogued as the Sacred Harp second edition, first printing, 1850. Its catalog
sheet supports that attribution; the historical title-page date is damaged.
`PRESELECTION.md` was recorded before viewing its pixels: screen printed pages
27-66 in order, stopping after six qualifying pages or page 66. The forty-page
screen found three likely-damage pages, plus an initially qualifying but
disputed page retained explicitly as a secondary ambiguous case. No quota or
post-inference selection was forced. Every complete tune on those four pages
is included: **six tunes, 12 configurations**. Source-only labels, exact native
crops, PDF provenance and the pre-inference SHA lock are under
`benchmarks/crossbook-frozen-rules/source-sets/1850-damaged-head-holdout-20261126/`.

The sealed run is
`benchmarks/crossbook-frozen-rules/runs/1850-damaged-head-holdout-20261126/`.
Read `SOURCE_REVIEW.md` and inspect `annotated-source-contact.png` before drawing
conclusions. **All three likely damaged heads survive baseline, prior b651 and
current c291 in both layouts**: Dublin's weak/missing square rim, Distress's
broken upper oval rim, Portugal's broken lower-left oval rim. One disputed
Lenox oval also survives but is excluded from the primary denominator.

**The revised abstention mechanism never triggers.** Zero abstentions/removals;
all 12 prior/current score XML pairs are byte-identical. This is source-head
survival evidence, not a demonstrated rescue or broad generalization. Of eight
intact controls, seven are notes in all stages; Lenox C1 is a real hollow
triangle classified/serialized as `rest_half` by every stage, in both layouts.
An independent source-only identity check agrees with the locked head label.
Distress also has a two-of-three-staff baseline layout failure, retained in the
sample. No baseline emitted note ID is lost. All 12 equal-part-span checks pass
in both policy versions; this does not establish correct pitch/voice/rhythm.

All **12 fresh CPU_ONLY captures and 24 policy outputs** completed with guards.
Both engine trees and fixed meter templates match the earlier 1860 run exactly.
No recognition/rule/threshold/annotation/crop changed after inference; no
reference XML was opened or PD/F1 score used. New `run_damaged_sample.py` handles
workspace-relative source sets and pre-inference selection locks only;
`review_damaged_sample.py` checks actual serialized source IDs and retains
baseline class mistakes. One analysis path-normalization failure was corrected
before writing its result; generation was not retried. The run binds **534
artifact hashes**, including the source PDF, inspected pixels, selections,
outputs, models, frozen code and reports. Defaults and gallery remain unchanged.

**Recommended:** keep the stage experimental and expand a source-first frozen
challenge set to severe damage and all four shapes. **Alternative:** audit the
baseline hollow-triangle/rest and missing-staff failures as separate development
work, then reserve another fresh holdout for any revision. These 1850 cases are
now observed material; shared repertoire/printing plates and unknown model
training provenance prevent a strong independence claim.

## Latest task complete: conservative abstention and untouched 1860 test

The requested damaged-head abstention revision is implemented. The live rule
now rejects a broader line/blemish candidate only when its ink is completely
explained by thin staff lines independently supported on both sides. **Any
unexplained fragment causes abstention**; no rim classifier, fragment-size
cutoff, book/title/ID exception or held-out tuning was added. The original narrow
empty-box, repeat-dot and beam rules remain unchanged. Abstentions are logged in
`rhythm_resolution_details.source_head_abstentions`.

Frozen revised engine:
`benchmarks/crossbook-frozen-rules/engines/damaged-head-abstention-c291185f6a20/`
(152 Python files). Prior is the unchanged b651 checkpoint. **214 tests pass**;
development recovery preserves **18 protected heads / 17 reviewed durations**,
Ninety-Third Psalm's printed 3/4 with 14 flagged six-quarter bars, and Lenox,
Ragan and Duane controls. Aylesbury 186 and selected Kedron 219 survive. Some
known artifacts are intentionally retained: **Jackson c1 is unresolved again**.
The earlier five-bar source-correctness audit is not all satisfied by this more
conservative version; do not hide that tradeoff.

Untouched 1860 evaluation is complete and sealed:
`benchmarks/crossbook-frozen-rules/runs/1860-abstention-holdout-20261126/`.
Read `SOURCE_REVIEW.md` first, then `REPORT.md` / `checks.json`. All 19 previously
selected source crops were retained, both layouts: **38 fresh CPU_ONLY captures
and 76 policy outputs**. All source/code/model/template hash guards passed
before scoring. Source judgments were locked in `source-review.json` with a
pre-score SHA before opening reference scores. Rules were never retuned.

**Result and limit:** zero current non-head deletions; four artifact objects
retained in both layouts (eight abstentions). No genuine held-out damaged head
was rescued or deleted, so **new damaged-head protection was not directly
exercised**. This is not broad generalization evidence. PD default **898 → 901**,
cleaned **1139 → 1143** against the prior policy, total +7 edits. PD better/tied/
worse **0/32/6**, F1 **0/33/5**. Supplication c12 expands **4 → 5.5**. Three
unequal-span configurations remain in both versions (Hallelujah both layouts,
Ocean default). The native baseline has higher F1 than either full applied
rhythm stage in this sample. All failures remain included.

The holdout manifest, engine mapping and predeclared protocol are under
`benchmarks/crossbook-frozen-rules/source-sets/1860-abstention-holdout-20261126/`.
Use `run_abstention_holdout.py` for a new tagged capture/replay; score only after
both completion guards, using `score_results.py`. The run's 737-hash manifest
binds outputs, review, protocol and engines. Earlier 594/1334-hash cross-book
runs and all JPK manifests remain intact. Defaults and gallery are unchanged.

**Recommended:** keep the stage opt-in and predeclare a fresh source set that
actually contains damaged heads from another printing before claiming transfer.
These 1860 cases are now observed data for any further revision. **Alternative:**
use the conservative version with manual review of abstentions/unresolved bars,
accepting retained artifacts. Do not tune this version to improve the 1860 scores.

## Earlier frozen cross-book evaluation

The frozen rules have now been tested on **26 matched tunes per book** from the
1870 MTS and J. L. White 1911 EMU printings: **52 crops / 104 configurations**,
both layout variants. The sealed expanded test is
`benchmarks/crossbook-frozen-rules/runs/expanded52-frozen-dot-head-20261126/`.
Read `SOURCE_REVIEW.md` first, then `REPORT.md`, `results.json`, and `checks.json`.
The earlier seven-tune pilot remains sealed at
`benchmarks/crossbook-frozen-rules/runs/pilot14-frozen-dot-head-20261126/`.

**The new line/blemish rejection deletes a genuine damaged notehead in EMU
Aylesbury (186), in both layouts.** A surviving curved head rim and downward stem
are visible despite an open/damaged counter. Across 12 distinct new rejection
objects (22 occurrences), source review confirms **10 non-head boxes, one genuine
head loss, and one localization ambiguity** (1870 Kedron 219; box below a real
hollow triangle). Do not call the Kedron deletion a success. New dot/short-beam
repairs made no emitted-output changes; their cross-book transfer remains
unestablished. The full postprocessor on baseline event pools fails equal
part-span checks in **16 configurations**, identically in both snapshots (14
default, two cleaned; cleaned failures are Elder in each printing).

The other chat prepared a 52-crop manifest (26 matched tunes per book), with
selection before new inference. Its immutable copy is
`benchmarks/crossbook-frozen-rules/source-sets/two-books-expanded-20261126/manifest.json`.
All **104 baseline captures and 208 frozen-policy outputs completed** before
reference scoring; all code/source hash guards passed. Twenty-eight pilot
captures were reused by hash and 76 new CPU_ONLY cases were generated.
Against the earlier rhythm snapshot, PD better/tied/worse is **11/92/1**, F1
**18/85/1**. On the 76 added configurations only, PD is **9/67/0** and F1
**16/60/0**. These metrics do not override the confirmed source loss.

Cleaned-layout all-26 PD edits: 1870 baseline/prior/current **1607/1561/1560**;
1911 EMU **1866/1902/1900**. Reference editions differ. The baseline event pools
do not reproduce the earlier JPK missing-head/source-system-reflow stages, so
this is specifically a frozen postprocessing transfer test. Four adapter/scoring
tests pass. The expanded artifact manifest binds **1334 hashes**, the pilot 594;
all older historical/JPK manifests remain intact. No rules were retuned.

Use `run_expanded_rules.py` for capture/replay and `score_results.py` only after
both policy completion guards exist. The original pilot adapter remains frozen;
its first scoring function stopped on the timing invariant, so use the separate
scorer, which records failures rather than hiding them. Source-change extraction
refuses sealed runs. The separately supplied 1860 source was not used here.

**Recommended:** keep the stage opt-in; make line/blemish rejection abstain on
damaged heads and resolve Kedron's localization. These diagnosed cases are now
development material; validate a revision on a fresh untouched sample, such as
selected 1860 material. **Alternative:** predeclare a source set specifically
exercising augmentation/repeat dots and short beams with the unchanged snapshots.
Defaults and gallery remain unchanged; broad enablement is not ready.

## JPK checkpoint: general dot and false-head fixes

The requested general fixes and new frozen 120-song batch are complete and
validated at
`benchmarks/sacred-harp-1911/experiments/rhythm-resolution/dot-head-evidence-20261126-b6512a5f402d/`.
Read `COMPARISON.md` for the direct comparison with `final-a17498fc863d`;
`REPORT.md` compares with the older source-timing/proposal parents.

**Results against the prior rhythm checkpoint:** PD disagreement **3333 → 3312**
(development 2712 → 2694; diagnostic 621 → 618). Time-aware F1
**.6640 → .6919** and **.6637 → .6642**. PD better/tied/worse **13/106/1**;
timing better/tied/worse **17/102/1**. Unresolved columns **87 → 80 / 2104**;
voice decisions **153 → 146**. Fourteen columns remain Ninety-Third Psalm's
printed 3/4/six-quarter conflict; **66 other columns** need source review.

The five locally adjudicated bars pass: Done With The World c0 = 2, Elder c2 = 6,
Jackson c1 = 4, Midnight Cry c7 = 2, Primrose c5 = 4. **Elder c8 remains flagged
at 7**, retaining its real dot on 361 and visible stemless head 365. All 21
rejected note interpretations have positive source non-head evidence (19 are
additional to the prior checkpoint); this is not newly recovered note count.

**Sole new regression:** Fillmore **+1 PD, -.00254 F1**, c18 cut 17/4 → 4.
`regression-source-review.json` and `fillmore-regression-source.png` confirm
that rejected 600 is staff-line/blemish ink below the real hollow square.
Keep the rejection. The alto still has competing note interpretations and
unresolved source durations (encoded end 13/4 before padding); a fitting bar
does not certify source rhythm. The regression stays included and documented.

**Validation:** **205 tests pass**, all 120 predictions finished before scoring,
and the code hash guard passed. All **151 frozen Python files** stayed unchanged.
All **8334 part-measures**, **18 protected heads**, **17 reviewed durations**,
meter/transition/whole/stub controls, Lenox/Ragan/Duane zero overflow, and the
Ninety-Third Psalm decision pass. The new manifest binds **377 files**; all prior
current/source-timing/proposal manifest hashes and file sets remain intact.
Defaults and gallery are unchanged; broad enablement remains unready.

Rules use source geometry, relative contrast and staff-space measurements, with
no titles, case IDs, reference counts or target bar lengths. Dotted chords and
separate augmentation dots beside repeats have negative controls. The original
`source_duration_options.py` is byte-identical to the prior checkpoint; the new
behavior stays opt-in. An early overbroad dot rule was rejected before generation;
its diagnostic output is clearly marked under the audit's implementation preflight.
Cross-book transfer has not been validated.

**Recommended:** source-review Fillmore's remaining rhythm/duplicate-head
interpretations and seek stronger evidence for Elder c8, then audit the remaining
regressions/source inventory. Evaluate frozen code on other four-shape books
before broad enablement. **Alternative:** retain the stage quarantined and begin
with a small independent cross-book control set. Holy Manna's rare layout remains
deferred; the general short-beam rule runs uniformly on the included batch.

## Prior checkpoint and its historical next-work notes

The latest work, **“resolve Lenox/Ragan and the remaining rhythm failures next,”** has reached a validated **handoff checkpoint** at `benchmarks/sacred-harp-1911/experiments/rhythm-resolution/final-a17498fc863d/REPORT.md`. The user asked to get to a handoff place and start a fresh chat. **The stage remains opt-in, and broad enablement is NOT ready.** Production defaults and the gallery remain unchanged. All 120 predictions were generated with frozen code before reference scoring; the end-of-generation hash guard passed.

**Main results:** Lenox, Ragan and Duane Street have zero overflowing shared columns (20/10/18 columns). This is a capacity check, not complete source adjudication. Unresolved columns fall **157 → 87 / 2104**; unresolved voice decisions **327 → 153**. **Fourteen** remaining columns are Ninety-Third Psalm’s printed meter/value conflict. The user explicitly chose **“Preserve printed 3/4 and flag the irregular bars.”** Keep 3/4, retain its six-quarter source values, and never silently normalize it to 3/2. The other **73 columns** require source review. Weeping Savior `1911-33t-weeping-savior` correctly preserves source 4/4 after rejecting a weak two-staff 3/4 template fallback.

**Scores and regressions:** PD disagreement **3500 → 3333 edits** (development 100: 2840 → 2712; diagnostic 20: 660 → 621); **67 better / 41 tie / 12 worse** against source-timing. Time-aware F1 .6426 → .6640 and .5783 → .6637. There are **26 timing regressions; 30 songs** in the union of metric regressions. All remain included. Lenox 19 → 15 PD, F1 .029 → .957; Ragan 27 → 22, .335 → .890; Duane 56 → 52, .088 → .834. Ragan still has **+1 PD** against the earlier proposal-rhythm parent 21, despite fixing its overflowing bars. All 120 songs are development/diagnostic and reference editions differ; disagreement is not pure accuracy.

**Validation:** **188 tests pass**. All 18 original recovered physical heads remain; all 17 adjudicated durations match. Protection M033 remains unadjudicated. All 8334 part-measures match their selected common cut; no retained physical heads are clipped. Two prior pitched objects are now rejected by positive source evidence: **Ocean 555 is a beam segment; Duane 519 is an empty box**. All other prior pitched ID/pitch sets remain. Four duplicate serialized copies and 232 note/rest interpretations of already emitted heads are removed; this is not a count of newly recovered source notes. Source geometry/staff identity, local accidentals/marks and normalized XML/trace durations pass. Prior proposal-rhythm 399 and source-timing 372 artifact hashes/file sets are unchanged. Five opening-meter checks, Primrose/Greenland transitions, Vermont/Weary controls, Golden P1M2 and Salem pass.

**Recommended next work:** audit the largest timing regressions using `regression-audit-queue.json` **before** broader enablement. Start with Done With The World (opening cut 2 → 3.5), Elder (6 → 7), Jackson (4 → 5), The Midnight Cry (2 → 3), Primrose (4 → 4.5). Source-backed duration repairs retained in otherwise unresolved voices can expand a shared cut and shift later onsets. Review the source values/dots, missing events and bar boundaries together; do not repair scores by clipping heads or changing printed meter. Causes for these regressions remain unadjudicated. Then use `residual-source-inventory.json` for 73 other source-review columns; Alabama has 6, Newburgh/Providence/Fillmore/Harmony/Vermont 3 each. Defer Holy Manna’s unusual layout as previously requested. **Alternative:** keep the stage quarantined and narrow the next experiment to the Lenox/Ragan fixes.

**Files:** `run_rhythm_resolution.py` creates the frozen/provenance-bound batch; `source_rhythm_resolution.py`, `attached_stem_evidence.py`, `beam_region_evidence.py` supply source-only constraints. `source_bar_fit.py` refines clocks/fallback with opt-in `refine_timing`; `run_source_timing_recovery.recover(...,rhythm_resolution=True)` enables the policy. The default is false. `summarize_rhythm_resolution.py` validates outputs and reports scores/regressions; `verify_source_timing_cases.py` validates source cases/user meter decision and parent manifests. No title/case IDs or reference counts enter prediction rules. Diagnostic source review and the Ragan 321 local detector probe are saved; the probe favors eighth for a matching refined box but was **not used in prediction**, and the exact source value is not yet adjudicated. Full generation uses cached recognition/source pixels, without new neural inference. A diagnostic CoreML source-crop check ran separately with CPU_ONLY.

The final directory contains all 120 XML/trace pairs, generation provenance/code snapshots/templates, results, validation, tests, source cases, source controls, residual/regression queues and the final artifact manifest. Earlier rhythm-resolution pilots/full/guarded/candidate/resolved are diagnostic only; some have rejected overbroad rules or mid-run code changes. Never overwrite them. Scratch history is `diagnostics/rhythm-resolution/WORKING.md`; a copyable next-chat prompt is `diagnostics/rhythm-resolution/NEXT_CHAT.md`. Use **`copisteria/.venv/bin/python`** and exact `run_local_recovery.samples()` input paths.

## Initial timing regression source audit (2026-11-26)

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

The general evidence fixes and new frozen batch are now complete, as recorded
in the current-checkpoint section above. The original source audit remains
available as provenance for those fixes.

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

> Read `/Users/mark/code/sh_omr/HANDOFF.md` and the new dot-head-evidence checkpoint's COMPARISON.md, regression-source-review.json, and residual-source-inventory.json. Review Fillmore's remaining source rhythm/duplicate-head interpretations and Elder's ambiguous c8, then the remaining ordinary-layout failures. Keep the stage opt-in, retain Ninety-Third Psalm's printed 3/4 with flagged irregular bars, and protect the 18 recovered heads and 17 reviewed durations. Do not restore proven non-heads to improve reference agreement. Cross-book transfer remains unvalidated.

**Recommended:** start a fresh chat with that prompt. **Alternative:** remain in this chat for a narrowly scoped regression source review.
