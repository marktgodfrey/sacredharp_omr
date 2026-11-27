# Source-first damaged-head test: 1850 Auburn copy

## Outcome

Three premarked likely damaged physical heads survive the baseline, prior b651,
and conservative c291185f6a20 engines in both layouts (three objects, six paired
layout observations). **The revised abstention mechanism never triggers.**
There are no current non-head removals and no prior/current emitted-event or
cut changes. All 12 prior/current score XML pairs are byte-identical.
This demonstrates survival on this small source-selected sample, not a rescue
by the fix, broad transfer, or complete recognition accuracy. No tuning followed.

| Source annotation | Physical object | Source-only judgment | Symbol ID, both layouts | Baseline / prior / current note | Revised abstention |
|---|---|---|---:|---|---|
| D1 | Dublin p46, bass hollow square | Likely missing/weak left rim; main and independent reviewer agree | 201 | yes / yes / yes | no |
| D2 | Distress p50, treble hollow oval | Likely broken upper rim; both reviewers agree | 49 | yes / yes / yes | no |
| D3 | Portugal p60, treble hollow oval | Likely broken lower-left rim; both reviewers agree | 195 | yes / yes / yes | no |
| A1, secondary | Lenox p40, treble hollow oval | Main sees a rim break; independent reviewer regards it as ambiguous/possibly normal | 314 | yes / yes / yes | no |

The three primary head proposals have front-end realness 0.974, 0.994 and 0.990.
They are recognizably damaged but remain easy enough for the baseline here. No
box, threshold or source selection was changed to manufacture a filter trigger.
Survival does not certify their pitch, voice assignment or duration.

## Controls and other failures

Seven of eight premarked intact physical controls are serialized as notes by
all stages, both layouts. C1, Lenox's initial intact hollow triangle, is detected
as rest_half (symbol355) and serialized as a rest by every stage. An independent
source-only identity recheck agrees that the source glyph is a hollow triangular
notehead, plausibly stemless/whole. This is a baseline classification error, not
a new conservative-rule deletion. The locked source label is preserved.

Distress is a three-staff source; the baseline detects two staves in both layouts.
Its premarked damaged head still has a matching serialized note, but this
layout failure prevents any claim of full-tune correctness. All cases remain
included. No baseline emitted note ID is lost by the current stage. All 12
policy configurations pass the equal-part-span invariant in both versions;
that timing consistency alone does not establish correct rhythm.

## Selection, provenance and blinding

Before viewing this printing's pixels, PRESELECTION.md declared an ascending
search of printed music pages27-66, stopping after six clear-damage pages or at
page66. Forty pages were screened. Three likely-damage pages qualified (46,50,60).
Initially qualifying page40 was disputed in independent review: an explicit
pre-inference deviation retained it as an ambiguous secondary page rather than
silently dropping it. No six-page quota or result-based exclusion was imposed.
All complete tunes on the four retained pages are included: Lenox, Dublin,
Hanover, Consolation, Distress, Portugal. Eight intact controls were marked, the
first two intact heads in reading order on each page.

The six source crops, twelve annotations, protocol, engine mapping, PDF and
preselection plan were hash locked before any target inference. Selection SHA:
82820dfa659b6c200441ab191118b4ea2c7af293d8e9ecfd14fba1752d25550f.
All 12 fresh CPU_ONLY baseline captures completed, followed by 24 frozen-policy
outputs. Source annotations never entered inference or recover(). No reference
XML or reference score was opened. Both engine source trees and template banks
match the prior sealed 1860 run exactly. No recognition or rule code was changed.
The new adapter handles source paths and guards only.

The public PDF catalog sheet identifies Sacred Harp, second edition, first
printing, 1850, Auburn University copy, scanned for Vermont Early Music Project;
it notes a library miscataloging as1844. The historical title page survives but
its date/bottom is damaged. The date attribution therefore relies on the
catalog sheet and VEMP catalog, not a visible original1850 date. PDF ordinals
43,49,53,63 correspond to printed40,46,50,60.

- Catalog: https://vermontearlymusicproject.org/shapes-notes-move-south-1835-southern-harmony-and-1844-sacred-harp
- Public PDF: https://drive.google.com/file/d/1lgGobvG-rYBaw9NjntowSK9jbfdTYl5P/view

Native JPEG images were extracted without re-encoding; input PNGs are exact
rectangular crops with no rescaling, warping, enhancement or synthetic damage.
Annotation boxes map by translation to native input pixels. Matched atomic
note/rest boxes overlap annotations and have centers within0.75 staff-space.
All twelve physical matches were visually checked; C1 was not replaced by a
distant note. Trace syms are merged front-end reading symbols, not raw detector
tensors. Writer e.si IDs establish actual serialized-note survival.

## Limits

This is a small enriched convenience sample from a different printing/scan,
with oval/square damage only. Shared repertoire and printing plates remain
possible, model training provenance is unknown, and reviewers are assistants
rather than independent human music engravers. Rim loss is visually judged;
the physical cause (printing, wear, scanning) is not established. Layout pairs
are repeated observations, not independent damaged objects. The untouched test
now becomes observed material. No rule or threshold was tuned to its result.
Defaults and gallery remain unchanged.

**Recommended:** keep the rules experimental; gather a larger, predeclared
source-only challenge set covering severe damage and all four shapes, then
test the same frozen version. **Alternative:** use this run to open a separate
development audit of hollow-triangle classification and missing-staff layout,
with a new holdout for any resulting revision.
