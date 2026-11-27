# Committed evidence and local artifact data

Git includes the evaluation adapters, tests, source-selection protocols and
labels, frozen Python engine snapshots and meter templates, and compact reports,
checks, provenance, review panels and artifact manifests for the five frozen
cross-book runs. The latest result is
[the severe four-shape report](runs/severe-four-shape-holdout-20261127/REPORT.md).
It records recognition/layout failures, retained duplicates, reviewer disputes,
and incomplete coverage; it does not establish broad generalization.

Large raw PDFs, rendered source pages, native input crops, generated XML/trace
trees and diagnostic attempts remain local under the existing ignore rules.
The committed artifact manifests hash those files as well as code and reports;
their presence in Git does not mean that every referenced artifact is in Git.
Full hash verification and inference require the corresponding local data.
The source-set protocols record PDF origins and raster/crop policies.

The older `workspace-2026-11-26` release described in the root README predates
these cross-book runs. It is not a complete backup of this evaluation. A separate
checksummed artifact release would be needed to restore the complete new data
on another machine. No release archive was uploaded as part of this commit.

The frozen engine copies are committed at their recorded original paths:

- `benchmarks/sacred-harp-1911/experiments/rhythm-resolution/final-a17498fc863d/`
- `benchmarks/sacred-harp-1911/experiments/rhythm-resolution/dot-head-evidence-20261126-b6512a5f402d/`
- `benchmarks/crossbook-frozen-rules/engines/damaged-head-abstention-c291185f6a20/`

Only their source snapshots, meter templates and freeze metadata are included;
their full development output trees remain local. Preserve the frozen copies
when developing revisions. Use a new snapshot and fresh holdout for changed
rules; the evaluated source material is now observed data.
