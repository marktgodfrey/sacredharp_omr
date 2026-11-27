# Rhythm resolution checkpoint — 2026-11-26

This is a validated **opt-in checkpoint**, not a broad-enablement pass. Generation used frozen code and saved all 120 predictions before opening reference transcriptions. Production defaults and the gallery remain unchanged.

- **Lenox, Ragan and Duane Street:** no overflowing shared columns (20, 10 and 18 columns respectively). This verifies capacity, not exact source transcription. Lenox PD edits 19 → 15, timing F1 .029 → .957; Ragan 27 → 22, .335 → .890; Duane Street 56 → 52, .088 → .834. Ragan is still +1 PD edit against the earlier proposal-rhythm parent (21), so its complete source rhythm is not adjudicated.
- **Remaining fits:** 157 → **87 / 2104 shared columns**, 327 → **153 unresolved voice decisions**. Fourteen columns deliberately preserve Ninety-Third Psalm’s printed **3/4**, retaining six-quarter source values and flagging the irregular bars per the user’s explicit decision. The other **73 columns** require source review.
- **Disagreement:** 3500 → **3333 PD edits** (development100 2840 → 2712; diagnostic20 660 → 621). Time-aware F1 .6426 → .6640 and .5783 → .6637. PD better/tie/worse: **67 / 41 / 12**. There are **26 timing regressions**, **30 songs** in the union against the previous source-timing run. These are development/diagnostic comparisons against a different edition, not population accuracy estimates.
- **Integrity:** **188 tests pass**; all 18 reviewed recovered heads remain; all 17 adjudicated durations match. All **8334 part-measures** have the selected common span, with no clipping of retained physical notes. All other prior pitched IDs/pitches remain except two source-proven non-head detections: Ocean 555 (beam stroke) and Duane 519 (empty box). Four repeated serialized copies and 232 duplicate note/rest interpretations were removed. Prior 399- and 372-entry artifact manifests/file sets are unchanged.

The generic fixes suppress rest interpretations of already emitted physical heads, separate vertical repeat dots from augmentation dots, protect hollow heads and short stem stubs, recover source-supported durations/tuplets, and require pixel plus direct-reading support for weak printed beams. Opening meter fallback now abstains from overriding a saved meter on only two of four staves; this preserves Weeping Savior (33t)’s printed 4/4. Previous meter transitions, Golden Harp’s two-quarter bar and Salem’s merged four-quarter bar pass source-case checks.

**Next review priority:** audit the largest timing regressions before enabling the stage. Done With The World’s opening common cut changes 2 → 3.5 after a hollow-head repair; Elder has 6 → 7 cuts; Jackson 4 → 5; The Midnight Cry 2 → 3; Primrose 4 → 4.5. A source-backed duration repair in an otherwise unresolved voice can expand a cut and shift every later onset. Inspect source values, dots, missing events and boundaries together; do not clip real heads or silently change meters to improve a reference score. No cause is yet adjudicated for these regressions.

Use [regression-audit-queue.json](regression-audit-queue.json) for the 30-song queue and changed-cut provenance; [residual-source-inventory.json](residual-source-inventory.json) for all 87 flagged columns with exact source inputs, boxes and duration options. [source-case-checks.json](source-case-checks.json) records the meter/bar checks and user decision. [checks.json](checks.json) records tests. [source-review.json](source-review.json) and [source-controls.jpg](source-controls.jpg) contain purposeful source controls. `ragan-321-diagnostic-probe.json` is a provenance-bound local detector check; it was not used in prediction. Its refined box matches the source head and favors eighth, but the source value remains a review candidate.

Earlier pilot/full/guarded/candidate/resolved trials remain diagnostic, including runs with rejected dot/hollow-head rules or code modified during generation. Use this final directory for the stable checkpoint.

## Detailed validation

Validated **120 songs**. Prior note IDs and pitches are retained except 2 source-supported non-head removals. Source geometry/staff, normalized durations, retained note annotations, and selected part-measure spans passed. No retained physical notes were clipped or dropped.

| Dataset | Stage | Songs | PD edit distance | Time aware F1 |
|---|---|---:|---:|---:|
| development100 | previous | 100 | 2840 | 0.643 |
| development100 | proposal_baseline | 100 | 2984 | 0.574 |
| development100 | current | 100 | 2712 | 0.664 |
| diagnostic20 | previous | 20 | 660 | 0.578 |
| diagnostic20 | proposal_baseline | 20 | 666 | 0.570 |
| diagnostic20 | current | 20 | 621 | 0.664 |

PD is pitch-duration edit distance; lower is better. Time aware F1 uses the exact event multiset. Per-song regressions against either comparison stage are listed in `validation.json`.

Unresolved timing is reported separately: **87 shared columns** and **153 voice decisions**. Removed serialized duplicate occurrences: **4**; removed mixed note/rest same-head conflicts: **232**.

The established source review retains **18 of 18 physical notes** and matches **17 of 17 checkable source durations**.

## Regressions

- Clamanda (`1911-Origin-JPK-0052`) vs previous: PD +0; time-aware F1 -0.004.
- Clamanda (`1911-Origin-JPK-0052`) vs proposal_baseline: PD +0; time-aware F1 -0.004.
- Holy Manna (`1911-Origin-JPK-0069`) vs previous: PD -2; time-aware F1 -0.249.
- Holy Manna (`1911-Origin-JPK-0069`) vs proposal_baseline: PD -2; time-aware F1 -0.249.
- Ninety-Third Psalm (`1911-31t-ninety-third-psalm`) vs proposal_baseline: PD +0; time-aware F1 -0.102.
- Primrose (`1911-47t-primrose`) vs previous: PD -2; time-aware F1 -0.502.
- Primrose (`1911-47t-primrose`) vs proposal_baseline: PD -2; time-aware F1 -0.502.
- Parting Hand (`1911-s0072-parting-hand`) vs previous: PD -1; time-aware F1 -0.351.
- Parting Hand (`1911-s0072-parting-hand`) vs proposal_baseline: PD -1; time-aware F1 -0.351.
- Mulberry Grove (`1911-s0104-mulberry-grove`) vs previous: PD +2; time-aware F1 -0.011.
- Mulberry Grove (`1911-s0104-mulberry-grove`) vs proposal_baseline: PD +2; time-aware F1 -0.011.
- Dull Care (`1911-s0108-dull-care`) vs previous: PD +1; time-aware F1 +0.000.
- Dull Care (`1911-s0108-dull-care`) vs proposal_baseline: PD +1; time-aware F1 +0.000.
- The Midnight Cry (`1911-s0124-the-midnight-cry`) vs previous: PD +1; time-aware F1 -0.547.
- The Midnight Cry (`1911-s0124-the-midnight-cry`) vs proposal_baseline: PD +1; time-aware F1 -0.547.
- All Is Well (`1911-s0132-all-is-well`) vs previous: PD +3; time-aware F1 -0.009.
- All Is Well (`1911-s0132-all-is-well`) vs proposal_baseline: PD +3; time-aware F1 -0.009.
- Stratfield (`1911-s0152-stratfield`) vs previous: PD +1; time-aware F1 +0.000.
- Stratfield (`1911-s0152-stratfield`) vs proposal_baseline: PD +1; time-aware F1 +0.000.
- Hallelujah (`1911-s0156-hallelujah`) vs previous: PD +4; time-aware F1 +0.000.
- Hallelujah (`1911-s0156-hallelujah`) vs proposal_baseline: PD +3; time-aware F1 +0.005.
- Exhilaration (`1911-s0180-exhilaration`) vs proposal_baseline: PD +0; time-aware F1 -0.003.
- New Lebanon (`1911-s0212-new-lebanon`) vs previous: PD -5; time-aware F1 -0.014.
- New Lebanon (`1911-s0212-new-lebanon`) vs proposal_baseline: PD -5; time-aware F1 -0.011.
- Repentance (`1911-s0224-repentance`) vs previous: PD +0; time-aware F1 -0.147.
- Repentance (`1911-s0224-repentance`) vs proposal_baseline: PD -2; time-aware F1 -0.070.
- Ocean (`1911-s0232-ocean`) vs previous: PD +2; time-aware F1 -0.339.
- Ocean (`1911-s0232-ocean`) vs proposal_baseline: PD +2; time-aware F1 -0.339.
- Victoria (`1911-s0304-victoria`) vs previous: PD -1; time-aware F1 -0.003.
- Victoria (`1911-s0304-victoria`) vs proposal_baseline: PD -1; time-aware F1 -0.003.
- The American Star (`1911-s0360-the-american-star`) vs previous: PD -3; time-aware F1 -0.214.
- The American Star (`1911-s0360-the-american-star`) vs proposal_baseline: PD -7; time-aware F1 -0.179.
- Oh, Sing With Me! (`1911-s0388-oh-sing-with-me`) vs previous: PD +0; time-aware F1 -0.055.
- Oh, Sing With Me! (`1911-s0388-oh-sing-with-me`) vs proposal_baseline: PD +0; time-aware F1 -0.055.
- New Prospect (`1911-s0404-new-prospect`) vs previous: PD -2; time-aware F1 -0.376.
- New Prospect (`1911-s0404-new-prospect`) vs proposal_baseline: PD -2; time-aware F1 -0.376.
- Protection (`1911-s0416-protection`) vs previous: PD +1; time-aware F1 +0.195.
- Protection (`1911-s0416-protection`) vs proposal_baseline: PD +1; time-aware F1 +0.191.
- Mutual Love (`1911-s0444-mutual-love`) vs proposal_baseline: PD -10; time-aware F1 -0.026.
- Elder (`1911-s0464-elder`) vs previous: PD +0; time-aware F1 -0.705.
- Elder (`1911-s0464-elder`) vs proposal_baseline: PD +0; time-aware F1 -0.705.
- Rest For The Weary (`1911-s0488-rest-for-the-weary`) vs previous: PD -1; time-aware F1 -0.271.
- Rest For The Weary (`1911-s0488-rest-for-the-weary`) vs proposal_baseline: PD -1; time-aware F1 -0.038.
- Christian’s Hope (`1911-s0520-christian-s-hope`) vs previous: PD +2; time-aware F1 -0.004.
- Christian’s Hope (`1911-s0520-christian-s-hope`) vs proposal_baseline: PD +3; time-aware F1 +0.125.
- Jackson (`1911-s0532-jackson`) vs previous: PD -3; time-aware F1 -0.602.
- Jackson (`1911-s0532-jackson`) vs proposal_baseline: PD -3; time-aware F1 -0.602.
- Burdette (`1911-s0536-burdette`) vs previous: PD -2; time-aware F1 -0.383.
- Burdette (`1911-s0536-burdette`) vs proposal_baseline: PD -2; time-aware F1 -0.383.
- The Converted Thief (`1911-s0054-the-converted-thief`) vs previous: PD +1; time-aware F1 -0.004.
- The Converted Thief (`1911-s0054-the-converted-thief`) vs proposal_baseline: PD +1; time-aware F1 +0.226.
- Albion (`1911-s0062-albion`) vs previous: PD +1; time-aware F1 -0.007.
- Albion (`1911-s0062-albion`) vs proposal_baseline: PD +1; time-aware F1 -0.007.
- Desire For Piety (`1911-s0086-desire-for-piety`) vs proposal_baseline: PD +0; time-aware F1 -0.016.
- Done With The World (`1911-s0098-done-with-the-world`) vs previous: PD -1; time-aware F1 -0.851.
- Done With The World (`1911-s0098-done-with-the-world`) vs proposal_baseline: PD -1; time-aware F1 -0.636.
- Supplication (`1911-holdout-s0055-supplication`) vs previous: PD -2; time-aware F1 -0.014.
- The Promised Land (`1911-holdout-s0138-the-promised-land`) vs previous: PD +1; time-aware F1 -0.409.
- Harmony (`1911-holdout-s0182-harmony`) vs previous: PD -1; time-aware F1 -0.014.
- Harmony (`1911-holdout-s0182-harmony`) vs proposal_baseline: PD -1; time-aware F1 -0.165.
- Ragan (`1911-holdout-s0186-ragan`) vs proposal_baseline: PD +1; time-aware F1 +0.297.
- Schenectady (`1911-holdout-s0202-schenectady`) vs previous: PD +0; time-aware F1 -0.003.
- Schenectady (`1911-holdout-s0202-schenectady`) vs proposal_baseline: PD +0; time-aware F1 -0.003.

All 120 songs are development/diagnostic examples. Scores measure disagreement with a different edition, rather than recognition accuracy. This stage remains opt-in; defaults and gallery are unchanged.

**Recommended:** inspect the per-song regressions and unresolved voice decisions before expanding the run.
**Alternative:** retain this as a bounded opt-in stage and collect additional source-reviewed cases.

[Validation details](validation.json); [run results](results.json).
