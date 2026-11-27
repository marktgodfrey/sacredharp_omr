# Shareable OMR performance report

[Open or download the six-page PDF](sacred-harp-omr-performance-2026-11-27.pdf).

The report covers the source-grounded rule changes, the 120-song development
comparison, scored cross-printing evaluations, and source-first damaged-head
holdouts. It includes baseline/policy PD and F1 tables, charts, source examples,
negative results, coverage gaps and limits on generalization.

Evidence is pinned to commit `4fbe781313add2c13ee86151c736282328cdd7bb`.
The PDF has embedded fonts and requires no external assets to read or share.
Its six evidence links point to that immutable commit. Large raw scans and full
inference traces remain local, as described in the benchmark's ARTIFACTS.md.

`report-statistics.json` contains source-backed metrics and cohort definitions;
`performance-data.json` holds the rounded table display values.
`report-verification.json` records source/PDF hashes and document checks.
The two PNG figures are lossless source crops with annotation boxes for display.

`build_performance_report.py` recreates the PDF with Python, ReportLab, Pillow
and the macOS Arial/Georgia fonts. It uses the bundled figure PNGs if original
page images are unavailable. The builder never runs or changes OMR rules.
