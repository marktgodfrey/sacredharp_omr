# Frozen rhythm rules: independent-printing pilot

**Source check failed:** the new line/blemish filter removes a genuine damaged head in 1911 Aylesbury. It correctly removes a staff-line artifact in Supplication. No rules were retuned. Read [source review and conclusion](SOURCE_REVIEW.md).

Seven matched tunes from each of the 1870 Sacred Harp and J. L. White 1911 editions; both baseline layout variants are retained. Rules and 1911 JPK meter templates were frozen before seeing these readings. No target-data tuning was performed.

| Book | Layout | Stage | PD edits / denominator | F1 | Failed predictions | Timing failures |
|---|---|---|---:|---:|---:|---:|
| 1870-Sacred-MTS | default | baseline | 375/878 | 0.5243 | 0 | 0 |
| 1870-Sacred-MTS | default | prior | 369/878 | 0.5445 | 0 | 1 |
| 1870-Sacred-MTS | default | current | 369/878 | 0.5445 | 0 | 1 |
| 1870-Sacred-MTS | clean_layout | baseline | 191/817 | 0.6797 | 0 | 0 |
| 1870-Sacred-MTS | clean_layout | prior | 177/817 | 0.7094 | 0 | 0 |
| 1870-Sacred-MTS | clean_layout | current | 177/817 | 0.7094 | 0 | 0 |
| 1911-Sacred-EMU | default | baseline | 597/1008 | 0.2972 | 0 | 0 |
| 1911-Sacred-EMU | default | prior | 615/1008 | 0.3772 | 0 | 0 |
| 1911-Sacred-EMU | default | current | 613/1006 | 0.3777 | 0 | 0 |
| 1911-Sacred-EMU | clean_layout | baseline | 400/897 | 0.4234 | 0 | 0 |
| 1911-Sacred-EMU | clean_layout | prior | 417/897 | 0.4301 | 0 | 0 |
| 1911-Sacred-EMU | clean_layout | current | 418/897 | 0.4293 | 0 | 0 |

Current versus prior across 28 paired configurations: **{'pd_better': 2, 'pd_tied': 25, 'pd_worse': 1, 'f1_better': 2, 'f1_tied': 25, 'f1_worse': 1}**.

`prior` is the pre-dot/false-head rhythm checkpoint; `current` is the new frozen checkpoint. Both start from identical baseline events; this does not reproduce the earlier JPK missing-head-proposal stages. `baseline` is the frozen CoreML reader without rhythm-resolution. Source voice order is used only for scoring; edition-absent altos are excluded, and unexpected/missing detected source parts remain penalized.

All 28 baseline captures and 56 frozen-policy outputs completed under hash guards before reference scoring. All baseline XMLs match the sealed pilot, ignoring encoding date. The original adapter scorer stopped on an equal-span assertion after generation; this separate analysis records that failure instead. Neither the adapter nor rule snapshots was changed.

## Timing invariant failures

- 1870-Sacred-MTS-28t-aylesbury / default: {'prior': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], 'current': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]}.

## Current versus prior: every changed score

- 1911-Sacred-EMU-28t-aylesbury / default: PD -1; F1 +0.0000.
- 1911-Sacred-EMU-28t-aylesbury / clean_layout: PD +1; F1 -0.0088.
- 1911-Sacred-EMU-45b-supplication / default: PD -1; F1 +0.0002.
- 1911-Sacred-EMU-45b-supplication / clean_layout: PD +0; F1 +0.0005.

These editions differ from the 2025 XML references, including absent altos and Bethel key signatures. Scores measure disagreement, not historical-source accuracy. Repeated matched tunes and two layout variants are paired observations, not 28 independent songs. This is a printing-domain test, not proof that the model never trained on these tunes or editions.

Source adjudication of changed decisions is recorded separately. Defaults and gallery remain unchanged.

**Recommended:** inspect changed source decisions and the full-stage timing failures before broader enablement.
**Alternative:** expand independent-book coverage with the same frozen rules and no tuning on this run.

Timing invariant checks in this table concern the two rhythm-stage outputs; baseline timing cells were not separately assessed. The results do not support broad enablement. New dot and short-beam rules had no emitted-output changes in this pilot, so those fixes lack cross-book coverage here.
