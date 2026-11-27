# Source-first damaged-head selection plan

Declared before viewing any page pixels from this printing or running any
prediction. Source: Vermont Early Music Project public complete scan, Sacred
Harp 2nd edition, 1st printing, 1850, Auburn copy (catalogued as worn/damaged).
Catalog: https://vermontearlymusicproject.org/shapes-notes-move-south-1835-southern-harmony-and-1844-sacred-harp
PDF: https://drive.google.com/file/d/1lgGobvG-rYBaw9NjntowSK9jbfdTYl5P/view

Inspect the title/front matter to confirm the edition and map printed pages.
Then inspect printed music pages 27 through 66 in ascending order. Stop after
the first six pages containing at least one clearly identifiable genuine head
with visible loss/breakage of head ink, or after page 66 if fewer qualify.
Do not consult model detections, verifier features, predictions, reference XML,
or scores during selection. No rule-condition selection. No artificial damage.

Include every complete tune on each selected page, including intact neighbours.
A continued tune may use an adjoining page only to include its full extent; log
this separately. Log screened pages and exclusions. For selected pages mark
every clearly damaged head, any plausible ambiguous head fragment, and the
first two intact heads in reading order as controls. Damage means broken/missing
expected head ink visible at native resolution; normal hollow counters, sharp
triangle corners and ordinary staff/stem overlaps do not alone qualify. State
uncertainty rather than forcing a damaged label. Store pixel coordinates in
the unmodified source page and input crop.

Lock manifest and source-only selection annotations with SHA256 before inference.
Test unchanged b651 prior and c291185f6a20 conservative frozen engines, both layout
variants on all selected inputs. No tuning, sample changes, reference fitting or
exclusion based on results. Track baseline proposal coverage separately from
physical-head retention and broad-filter abstention. A missed baseline head is
not a successful abstention. Inspect all changed decisions and current removals.
No reference scores are needed for this targeted source-safety test. Never
interpret this enriched convenience sample as book-wide accuracy or proof of
unknown model-training exclusion. Same tunes/printing plates may be shared.
