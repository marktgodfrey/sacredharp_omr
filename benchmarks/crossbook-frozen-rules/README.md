# Frozen rhythm rules across historical printings

The severe four-shape expansion is complete with unchanged rules: eight tunes,
16 fresh captures and 32 frozen-policy outputs. **Only 6/10 premarked severe
heads serialize as notes**, identically in baseline/prior/current. The remaining
four are recognition/output failures. System grouping fails in six of eight
tunes; Dublin retains unequal spans in both policies. Exploratory abstentions
include possible real-head recoveries, reviewer disagreements and newly retained
shifted duplicates. This does not establish broad generalization.

- [Severe coverage, failures, gaps and provenance](runs/severe-four-shape-holdout-20261127/REPORT.md)
- [Machine-readable checks](runs/severe-four-shape-holdout-20261127/checks.json)
- [Locked source labels and declared deviations](source-sets/severe-four-shape-holdout-20261126/selection.json)
- [Every abstention/removal source panel](runs/severe-four-shape-holdout-20261127/source-audit-artifacts/all-policy-decisions.png)

The third severe oval/triangle slots and moderate diamonds remain unfilled;
several fill/shape cells and controls are missing. No labels, crops, engines or
thresholds changed after inference. Use the new `run_damage_coverage.py` for
guarded source-manifest runs and `review_damage_coverage.py` for failure-inclusive
analysis. **Recommended:** keep this experimental and address observed layout /
recognition / duplicate failures in development before a new independent holdout.
**Alternative:** keep the rules frozen and expand independently adjudicated
missing source coverage. These cases are now observed material.

The source-first **1850 Auburn printing** test is now complete: six tunes on
four selected pages, both layouts. Three premarked likely damaged heads survive
baseline/prior/current; one disputed oval is reported separately. **Zero revised
abstentions occur, and all 12 prior/current score XML pairs are byte-identical.**
This demonstrates survival on the selected heads, not a rescue by the fix.
One intact hollow triangle remains misclassified as a rest, and Distress keeps
a baseline missing-staff failure. No rule or selection was tuned to the result.

- [1850 source review and limits](runs/1850-damaged-head-holdout-20261126/SOURCE_REVIEW.md)
- [Every source-to-prediction match](runs/1850-damaged-head-holdout-20261126/annotated-source-contact.png)
- [Locked source-first selection](source-sets/1850-damaged-head-holdout-20261126/selection.json)
- [Preselection plan](source-sets/1850-damaged-head-holdout-20261126/PRESELECTION.md)

Use `run_damaged_sample.py` with a workspace-relative `--source-set` and a new
`--tag` for capture/replay; `review_damaged_sample.py` performs source-only
analysis after completion. The 534-hash sealed run includes models and the
original public PDF. Broader enablement remains unsupported. **Recommended:**
expand predeclared damage coverage without changing the frozen rules.
**Alternative:** separately audit baseline class/layout failures, reserving
fresh material to validate any revision.

The latest revision makes damaged-head abstention conservative: any unexplained
ink is retained rather than treated as proof of no head. It passes 214 development
tests and protects the known Aylesbury/Kedron cases. The untouched 1860 test is
complete: **19 crops / 38 configurations**, zero non-head deletions, four
artifacts retained, and PD disagreement **+7 edits** across both layouts. No new
genuine damaged-head protection case was exercised, so transfer remains
unestablished. No rule was retuned on those outcomes.

- [1860 source review and limits](runs/1860-abstention-holdout-20261126/SOURCE_REVIEW.md)
- [1860 metrics](runs/1860-abstention-holdout-20261126/REPORT.md)
- [Predeclared holdout protocol](source-sets/1860-abstention-holdout-20261126/PROTOCOL.md)

The current engine is `engines/damaged-head-abstention-c291185f6a20/`. Use
`run_abstention_holdout.py` for a new tagged run. These observed 1860 cases cannot
be described as untouched validation for a later revision. The experimental
stage remains opt-in; broad enablement is not supported.

## Earlier unchanged-rule transfer test

The completed evaluation uses 26 matched tunes each from the 1870 Sacred Harp
(MTS) and J. L. White 1911 Sacred Harp (EMU), both layout settings: 52 crops and
104 configurations. The selection was copied from the other chat's reviewed
manifest before new inference. All outcomes remain included.

**The new line/blemish filter fails a physical-source check.** It deletes a
genuine damaged Aylesbury head. The expanded source review confirms ten
non-head boxes, one genuine-head loss, and one localization ambiguity. New dot
and short-beam effects were not exercised in the emitted outputs. The stage
remains opt-in; no rule was retuned on this evaluation.

- [Expanded source review and conclusion](runs/expanded52-frozen-dot-head-20261126/SOURCE_REVIEW.md)
- [Expanded metrics](runs/expanded52-frozen-dot-head-20261126/REPORT.md)
- [Expanded source decisions](runs/expanded52-frozen-dot-head-20261126/source-review.json)
- [Initial seven-tune pilot](runs/pilot14-frozen-dot-head-20261126/SOURCE_REVIEW.md)
- [Immutable expanded selection](source-sets/two-books-expanded-20261126/manifest.json)

Generation uses frozen rule/Copisteria snapshots and frozen 1911 JPK meter
templates. Both rule versions consume identical baseline readings. The 28 pilot
captures match the earlier sealed pilot; expanded capture reuses them only when
source/model/code/output hashes match and performs 76 additional CPU_ONLY runs.
Neither reference XML nor manual source counts/meters/voice orders enters
prediction. Voice alignment and edition-absent alto exclusion are scoring only.

The test applies postprocessing to baseline event pools; it does not reproduce
the JPK-specific upstream missing-head and system-reflow stages. Older-reference
edition differences remain in scores. The full applied stage has 16 unequal-span
configurations in both snapshots, including two with cleaned layout.

Use `run_expanded_rules.py` for capture/replay in a **new tagged directory**.
Use `score_results.py` only after both completion guards, then
`extract_source_changes.py` before sealing. Reproduction commands and manual
source-review limits are in the expanded report. CoreML compilation may require
sandbox escalation. Do not rerun the original adapter's scoring phase: its
equal-span assertion intentionally exposed a portability failure; the separate
analysis retains that failure as data.

Generated runs are ignored by Git, matching the existing benchmark convention.
Their artifact manifests include output/source/reference hashes, frozen engine
code and templates, and copied analysis/adapter source. No defaults or gallery
were changed.

**Recommended:** rework damaged-head abstention and source localization, then
test a revision on untouched material. **Alternative:** collect a predeclared
cross-book source set that exercises dot/repeat and short-beam mechanisms.
