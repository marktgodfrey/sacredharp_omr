# Frozen rules on a fresh damaged-head sample

The public 1850 Auburn printing was selected from source pixels before inference:
6 complete tunes on4 pages,3 likely damaged heads,1 disputed secondary head and
8 intact controls, each in both layout variants. Forty source pages were screened.

| Check | Result |
|---|---|
| Baseline captures / frozen policy outputs | 12 /24, all completed |
| Premarked likely damaged heads emitted as notes | 3/3 physical heads in all stages, both layouts |
| Disputed secondary head | Retained by all stages; excluded from primary denominator |
| Intact controls | 7/8 emitted as notes;1 baseline rest misclassification persists |
| Revised abstentions / non-head removals | 0 /0 |
| Current-vs-prior score XML | 12/12 byte-identical |
| Equal-part-span failures | 0/12, both policy versions |
| Target tuning / reference-score fitting | None |

**Conclusion:** damaged-head survival was exercised, but the abstention change
was not. No rescue benefit is demonstrated. Do not claim broad generalization
or complete source accuracy. Distress also retains a two-of-three-staff baseline
layout failure. No baseline emitted note ID is deleted by the conservative stage.

Read SOURCE_REVIEW.md for annotation judgments, source provenance, explicit
selection deviation, baseline classification error and limitations; inspect
annotated-source-contact.png and source-head-review.json for every match.
Selection annotations stayed hash-identical. Both frozen rule trees and 1911
JPK template banks match the earlier sealed1860 test. No defaults/gallery changes.

## Reproduce in a new run

From the workspace root, use copisteria/.venv/bin/python and run_damaged_sample.py
with --source-set benchmarks/crossbook-frozen-rules/source-sets/1850-damaged-head-holdout-20261126
and --tag NEW_TAG: first --phase capture, then --phase replay --engine prior,
then --phase replay --engine current. Every generation phase refuses overwrite.
Use extract_source_changes.py NEW_RUN and review_damaged_sample.py NEW_RUN
SOURCE_SET only after all completion guards. No reference scorer is required.
The analysis utility had one path-normalization failure before writing output;
it was corrected in analysis only, with no inference/replay retry or rule change.

**Recommended:** retain the experimental status and expand the frozen
source-first challenge set. **Alternative:** audit the baseline's triangle/rest
and missing-staff failures as separate development work with fresh validation.
