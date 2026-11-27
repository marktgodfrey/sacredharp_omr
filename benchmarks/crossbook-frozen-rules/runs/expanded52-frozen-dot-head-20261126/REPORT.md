# Frozen rhythm rules: independent-printing evaluation

**Source portability check failed:** one genuine damaged head is deleted; ten non-head boxes are confirmed and one localization case remains ambiguous. Read [source review and conclusion](SOURCE_REVIEW.md). The rules were not retuned.

All 52 selected source crops (104 layout configurations) are retained. Rules and 1911 JPK meter templates were frozen before seeing these readings. No target-data tuning was performed.

| Book | Layout | Stage | PD edits / denominator | F1 | Failed predictions | Timing failures |
|---|---|---|---:|---:|---:|---:|
| 1870-Sacred-MTS | default | baseline | 2370/4830 | 0.3133 | 0 | 0 |
| 1870-Sacred-MTS | default | prior | 2330/4830 | 0.3763 | 0 | 9 |
| 1870-Sacred-MTS | default | current | 2328/4830 | 0.3765 | 0 | 9 |
| 1870-Sacred-MTS | clean_layout | baseline | 1607/4546 | 0.4401 | 0 | 0 |
| 1870-Sacred-MTS | clean_layout | prior | 1561/4546 | 0.4815 | 0 | 1 |
| 1870-Sacred-MTS | clean_layout | current | 1560/4546 | 0.4816 | 0 | 1 |
| 1911-Sacred-EMU | default | baseline | 2652/5014 | 0.4184 | 0 | 0 |
| 1911-Sacred-EMU | default | prior | 2672/5014 | 0.4224 | 0 | 5 |
| 1911-Sacred-EMU | default | current | 2667/5010 | 0.4228 | 0 | 5 |
| 1911-Sacred-EMU | clean_layout | baseline | 1866/4707 | 0.5141 | 0 | 0 |
| 1911-Sacred-EMU | clean_layout | prior | 1902/4707 | 0.4699 | 0 | 1 |
| 1911-Sacred-EMU | clean_layout | current | 1900/4705 | 0.4701 | 0 | 1 |

Current versus prior across 104 paired configurations: **{'pd_better': 11, 'pd_tied': 92, 'pd_worse': 1, 'f1_better': 18, 'f1_tied': 85, 'f1_worse': 1}**.
Added cohort only (76 configurations): **{'pd_better': 9, 'pd_tied': 67, 'pd_worse': 0, 'f1_better': 16, 'f1_tied': 60, 'f1_worse': 0}**.

`prior` is the pre-dot/false-head rhythm checkpoint; `current` is the new frozen checkpoint. Both start from identical baseline events; this does not reproduce the earlier JPK missing-head-proposal stages. `baseline` is the frozen CoreML reader without rhythm-resolution. Source voice order is used only for scoring; edition-absent altos are excluded, and unexpected/missing detected source parts remain penalized.

All 104 baseline captures and 208 frozen-policy outputs completed under hash guards before reference scoring. Original pilot baselines match the sealed pilot, ignoring encoding date; new captures have no prior XML parity comparator. The first pilot adapter scorer stopped on an equal-span assertion after generation; this analysis records timing failures instead. Neither rule snapshot was changed.

## Timing invariant failures

- 1870-Sacred-MTS-28t-aylesbury / default: {'prior': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 'current': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]}.
- 1911-Sacred-EMU-64-nashville / default: {'prior': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18], 'current': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]}.
- 1911-Sacred-EMU-222-ocean / default: {'prior': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27], 'current': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]}.
- 1911-Sacred-EMU-302-greenland / default: {'prior': [19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30], 'current': [19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]}.
- 1911-Sacred-EMU-370-monroe / default: {'prior': [7, 8, 9, 10, 11, 12], 'current': [7, 8, 9, 10, 11, 12]}.
- 1911-Sacred-EMU-450-elder / default: {'prior': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26], 'current': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]}.
- 1911-Sacred-EMU-450-elder / clean_layout: {'prior': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25], 'current': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]}.
- 1870-Sacred-MTS-122-all-is-well / default: {'prior': [9, 10, 11, 12, 13, 14, 15, 16, 17], 'current': [9, 10, 11, 12, 13, 14, 15, 16, 17]}.
- 1870-Sacred-MTS-146-hallelujah / default: {'prior': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27], 'current': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]}.
- 1870-Sacred-MTS-270-confidence / default: {'prior': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29], 'current': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]}.
- 1870-Sacred-MTS-302-greenland / default: {'prior': [49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60], 'current': [49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60]}.
- 1870-Sacred-MTS-326-weary-pilgrim / default: {'prior': [9, 10, 11, 12, 13, 14, 15, 16], 'current': [9, 10, 11, 12, 13, 14, 15, 16]}.
- 1870-Sacred-MTS-370-monroe / default: {'prior': [7, 8, 9, 10, 11, 12], 'current': [7, 8, 9, 10, 11, 12]}.
- 1870-Sacred-MTS-450-elder / default: {'prior': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18], 'current': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]}.
- 1870-Sacred-MTS-450-elder / clean_layout: {'prior': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18], 'current': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]}.
- 1870-Sacred-MTS-470-sardis / default: {'prior': [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29], 'current': [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]}.

## Current versus prior: every changed score

- 1911-Sacred-EMU-28t-aylesbury / default: PD -1; F1 +0.0000.
- 1911-Sacred-EMU-28t-aylesbury / clean_layout: PD +1; F1 -0.0088.
- 1911-Sacred-EMU-45b-supplication / default: PD -1; F1 +0.0002.
- 1911-Sacred-EMU-45b-supplication / clean_layout: PD +0; F1 +0.0005.
- 1911-Sacred-EMU-48t-devotion / default: PD +0; F1 +0.0022.
- 1911-Sacred-EMU-48t-devotion / clean_layout: PD +0; F1 +0.0022.
- 1911-Sacred-EMU-82b-edgefield / default: PD +0; F1 +0.0013.
- 1911-Sacred-EMU-82b-edgefield / clean_layout: PD +0; F1 +0.0013.
- 1911-Sacred-EMU-146-hallelujah / default: PD -1; F1 +0.0001.
- 1911-Sacred-EMU-146-hallelujah / clean_layout: PD -1; F1 +0.0001.
- 1911-Sacred-EMU-170-exhilaration / default: PD -1; F1 +0.0010.
- 1911-Sacred-EMU-170-exhilaration / clean_layout: PD -1; F1 +0.0010.
- 1911-Sacred-EMU-450-elder / default: PD -1; F1 +0.0012.
- 1911-Sacred-EMU-450-elder / clean_layout: PD -1; F1 +0.0012.
- 1870-Sacred-MTS-48b-kedron / default: PD -1; F1 +0.0043.
- 1870-Sacred-MTS-122-all-is-well / default: PD +0; F1 +0.0003.
- 1870-Sacred-MTS-122-all-is-well / clean_layout: PD +0; F1 +0.0019.
- 1870-Sacred-MTS-146-hallelujah / default: PD +0; F1 +0.0000.
- 1870-Sacred-MTS-370-monroe / default: PD -1; F1 +0.0002.
- 1870-Sacred-MTS-370-monroe / clean_layout: PD -1; F1 +0.0014.

These editions differ from the 2025 XML references, including absent altos and Bethel key signatures. Scores measure disagreement, not historical-source accuracy. Repeated matched tunes and two layout variants are paired observations, not independent songs. This is a printing-domain test, not proof that the model never trained on these tunes or editions.

Source adjudication of changed decisions is recorded separately. Defaults and gallery remain unchanged.

**Recommended:** inspect changed source decisions and the full-stage timing failures before broader enablement.
**Alternative:** expand independent-book coverage with the same frozen rules and no tuning on this run.

## Final validation

104 baseline configurations and 208 policy outputs are complete. All generation hash guards pass; 28 cached pilot baselines match their sealed XML, and 76 new CPU_ONLY captures are retained. Four adapter/scoring tests pass. Sixteen configurations fail the part-span invariant in both rule versions (14 default layout, two cleaned layout). Baseline timing cells were not independently assessed. No output was excluded to improve these results. Source review of every new effect is recorded in `source-review.json`. No emitted dot/duration/type/pitch or short-beam delta was observed; all 22 removal occurrences were line/blemish decisions.
