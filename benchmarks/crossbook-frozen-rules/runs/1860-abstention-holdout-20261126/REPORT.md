# Conservative damaged-head abstention: untouched 1860 holdout

**Limited validation:** the revision keeps the development damaged head, but the holdout retained four artifacts and produced no new genuine-head protection example. No non-heads were deleted, so no genuine heads were deleted by the filter in these configurations. PD disagreement increases by seven edits across both layouts. Read [source review and limitations](SOURCE_REVIEW.md). No rule was retuned.

All 19 selected source crops (38 layout configurations) are retained. Rules and 1911 JPK meter templates were frozen before seeing these readings. No target-data tuning was performed.

| Book | Layout | Stage | PD edits / denominator | F1 | Failed predictions | Timing failures |
|---|---|---|---:|---:|---:|---:|
| 1860-Sacred-IMSLP | default | baseline | 950/3187 | 0.5662 | 0 | 0 |
| 1860-Sacred-IMSLP | default | prior | 898/3186 | 0.5242 | 0 | 2 |
| 1860-Sacred-IMSLP | default | current | 901/3187 | 0.5228 | 0 | 2 |
| 1860-Sacred-IMSLP | clean_layout | baseline | 1196/3305 | 0.5303 | 0 | 0 |
| 1860-Sacred-IMSLP | clean_layout | prior | 1139/3303 | 0.4901 | 0 | 1 |
| 1860-Sacred-IMSLP | clean_layout | current | 1143/3305 | 0.4887 | 0 | 1 |

Current versus prior across 38 paired configurations: **{'pd_better': 0, 'pd_tied': 32, 'pd_worse': 6, 'f1_better': 0, 'f1_tied': 33, 'f1_worse': 5}**.
Added cohort only (38 configurations): **{'pd_better': 0, 'pd_tied': 32, 'pd_worse': 6, 'f1_better': 0, 'f1_tied': 33, 'f1_worse': 5}**.

`prior`: Frozen pre-abstention dot/false-head checkpoint. `current`: Frozen conservative damaged-head abstention revision. Both start from identical baseline events; this does not reproduce the earlier JPK missing-head-proposal stages. `baseline` is the frozen CoreML reader without rhythm-resolution. Source voice order is used only for scoring; edition-absent altos are excluded, and unexpected/missing detected source parts remain penalized.

All 38 baseline captures and 76 frozen-policy outputs completed under hash guards before reference scoring. Baseline parity comparators: 0 match, 0 differ, 38 unavailable for new captures. Timing failures remain data rather than exclusions. Neither rule snapshot was changed during generation.

## Timing invariant failures

- 1860-Sacred-IMSLP-145-hallelujah / default: {'prior': [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25], 'current': [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]}.
- 1860-Sacred-IMSLP-145-hallelujah / clean_layout: {'prior': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34], 'current': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34]}.
- 1860-Sacred-IMSLP-222-ocean / default: {'prior': [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28], 'current': [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]}.

## Current versus prior: every changed score

- 1860-Sacred-IMSLP-45b-supplication / default: PD +1; F1 -0.0320.
- 1860-Sacred-IMSLP-45b-supplication / clean_layout: PD +1; F1 -0.0320.
- 1860-Sacred-IMSLP-82t-bound-for-canaan / default: PD +1; F1 -0.0006.
- 1860-Sacred-IMSLP-82t-bound-for-canaan / clean_layout: PD +1; F1 -0.0006.
- 1860-Sacred-IMSLP-145-hallelujah / default: PD +1; F1 +0.0000.
- 1860-Sacred-IMSLP-145-hallelujah / clean_layout: PD +2; F1 -0.0002.

These editions differ from the 2025 XML references, including absent altos and Bethel key signatures. Scores measure disagreement, not historical-source accuracy. Repeated matched tunes and two layout variants are paired observations, not independent songs. This is a printing-domain test, not proof that the model never trained on these tunes or editions.

Source adjudication of changed decisions is recorded separately. Defaults and gallery remain unchanged.

**Recommended:** inspect changed source decisions and the full-stage timing failures before broader enablement.
**Alternative:** expand independent-book coverage with the same frozen rules and no tuning on this run.

## Final validation

214 tests passed before freezing the revised 152-file engine. Development recovery preserves 18 protected heads, 17 reviewed durations, Ninety-Third Psalm printed 3/4, and Lenox/Ragan/Duane controls. All 38 fresh baseline captures and 76 policy outputs completed under hash guards before scoring. Human source judgments were locked before reference scores. All selected baseline note ID/pitch sets survive the conservative current run. Three equal-span failures remain in both versions. Damaged-head holdout coverage is insufficient: all four changed objects are artifacts. Defaults and gallery are unchanged.
