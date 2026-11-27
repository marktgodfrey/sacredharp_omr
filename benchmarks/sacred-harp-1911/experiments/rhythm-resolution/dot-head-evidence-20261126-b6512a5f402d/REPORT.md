# Rhythm resolution validation

Validated **120 songs**. Prior note IDs and pitches are retained except 21 source-supported non-head removals. Source geometry/staff, normalized durations, retained note annotations, and selected part-measure spans passed. No retained physical notes were clipped or dropped.

| Dataset | Stage | Songs | PD edit distance | Time aware F1 |
|---|---|---:|---:|---:|
| development100 | previous | 100 | 2840 | 0.643 |
| development100 | proposal_baseline | 100 | 2984 | 0.574 |
| development100 | current | 100 | 2694 | 0.692 |
| diagnostic20 | previous | 20 | 660 | 0.578 |
| diagnostic20 | proposal_baseline | 20 | 666 | 0.570 |
| diagnostic20 | current | 20 | 618 | 0.664 |

PD is pitch-duration edit distance; lower is better. Time aware F1 uses the exact event multiset. Per-song regressions against either comparison stage are listed in `validation.json`.

Unresolved timing is reported separately: **80 shared columns** and **146 voice decisions**. Removed serialized duplicate occurrences: **4**; removed mixed note/rest same-head conflicts: **232**.

The established source review retains **18 of 18 physical notes** and matches **17 of 17 checkable source durations**.

## Regressions

- Clamanda (`1911-Origin-JPK-0052`) vs previous: PD +0; time-aware F1 -0.004.
- Clamanda (`1911-Origin-JPK-0052`) vs proposal_baseline: PD +0; time-aware F1 -0.004.
- Ninety-Third Psalm (`1911-31t-ninety-third-psalm`) vs proposal_baseline: PD +0; time-aware F1 -0.102.
- Parting Hand (`1911-s0072-parting-hand`) vs previous: PD -1; time-aware F1 -0.351.
- Parting Hand (`1911-s0072-parting-hand`) vs proposal_baseline: PD -1; time-aware F1 -0.351.
- Mulberry Grove (`1911-s0104-mulberry-grove`) vs previous: PD +2; time-aware F1 -0.011.
- Mulberry Grove (`1911-s0104-mulberry-grove`) vs proposal_baseline: PD +2; time-aware F1 -0.011.
- Dull Care (`1911-s0108-dull-care`) vs previous: PD +1; time-aware F1 +0.000.
- Dull Care (`1911-s0108-dull-care`) vs proposal_baseline: PD +1; time-aware F1 +0.000.
- All Is Well (`1911-s0132-all-is-well`) vs previous: PD +3; time-aware F1 -0.009.
- All Is Well (`1911-s0132-all-is-well`) vs proposal_baseline: PD +3; time-aware F1 -0.009.
- Stratfield (`1911-s0152-stratfield`) vs previous: PD +1; time-aware F1 +0.000.
- Stratfield (`1911-s0152-stratfield`) vs proposal_baseline: PD +1; time-aware F1 +0.000.
- Hallelujah (`1911-s0156-hallelujah`) vs previous: PD +2; time-aware F1 +0.001.
- Hallelujah (`1911-s0156-hallelujah`) vs proposal_baseline: PD +1; time-aware F1 +0.005.
- Exhilaration (`1911-s0180-exhilaration`) vs proposal_baseline: PD +0; time-aware F1 -0.002.
- New Lebanon (`1911-s0212-new-lebanon`) vs previous: PD -5; time-aware F1 -0.014.
- New Lebanon (`1911-s0212-new-lebanon`) vs proposal_baseline: PD -5; time-aware F1 -0.011.
- Repentance (`1911-s0224-repentance`) vs previous: PD +0; time-aware F1 -0.147.
- Repentance (`1911-s0224-repentance`) vs proposal_baseline: PD -2; time-aware F1 -0.070.
- Ocean (`1911-s0232-ocean`) vs previous: PD +2; time-aware F1 -0.339.
- Ocean (`1911-s0232-ocean`) vs proposal_baseline: PD +2; time-aware F1 -0.339.
- Victoria (`1911-s0304-victoria`) vs previous: PD -1; time-aware F1 -0.003.
- Victoria (`1911-s0304-victoria`) vs proposal_baseline: PD -1; time-aware F1 -0.003.
- The American Star (`1911-s0360-the-american-star`) vs previous: PD -3; time-aware F1 -0.213.
- The American Star (`1911-s0360-the-american-star`) vs proposal_baseline: PD -7; time-aware F1 -0.177.
- Oh, Sing With Me! (`1911-s0388-oh-sing-with-me`) vs previous: PD +0; time-aware F1 -0.055.
- Oh, Sing With Me! (`1911-s0388-oh-sing-with-me`) vs proposal_baseline: PD +0; time-aware F1 -0.055.
- New Prospect (`1911-s0404-new-prospect`) vs previous: PD -3; time-aware F1 -0.375.
- New Prospect (`1911-s0404-new-prospect`) vs proposal_baseline: PD -3; time-aware F1 -0.375.
- Protection (`1911-s0416-protection`) vs previous: PD +1; time-aware F1 +0.195.
- Protection (`1911-s0416-protection`) vs proposal_baseline: PD +1; time-aware F1 +0.191.
- Mutual Love (`1911-s0444-mutual-love`) vs proposal_baseline: PD -10; time-aware F1 -0.026.
- Elder (`1911-s0464-elder`) vs previous: PD -2; time-aware F1 -0.420.
- Elder (`1911-s0464-elder`) vs proposal_baseline: PD -2; time-aware F1 -0.420.
- Rest For The Weary (`1911-s0488-rest-for-the-weary`) vs previous: PD -1; time-aware F1 -0.271.
- Rest For The Weary (`1911-s0488-rest-for-the-weary`) vs proposal_baseline: PD -1; time-aware F1 -0.038.
- Christian’s Hope (`1911-s0520-christian-s-hope`) vs previous: PD +2; time-aware F1 -0.004.
- Christian’s Hope (`1911-s0520-christian-s-hope`) vs proposal_baseline: PD +3; time-aware F1 +0.125.
- Burdette (`1911-s0536-burdette`) vs previous: PD -2; time-aware F1 -0.383.
- Burdette (`1911-s0536-burdette`) vs proposal_baseline: PD -2; time-aware F1 -0.383.
- The Converted Thief (`1911-s0054-the-converted-thief`) vs previous: PD +1; time-aware F1 -0.004.
- The Converted Thief (`1911-s0054-the-converted-thief`) vs proposal_baseline: PD +1; time-aware F1 +0.226.
- Albion (`1911-s0062-albion`) vs previous: PD +1; time-aware F1 -0.007.
- Albion (`1911-s0062-albion`) vs proposal_baseline: PD +1; time-aware F1 -0.007.
- Desire For Piety (`1911-s0086-desire-for-piety`) vs proposal_baseline: PD +0; time-aware F1 -0.016.
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
