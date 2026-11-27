# Dot and false-head evidence: frozen batch comparison

Compared with `final-a17498fc863d` on all 120 songs. Predictions completed under the code hash guard before reference scoring. Defaults and gallery remain unchanged.

| Dataset | Stage | PD edits | Time-aware F1 |
|---|---|---:|---:|
| development100 | previous | 2712 | 0.6640 |
| development100 | current | 2694 | 0.6919 |
| diagnostic20 | previous | 621 | 0.6637 |
| diagnostic20 | current | 618 | 0.6642 |

PD better / tied / worse: 13 / 106 / 1. Timing better / tied / worse: 17 / 102 / 1.
Unresolved shared columns: 87 → 80. Changed common cuts: 8.

## Audited source bars

| Song ID | Column (zero-based) | Selected quarters | Status |
|---|---:|---:|---|
| 1911-s0098-done-with-the-world | 0 | 2 | source_adjudicated_local_voice |
| 1911-s0464-elder | 2 | 6 | source_adjudicated_local_voice |
| 1911-s0464-elder | 8 | 7 | source_ambiguity_retained |
| 1911-s0532-jackson | 1 | 4 | source_adjudicated_local_voice |
| 1911-s0124-the-midnight-cry | 7 | 2 | source_adjudicated_local_voice |
| 1911-47t-primrose | 5 | 4 | source_adjudicated_local_voice |

The five locally adjudicated bars pass their source-value/false-head checks. Elder column 8 retains its visible stemless head, real dot, and flagged seven-quarter overflow. These checks do not adjudicate every event in the five songs.

## Regressions against the prior checkpoint

- Fillmore (`1911-s0448-fillmore`): PD +1; F1 -0.0025.

All songs are development/diagnostic material from one book. Reference editions differ; these metrics do not establish cross-book accuracy. Holy Manna remains included without a layout-specific repair.

**Recommended:** source-review remaining regressions and evaluate a frozen cross-book holdout before broader enablement.
**Alternative:** keep the stage quarantined while collecting more source-reviewed controls.

## Fillmore source follow-up

The sole new metric regression is retained. Source review confirms that rejected ID 600 is staff-line/blemish ink below a real hollow square, not a physical head. The alto still has competing head interpretations and unresolved durations, despite passing the capacity check. Its selected end is 13/4 before padding to the four-quarter common cut. Do not restore the false note to improve reference agreement. [Source crop](fillmore-regression-source.png); [review evidence](regression-source-review.json).

## Final checks

205 tests passed before generation; all 151 frozen Python files stayed unchanged. All 8,334 part-measures match their selected cuts, all 18 protected heads remain, and all 17 reviewed durations match. Ninety-Third Psalm retains printed 3/4 and fourteen flagged six-quarter columns. The remaining 66 columns need source review. All 21 rejected note interpretations have positive non-head evidence; nineteen are additional to the prior checkpoint.
