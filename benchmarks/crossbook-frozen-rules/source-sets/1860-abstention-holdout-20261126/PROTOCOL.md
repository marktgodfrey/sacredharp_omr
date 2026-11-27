# Untouched 1860 holdout protocol

Declared before inspecting target pixels or generating any 1860 prediction for
this revision. The 19 source rows were selected earlier by the other chat from
the supplied PDF, with missing pages and edition differences recorded before
inference. Both layout settings are retained: 38 configurations.

The change is conservative and structural: broad line/blemish rejection may
remove only ink completely explained by thin staff lines supported outside the
candidate on both sides. Any unexplained fragment triggers abstention. No new
rim shape, fragment-size threshold, book ID, title, reference note count or
target meter is added to prediction. The narrower pre-existing empty-box rule,
repeat-dot rejection, beam evidence and duration policies remain unchanged.

Aylesbury and Kedron from the already examined 1870/1911 material are development
controls, not holdout successes. Synthetic partial rims, corners, vertical
fragments and single off-line pixels are tested at multiple staff scales. Known
artifacts may be retained; no requirement to preserve their earlier rejection
will be used to tune this version.

Before target evaluation:

- Finish all rule/test edits and run the existing development checks.
- Verify the 18 protected JPK heads, 17 reviewed durations and printed-meter
  safeguards using saved recognition, without reference XML.
- Freeze a new engine snapshot and the 1911 JPK template bank. Hash the adapter,
  source selection, source/crop bytes, taxonomy and models.

During target evaluation:

- Generate all 38 baseline captures and both sets of 38 policy outputs before
  opening any reference XML for scoring.
- Retain failed outputs and timing invariant failures; do not filter songs by
  score, layout quality or whether a rule helped.
- Review source pixels only after completion. Inspect every current non-head
  removal and every prior-versus-current changed source decision. Retained
  uncertain objects are not automatically correct notes.
- Any confirmed genuine-head deletion is a source-safety failure, even if the
  reference metric improves. Unresolved identities remain explicitly ambiguous.
- Report whether the abstention change was exercised; lack of changes is not
  proof of transferability. PD/F1 are secondary disagreement measurements, with
  edition differences and absent voices handled by the predeclared metadata.

No rule, threshold or target selection will be revised after observing this
holdout. A further fix would be a new version, with these cases treated as
development data and a new untouched test set. Defaults and gallery remain off
for the experimental stage.
