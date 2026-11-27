# Frozen rules: source-first 1850 damaged-head test

## Preselection

PRESELECTION.md was written and hashed before target pixels were inspected.
The PDF catalog sheet identifies the Auburn copy as Sacred Harp, second edition,
first printing, 1850; the original title page bottom/date is damaged. The edition
attribution relies on the catalog sheet plus VEMP catalog, not a visible date.
Native JPEG bytes were extracted with pypdf (one unrotated image per page).
Inputs are exact rectangular native-pixel crops encoded as PNG, no resizing,
denoising, thresholding, warping or synthetic damage.

Printed pages 27-66 were screened in order. Three likely-damage pages qualified
(46,50,60). Page 40 initially qualified but independent review disagreed: keep
it as a secondary ambiguous page with denominator separate. This small explicit
pre-inference deviation preserves uncertainty; there is no result-based selection.
All complete tunes on these four pages are included: Lenox, Dublin, Hanover,
Consolation, Distress, Portugal. No tune continues outside its crop. No inference,
verifier, reference score or model condition was consulted for selection.

## Frozen rule check

Use the unchanged prior b651 and conservative c291185f6a20 code and fixed 1911
JPK meter templates. Engine mapping is engines.json. Both default and clean_layout
run all six inputs. Original model weights, taxonomy, crops, protocol, selection,
adapter and frozen rule trees are hash guarded. Selection annotations are never
passed into inference or recovery. Capture all baseline traces, then replay both
engines; no reference XML is opened and no PD/F1 scoring is needed here.

For each premarked likely damaged head and intact control report separately:
(1) baseline model detection (2) baseline emitted note (3) prior emitted note
(4) conservative emitted note (5) corresponding rejection/abstention reason.
A missed detection or unselected interpretation is a coverage failure, never a
protection success. Multiple copies of one physical head are not independent
heads; paired layout outcomes are not independent samples. Match annotations
with full source context; preserve uncertain or conflicting matches explicitly.

Inspect every new or current non-head removal, every abstention, every emitted
source decision change and all part-span failures. A confirmed genuine head
deleted by current is a safety failure even if other outputs improve. Retention
without triggering the revised evidence rule is survival, not a rescued head.
Retained artifacts remain errors; do not call all abstentions successes.

## No tuning

Do not change any rule, threshold, selected input, annotation or crop after
inference. Preserve failed attempts; document infrastructure-only retries. Report
negative results and mechanism coverage. These cases become observed data after
this run. Defaults and gallery remain unchanged. This enriched small scan sample
cannot establish book-wide accuracy, all-shape transfer or absence from model
training. Further revisions require fresh validation material.
