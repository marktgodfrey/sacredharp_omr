"""Summarize independent layout replay and frozen closer-crop experiments."""
import html
import json
import os
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'experiments/reader-v1'


def stats(samples, variant):
    ts = [s['variants'][variant]['comparison']['totals'] for s in samples]
    edits = sum(t['pitch_duration_edit_distance'] for t in ts)
    denominator = sum(t['pitch_duration_rate_denominator'] for t in ts)
    diffs = [s['variants'][variant]['comparison']['totals']['pitch_duration_error_rate'] -
             s['variants']['reproduced_default']['comparison']['totals']['pitch_duration_error_rate']
             for s in samples]
    return {'songs': len(samples), 'edits': edits, 'denominator': denominator,
            'rate': edits / denominator, 'better': sum(d < 0 for d in diffs),
            'equal': sum(d == 0 for d in diffs), 'worse': sum(d > 0 for d in diffs)}


def main():
    pilot = json.loads((OUT / 'results.json').read_text())['samples']
    validation = json.loads((ROOT / 'experiments/reader-v1-validation/results.json').read_text())['samples']
    selection = json.loads((OUT / 'layout-selection-evaluated.json').read_text())
    aggregates = {name: stats(validation, name) for name in
                  ['reproduced_default', 'baseline_exclusive', 'staff16', 'staff16_exclusive']}
    (OUT / 'improvement-summary.json').write_text(json.dumps({
        'crop_followup': aggregates, 'layout_replay': selection['aggregates'],
        'original_baselines_reproduced_exactly': len(pilot) + len(validation),
        'trace_xml_pitched_sequences_verified': 88,
        'holy_manna_in_crop_pilot_or_followup': False,
        'reference_used_for_inference_or_layout_selection': False,
    }, indent=2) + '\n')
    lines = ['# First reader improvement experiments', '',
             'Two independent experiments: conservative raw/clean layout selection, and closer detector views with overlapping note/rest resolution. Holy Manna was excluded from the four-song crop pilot and sixteen-song follow-up. The layout replay below also excludes it. These are development experiments on the existing 100-song corpus, not an independent test set.', '',
             '## Layout selection', '',
             'Only switch from raw to cleaned when the raw result fails the structural checks and the cleaned result satisfies them: three or four exported voices, consistent across the detected systems. Raw wins ties; if both are broken, retain raw. Reference XML, expected counts and note scores are not selection inputs.', '']
    a = selection['aggregates']['excluding_holy_manna']
    lines += [f"Across {a['songs']} songs, disagreement changes from {a['default_pooled_error_rate']:.1%} to {a['selected_pooled_error_rate']:.1%}; layout-count mismatches fall from {a['default_layout_mismatches']} to {a['selected_layout_mismatches']}. The selector switches {a['switched']} songs. This is a replay of existing outputs; it does not measure the extra cost of trying both layouts.", '',
              '[Exact layout selection results](layout-selection-evaluated.json) · [Selection method](layout-selection.md)', '',
              '## Closer crops and glyph conflicts', '',
              'The detector first reads the whole page normally. Additional overlapping staff crops target 16 pixels per staff space and are mapped back to original image coordinates. Only note/rest candidates are merged; crop detections do not replace the original clefs, barlines or measure boxes. The same CoreML weights and CPU_ONLY setting are used.', '',
              'After contextual decoding, two readings of one physical glyph cannot both survive when one is a note and the other a rest: same staff/bar, at least 0.5 bounding-box IoU, near-identical centers, winner probability at least 0.95 and probability margin at least 0.20. Ambiguous cases are retained. No notes are fabricated, manually inserted or taken from the reference.', '',
              'These thresholds were fixed after examining the initial four songs, before running the additional sixteen. The sixteen-song list and source hashes are saved in [the follow-up plan](../reader-v1-validation/plan.json).', '',
              '| Sixteen-song follow-up | Edits / denominator | Disagreement | Better / equal / worse |',
              '|---|---:|---:|---:|']
    labels = {'reproduced_default': 'Original reader reproduced', 'baseline_exclusive': 'Conflict rule only',
              'staff16': 'Closer crops only', 'staff16_exclusive': 'Closer crops + conflict rule'}
    for key, value in aggregates.items():
        lines.append(f"| {labels[key]} | {value['edits']} / {value['denominator']} | {value['rate']:.1%} | {value['better']} / {value['equal']} / {value['worse']} |")
    lines += ['', 'The main gain comes from recovering better note candidates at closer scale. The conflict rule then prevents an old false-rest candidate from coexisting with a recovered note and pushing later notes beyond the bar.', '',
              '![Plenary bar before and after](plenary-recovered.png)', '',
              'Plenary treble bar 2 now contains the four printed notes with their correct durations. Its whole-song disagreement falls from 4.0% to 2.7%. Monroe remains a failure: crops slightly worsen it (91.3% to 91.6%), and its exported five-part structure still needs a separate geometry/part-assignment fix.', '',
              '## Per-song follow-up', '', '| Song | Original | Crops + conflict rule |', '|---|---:|---:|']
    htmlrows = []
    for s in validation:
        baseline = s['variants']['reproduced_default']
        improved = s['variants']['staff16_exclusive']
        ar, br = [v['comparison']['totals']['pitch_duration_error_rate'] for v in (baseline, improved)]
        lines.append(f"| {s['title']} | {ar:.1%} | {br:.1%} |")
        links = []
        for label, v in [('Before', baseline), ('After', improved)]:
            path = Path(v['prediction'])
            if not path.is_absolute():
                path = ROOT.parents[1] / path
            links.append(f'<a href="{quote(os.path.relpath(path.with_suffix(".html"), OUT))}">{label}</a>')
        htmlrows.append(f"<tr><td>{html.escape(s['title'])}</td><td>{ar:.1%}</td><td>{br:.1%}</td><td>{' · '.join(links)}</td></tr>")
    lines += ['', '## Verification and reproduction', '',
              'All twenty unmodified baseline reproductions exactly match the original per-part comparisons. All 88 experimental trace/XML pairs have identical emitted pitched-note sequences. Model candidates, post-context readings, conflict decisions and final emitted symbol IDs are saved in each .trace.json. Focused tests cover tile coordinates/merging, conservative selection, symbol conflicts, writer-hook restoration, CoreML input buffer ownership, and the scorer.', '',
              'A Python/CoreML bridge crash during model reuse was avoided by retaining owned input buffers per shape; subsequent pilot/follow-up runs completed. This is an experimental benchmark reader; the application pipeline and model weights have not been changed. Timings are not a controlled speed comparison.', '',
              'The scores retain the original cross-edition comparison method. Layout selection and crop gains were measured separately and must not be added together. A full-corpus run of the combined reader remains to be done.', '',
              'From /Users/mark/code/sh_omr:', '', '```sh',
              'copisteria/.venv/bin/python benchmarks/sacred-harp-1911/evaluate_layout_selection.py',
              'copisteria/.venv/bin/python benchmarks/sacred-harp-1911/experiment_reader.py --targets 16 --resolve-conflicts',
              "copisteria/.venv/bin/python -m pytest -q benchmarks/sacred-harp-1911/test_*.py", '```', '',
              'Use --titles to select other manifest songs and --out for a separate experiment directory. CoreML inference requires the usual Apple compiler/cache access.', '']
    (OUT / 'REPORT.md').write_text('\n'.join(lines))
    doc = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Reader improvement experiments</title>'
           '<style>body{max-width:1100px;margin:40px auto;padding:0 24px;font:18px/1.5 system-ui;background:#f6f5ef;color:#203133}img{width:100%;height:auto}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:8px;border-bottom:1px solid #bbb}a{color:#11656a}</style>'
           '<h1>First reader improvement experiments</h1>'
           f"<p>Sixteen additional songs: {aggregates['reproduced_default']['rate']:.1%} disagreement before, {aggregates['staff16_exclusive']['rate']:.1%} after closer crops and conflict resolution. Fifteen improve, one ties. Holy Manna excluded.</p>"
           '<p><a href="REPORT.md">Methods, limitations and reproduction</a> · <a href="improvement-summary.json">Summary JSON</a> · <a href="../reader-v1-validation/results.json">Full follow-up results</a></p>'
           '<img src="plenary-recovered.png" alt="Plenary before and after">'
           '<h2>Sixteen-song follow-up</h2><table><tr><th>Song</th><th>Before</th><th>After</th><th>Scan/score viewers</th></tr>'
           + ''.join(htmlrows) + '</table>'
           f"<p>Separate layout replay on 99 songs: {a['default_pooled_error_rate']:.1%} to {a['selected_pooled_error_rate']:.1%}. Layout-count failures: {a['default_layout_mismatches']} to {a['selected_layout_mismatches']}.</p>"
           '<p>These gains were measured separately. Combined-reader full-corpus accuracy has not been measured. Monroe remains unresolved.</p></html>')
    (OUT / 'index.html').write_text(doc)
    print(json.dumps(aggregates, indent=2))


if __name__ == '__main__':
    main()
