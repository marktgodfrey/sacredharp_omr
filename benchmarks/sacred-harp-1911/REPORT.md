# 1911 Sacred Harp CoreML benchmark

Local CoreML comparison of 100 songs from Original Sacred Harp (1911) against the project's 2025 MusicXML. All three neural stages use Apple's CoreML runtime with CPU_ONLY and the existing float32 copista-28m export (28,721,631 detector parameters), plus evidence-2m. Python handles geometry, ROI sampling and MusicXML decoding. This is a desktop reader benchmark, not the native Swift/iPhone pipeline.

Source scans: [Sounding Spirit Digital Library](https://library.soundingspirit.org/volume/1911-Origin-JPK/page/all). The saved manifest includes every full-resolution download URL.

The main metric is per-part Levenshtein disagreement on (absolute written chromatic pitch, notated duration in quarter notes). Its denominator is the sum of max(reference notes, predicted notes) for corresponding parts; missing/extra parts count. Lower is better. Parts match in printed order (normally treble, alto, tenor, bass). Generic prediction labels map by physical part position, including three-part layouts. Repeats are not unfolded; no key transposition, octave correction, arranging, or manual correction is applied. Rests, lyrics, shape semantics, ties, beams and repeat notation are not scored. JSON also includes pitch-only disagreement and exact absolute-onset event precision/recall/F1. These metrics are not the upstream OMR-NED metric.

The 2025 files are candidate references for the 1911 music, not a fully proofread 1911 ground truth. Edition changes, encoded repeat structure, alternate endings and engraving differences can contribute to disagreement. Songs were selected by checking printed titles, not page number alone. The original twenty were retained; the expansion reviewed evenly spaced scan candidates across the volume, with documented supplementary pages. Additional songs were screened for complete boundaries, matching key signatures and reference part counts. A final source audit corrected crops/layout metadata and removed incompatible or incomplete pairings after initial inference; those runs are retained as diagnostics. Selection did not favor songs with better recognition scores. This remains a non-random convenience sample filtered for compatible reference editions; no book-wide accuracy claim is supported. Expected layout counts were checked visually; matching counts alone does not prove correct geometry. Both settings are reported for every song, without choosing the best setting per song. Timings include per-song model setup, two detector passes, decoding and viewer generation; they are single runs, not a controlled latency benchmark.

| Song (1911 page) | Default disagreement | Clean-layout disagreement | Default / clean systems |
|---|---:|---:|---:|
| Bethel (27) | 10.9% | 10.9% | 2 / 2 (expected 2) |
| Lenox (40) | 31.7% | 31.7% | 2 / 2 (expected 2) |
| Clamanda (42) | 77.2% | 90.2% | 1 / 6 (expected 2) |
| Idumea (47b) | 46.7% | 93.4% | 1 / 4 (expected 1) |
| Holy Manna (59) | 85.5% | 24.7% | 1 / 2 (expected 2) |
| Aylesbury (28t) | 41.0% | 27.6% | 1 / 1 (expected 1) |
| Wells (28b) | 26.7% | 37.0% | 1 / 1 (expected 1) |
| Fairfield (29t) | 53.7% | 53.7% | 1 / 1 (expected 1) |
| Tribulation (29b) | 49.0% | 49.0% | 1 / 1 (expected 1) |
| Rochester (30t) | 19.5% | 89.3% | 1 / 4 (expected 1) |
| Prospect (30b) | 18.3% | 18.3% | 1 / 1 (expected 1) |
| Ninety-Third Psalm (31t) | 32.1% | 32.1% | 1 / 1 (expected 1) |
| Webster (31b) | 24.8% | 24.8% | 1 / 1 (expected 1) |
| Corinth (32t) | 24.1% | 24.1% | 1 / 1 (expected 1) |
| Weeping Savior (33t) | 81.4% | 81.4% | 3 / 3 (expected 1) |
| Abbeville (33b) | 13.7% | 13.7% | 1 / 1 (expected 1) |
| America (36t) | 47.8% | 47.8% | 1 / 1 (expected 1) |
| Ninety-Fifth (36b) | 52.2% | 52.2% | 1 / 1 (expected 1) |
| Primrose (47t) | 22.2% | 22.2% | 1 / 1 (expected 1) |
| Liverpool (37b) | 21.6% | 21.6% | 1 / 1 (expected 1) |
| Winter (38t) | 10.2% | 10.2% | 1 / 1 (expected 1) |
| Pisgah (58) | 68.5% | 17.6% | 1 / 2 (expected 2) |
| Parting Hand (62) | 17.8% | 18.8% | 2 / 2 (expected 2) |
| Save, Mighty Lord (70b) | 51.0% | 51.0% | 1 / 1 (expected 1) |
| Gainsville (70t) | 27.9% | 27.2% | 1 / 1 (expected 1) |
| King Of Peace (74b) | 21.5% | 21.5% | 1 / 1 (expected 1) |
| Edgefield (82b) | 73.4% | 73.4% | 1 / 1 (expected 1) |
| Bound For Canaan (82t) | 44.8% | 44.8% | 1 / 1 (expected 1) |
| Look Out (90) | 19.6% | 19.6% | 2 / 2 (expected 2) |
| Mulberry Grove (94) | 16.4% | 16.4% | 2 / 2 (expected 2) |
| Dull Care (98) | 45.9% | 90.2% | 3 / 8 (expected 2) |
| Fulfillment (102) | 26.4% | 26.8% | 2 / 2 (expected 2) |
| Mount Vernon (110) | 39.0% | 38.3% | 2 / 2 (expected 2) |
| The Midnight Cry (114b) | 46.7% | 46.7% | 1 / 1 (expected 1) |
| Suffield (114t) | 33.3% | 33.3% | 1 / 1 (expected 1) |
| All Is Well (122) | 20.7% | 20.7% | 2 / 2 (expected 2) |
| Babel’s Streams (126) | 28.9% | 28.9% | 2 / 2 (expected 2) |
| The Christian’s Hope (134) | 7.7% | 7.7% | 2 / 2 (expected 2) |
| Stratfield (142) | 79.3% | 39.9% | 1 / 2 (expected 2) |
| Hallelujah (146) | 14.5% | 14.5% | 2 / 2 (expected 2) |
| Funeral Thought (158) | 11.6% | 11.6% | 2 / 2 (expected 2) |
| Plenary (162) | 4.0% | 4.0% | 2 / 2 (expected 2) |
| Exhilaration (170) | 41.1% | 41.1% | 2 / 2 (expected 2) |
| Newburgh (182) | 47.8% | 47.8% | 2 / 2 (expected 2) |
| Sherburne (186) | 42.1% | 42.1% | 2 / 2 (expected 2) |
| New Lebanon (202) | 40.4% | 40.4% | 2 / 2 (expected 2) |
| Lena (210) | 41.9% | 41.9% | 2 / 2 (expected 2) |
| Repentance (214) | 63.4% | 62.4% | 2 / 2 (expected 2) |
| Ocean (222) | 19.5% | 19.5% | 2 / 2 (expected 2) |
| Confidence (270) | 30.5% | 30.5% | 2 / 2 (expected 2) |
| The Golden Harp (274t) | 66.2% | 66.2% | 2 / 2 (expected 1) |
| I’m Going Home (282) | 29.1% | 29.1% | 2 / 2 (expected 2) |
| Victoria (290) | 20.1% | 20.1% | 2 / 2 (expected 2) |
| Never Part (294) | 50.8% | 50.8% | 2 / 2 (expected 2) |
| Providence (298) | 36.5% | 36.5% | 2 / 2 (expected 2) |
| Greenland (302) | 49.6% | 49.6% | 2 / 2 (expected 2) |
| Weeping Savior (310) | 20.5% | 20.5% | 2 / 2 (expected 2) |
| Weary Pilgrim (326) | 20.4% | 20.4% | 2 / 2 (expected 2) |
| Love Divine (330t) | 36.8% | 36.8% | 1 / 1 (expected 1) |
| Sawyer’s Exit (338) | 23.0% | 23.0% | 2 / 2 (expected 2) |
| The American Star (346) | 54.6% | 54.6% | 2 / 2 (expected 2) |
| Happy Land (354b) | 28.6% | 28.6% | 1 / 1 (expected 1) |
| Monroe (370) | 91.3% | 91.3% | 2 / 2 (expected 2) |
| Oh, Sing With Me! (374) | 24.8% | 24.8% | 2 / 2 (expected 2) |
| Heavenly Port (378t) | 30.5% | 30.5% | 1 / 1 (expected 1) |
| New Prospect (390) | 18.4% | 18.4% | 2 / 2 (expected 2) |
| The Messiah’s Praise (394) | 48.7% | 48.7% | 2 / 2 (expected 2) |
| Farewell To All (398t) | 92.2% | 92.2% | 4 / 4 (expected 1) |
| Protection (402) | 61.0% | 61.0% | 2 / 2 (expected 2) |
| New Harmony (406) | 39.2% | 39.2% | 2 / 2 (expected 2) |
| Rees (418) | 59.9% | 59.9% | 2 / 2 (expected 2) |
| The Grieved Soul (422b) | 45.1% | 43.4% | 1 / 1 (expected 1) |
| Mutual Love (430) | 46.6% | 46.0% | 1 / 1 (expected 1) |
| Fillmore (434) | 84.5% | 84.5% | 1 / 1 (expected 2) |
| Blooming Youth (442t) | 39.2% | 39.2% | 1 / 1 (expected 1) |
| Elder (450) | 22.6% | 22.6% | 2 / 2 (expected 2) |
| Friendship (458) | 39.5% | 38.1% | 2 / 2 (expected 2) |
| Sardis (470) | 38.6% | 38.6% | 2 / 2 (expected 2) |
| Rest For The Weary (474) | 30.1% | 29.2% | 2 / 2 (expected 2) |
| Chester (478) | 44.1% | 44.1% | 1 / 1 (expected 1) |
| Amsterdam (494) | 24.6% | 24.6% | 2 / 2 (expected 2) |
| Saint’s Delight (498) | 41.4% | 41.4% | 2 / 2 (expected 2) |
| Christian’s Hope (506) | 31.1% | 31.4% | 2 / 2 (expected 2) |
| Jackson (518b) | 36.6% | 38.1% | 1 / 1 (expected 1) |
| Burdette (522) | 23.4% | 23.4% | 2 / 2 (expected 2) |
| Kelley (526t) | 25.9% | 25.9% | 1 / 1 (expected 1) |
| Arbacoochee (530) | 51.0% | 50.0% | 2 / 2 (expected 2) |
| The Converted Thief (44) | 12.9% | 12.9% | 2 / 2 (expected 2) |
| Devotion (48t) | 35.3% | 33.1% | 1 / 1 (expected 1) |
| Albion (52t) | 16.0% | 16.0% | 1 / 1 (expected 1) |
| Nashville (64) | 55.8% | 9.8% | 4 / 2 (expected 2) |
| Salem (68t) | 93.2% | 93.2% | 4 / 4 (expected 1) |
| Bellevue (72b) | 32.2% | 93.4% | 1 / 4 (expected 1) |
| The Weary Soul (72t) | 12.8% | 12.8% | 1 / 1 (expected 1) |
| Desire For Piety (76b) | 39.5% | 23.8% | 1 / 1 (expected 1) |
| Holiness (76t) | 37.4% | 23.0% | 1 / 1 (expected 1) |
| Service Of The Lord (80b) | 89.9% | 15.8% | 4 / 1 (expected 1) |
| Mount Zion (88b) | 27.3% | 98.3% | 1 / 4 (expected 1) |
| Done With The World (88t) | 13.3% | 13.3% | 1 / 1 (expected 1) |
| The Bower Of Prayer (100) | 83.4% | 20.5% | 1 / 2 (expected 2) |

## Pooled results

default: 40.9% pitch+duration disagreement (8347/20427); 13/100 layout count failures; 0/100 inference failures; 426.7 s total.

clean_layout: 39.2% pitch+duration disagreement (7974/20327); 11/100 layout count failures; 0/100 inference failures; 390.7 s total.

## Findings

default layout-count failures: Clamanda, Holy Manna, Weeping Savior, Pisgah, Dull Care, Stratfield, The Golden Harp, Farewell To All, Fillmore, Nashville, Salem, Service Of The Lord, The Bower Of Prayer.

default inference failures: none.

clean_layout layout-count failures: Clamanda, Idumea, Rochester, Weeping Savior, Dull Care, The Golden Harp, Farewell To All, Fillmore, Salem, Bellevue, Mount Zion.

clean_layout inference failures: none.

Lowest default pitch+duration disagreement: Plenary (4.0%), The Christian’s Hope (7.7%), Winter (10.2%).

Cleanup lowers pooled disagreement by 1.6 percentage points. Its effect varies by song: it repairs Holy Manna's system grouping, but breaks Idumea and Rochester. Even matching staff/system counts do not guarantee correct notes or bar segmentation.

## Files and reproduction

`manifest.json` records source URLs, exact song crops and reference files. `results.json` records all per-part scores, runtime reports, hashes and dependency versions. `index.html` links every scan, output and reference.

From `/Users/mark/code/sh_omr`:

```sh
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_benchmark.py
# Recreate crops/copy references and run any missing predictions:
copisteria/.venv/bin/python benchmarks/sacred-harp-1911/run_benchmark.py --prepare --infer
# Add --force to rerun saved predictions; CoreML needs Apple's compiler/cache access.
# Add --render-references to recreate the reference score previews.
python3 -m unittest discover -s benchmarks/sacred-harp-1911 -p 'test_compare_musicxml.py' -v
```

1911 page 35 / scan 0045 (Augusta) was downloaded during discovery and excluded because modern page 35 is Saints Bound for Heaven. Scan 0044 (Hamilton / Bleeding Saviour) also lacked title matches. Peterborough (1911 32b / 2025 452t) was run, then excluded because the scan has four parts and the reference only three. Its full results remain in `diagnostics/excluded-peterborough.json`; Liverpool replaces it in the pooled set of 100 songs. Original scans and all raw outputs are retained.

The final expansion audit exclusions and their original scores are preserved in `diagnostics/excluded-expanded-pairs.json`. Review decisions and reasons are in the manifest's `excluded_candidates` and the three `review_*.json` files. Outputs from the corrected King of Peace crop are retained under `diagnostics/crop-before-final-audit/`. The original twenty-song manifest and results remain in `diagnostics/manifest-20.json` and `diagnostics/results-20.json`.

Integrity checks are recorded in `diagnostics/validation-100.json`: 100 unique reference files copied unchanged, all reference self-comparisons at zero edits, 200 CPU_ONLY CoreML outputs and 100 reference previews present, valid crop bounds, unchanged original twenty-song scores, and no broken local report links. The ten scorer/runner unit checks pass.
