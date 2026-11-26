"""Validate and summarize a saved local-recovery ablation, without rerunning it."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from reader_policy import near_head
from run_local_recovery import ROOT, samples, physical_loss
from replay_writer_trace import _reading
from PIL import Image


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviewed_status(trace, cases):
    result = []
    for c in cases:
        sp = trace['staves'][c['staff']]['sp']
        ids = {s['i'] for s in trace['syms'] if s['staff'] == c['staff']
               and near_head(c['box'], s['box'], sp)}
        events = [e for e in trace['writer']['emitted'] if e['e.si'] in ids]
        note = any(e['kind'] == 'note' for e in events)
        result.append({'case_id': c['case_id'], 'note_emitted': note,
            'false_rest_emitted': not note and any(e['kind'] == 'rest' for e in events)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment', type=Path)
    args = parser.parse_args()
    out = args.experiment.resolve()
    data = read(out/'results.json')
    metadata = {s['id']: s for s in samples()}
    cases = read(ROOT/'diagnostics/miss-trace/confirmed-misses.json')['cases']
    provenance_sources = {}
    for name, expected in data['provenance']['sha256'].items():
        current = ROOT.parent.parent/name
        snapshot = out/'source-snapshots'/name
        if not snapshot.exists():
            snapshot = out/'source-snapshots'/Path(name).name
        used = current if sha(current) == expected else snapshot
        assert used.exists() and sha(used) == expected, name
        provenance_sources[name] = str(used.relative_to(ROOT.parent.parent))
    names = ['frozen']+list(data['samples'][0]['variants'])
    reviewed = {n: [] for n in names}
    verified_files = 0
    guards = Counter(); selected = Counter(); short = Counter()
    references = {}
    for row in data['samples']:
        sid = row['id']; s = metadata[sid]
        assert row['frozen_exact_replay']
        prior = read((ROOT/s['old_prediction']).with_suffix('.trace.json'))
        song_cases = [c for c in cases if c['song_id'] == sid]
        reviewed['frozen'] += reviewed_status(prior, song_cases)
        reference = ROOT/s['reference']
        references[str(reference.relative_to(ROOT))] = sha(reference)
        assert references[str(reference.relative_to(ROOT))] == s['reference_sha256']
        image = Image.open(ROOT/s['input'])
        for variant,v in row['variants'].items():
            p = ROOT/v['prediction']; assert sha(p) == v['sha256']
            trace = read(p.with_suffix('.trace.json'))
            root = ET.parse(p).getroot()
            # Generated padding rests can bypass the source-linked _note hook.
            # Every pitched event must agree with actual serialized MusicXML.
            xml_notes = [n for n in root.findall('.//note') if n.find('pitch') is not None]
            actual = [(n.findtext('pitch/step'), int(n.findtext('pitch/octave')),
                int(n.findtext('pitch/alter', '0')), int(n.findtext('duration', '0'))) for n in xml_notes]
            traced = [(e['step'],e['octave'],e['alter'],e['dur']) for e in trace['writer']['emitted'] if e['kind'] == 'note']
            assert actual == traced, (sid,variant)
            if variant != 'masking':
                rd = _reading(trace, image)
                assert not physical_loss(prior, trace['writer'], rd.layout), (sid,variant)
                old_root = ET.parse(ROOT/s['old_prediction']).getroot()
                assert [ET.tostring(t) for t in root.findall('.//attributes/time')] == [
                    ET.tostring(t) for t in old_root.findall('.//attributes/time')], (sid,variant,'meter')
                assert [len(p.findall('measure')) for p in root.findall('part')] == [
                    len(p.findall('measure')) for p in old_root.findall('part')], (sid,variant,'bars')
            reviewed[variant] += reviewed_status(trace, song_cases)
            guards[variant] += trace.get('global_guard_fallback', False)
            selected[variant] += sum(d['selected'] != 'frozen' for d in trace.get('local_bar_decisions', []))
            short[variant] += sum(d['evidence']['found'] for d in trace.get('note_rest_evidence', []))
            verified_files += 1
    reviewed_counts = {n: {'reviewed_heads': len(cs), 'notes_emitted': sum(c['note_emitted'] for c in cs),
        'false_rests_emitted': sum(c['false_rest_emitted'] for c in cs)} for n,cs in reviewed.items()}
    meta_files = [ROOT/f for f in ('reader-gallery/results.json', 'experiments/reader-v2/replay_bar_fit/results.json',
        'experiments/bar-fitting/unused20/results.json', 'experiments/bar-fitting/unused20/manifest.json',
        'diagnostics/miss-trace/confirmed-misses.json', 'validate_frozen_policy.py')]
    validation = {'songs': len(data['samples']), 'predictions_checked': verified_files,
        'all_frozen_replays_exact': True, 'local_variants_preserve_frozen_physical_pitches': True,
        'local_variants_preserve_emitted_meter_and_measure_counts': True,
        'reviewed_heads': reviewed_counts, 'selected_staff_bars': dict(selected),
        'global_guard_fallbacks': dict(guards), 'positive_short_stem_evidence': dict(short),
        'generation_provenance_sources_verified': provenance_sources,
        'reviewed_cases': reviewed, 'reference_sha256_after_generation': references,
        'metadata_and_observation_helper_sha256': {str(p.relative_to(ROOT)): sha(p) for p in meta_files}}
    if (out/'checks.json').exists():
        checks = read(out/'checks.json')
        for name, expected in checks['code_sha256'].items():
            assert sha(ROOT.parent.parent/name) == expected, name
        validation['tests'] = checks
    (out/'validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    lines = ['# Staff masking, local bar recovery and note/rest evidence', '',
        'Saved-reading replay of all selected songs. The frozen outputs and published gallery are unchanged. '
        'All predictions were saved before the scoring phase opened reference XML. '
        'Both the development 100 and previously unused 20 are diagnostic/development examples for these changes.', '',
        f'Experiment key: `{data["experiment_key"]}`. [Results](results.json), [validation](validation.json).', '',
        '| Dataset | Variant | Pitch edits | Pitch + duration edits | Denominator | Disagreement | Better / tie / worse vs frozen |',
        '|---|---|---:|---:|---:|---:|---|']
    for dataset, variants in data['aggregates'].items():
        for n,t in variants.items():
            lines.append(f'| {dataset} | {n} | {t["pitch_edits"]} | {t["edits"]} | {t["denominator"]} | '
                f'{t["edits"]/t["denominator"]:.2%} | {t["better"]} / {t["same"]} / {t["worse"]} |')
    lines += ['', '## Changes and safeguards', '',
        '- **Masking:** removes only thin staff-row runs supported by horizontal ink coverage on both sides. '
        'Nearby stems and broad adjacent heads no longer erase most of a square head. A head must also contain '
        'connected ink spanning both dimensions, so sparse staff-line fragments cannot qualify as head evidence.',
        '- **Bar recovery:** chooses complete staff-bar voice sets before tie, beam and slur attachment. '
        'The frozen opening meter and global column cuts stay fixed. A candidate must retain every baseline '
        'physical head/pitch and add an image-verified head. Detector-supported durations remain bounded alternatives.',
        '- **Note/rest:** adds narrow, connected short-stem evidence only when there is an existing neural note '
        'alternative with credible staff position. It never manufactures a pitch or duration for a rest-only detection. '
        'Original model probabilities remain in audit fields; the .51 admission floor is not a calibrated probability.',
        '- Each frozen reading was first reproduced with exact XML and serialized event/source-ID equality. '
        'Local outputs also pass a final serialized physical-pitch retention guard.',
        '', '## Previously reviewed physical heads', '',
        'This is the purposeful five-song miss audit, not population accuracy. Emitting a physical head does not '
        'by itself verify its pitch or duration.', '',
        '| Variant | Reviewed heads | Emitted notes at head | False rests at head |', '|---|---:|---:|---:|']
    for n,c in reviewed_counts.items():
        lines.append(f'| {n} | {c["reviewed_heads"]} | {c["notes_emitted"]} | {c["false_rests_emitted"]} |')
    lines += ['', '## Regressions retained in the results', '',
        '| Dataset | Song ID | Song | Frozen edits | Masking | Bar recovery | Note/rest |',
        '|---|---|---|---:|---:|---:|---:|']
    for r in data['samples']:
        base = r['frozen']['comparison']['totals']['pitch_duration_edit_distance']
        edits = {n:v['comparison']['totals']['pitch_duration_edit_distance'] for n,v in r['variants'].items()}
        if any(e > base for e in edits.values()):
            lines.append(f'| {r["dataset"]} | {r["id"]} | {r["title"]} | {base} | '+
                ' | '.join(str(edits.get(n,'—')) for n in ('masking','bar_recovery','note_rest'))+' |')
    if (out/'source-review.json').exists():
        lines += ['', '## Source review and negative controls', '',
            'Eight additional note/rest recoveries in Newburgh, Sherburne and New Lebanon were visually '
            'confirmed as printed notes: [source crops](note-rest-source-review.jpg). All eight remain '
            'newly emitted notes in this final note/rest ablation.', '',
            'Review of an earlier trial found empty candidate boxes at Winter symbol 313 and Ocean symbol 706. '
            'Sparse staff-line fragments had passed quadrant counting while nearby stems passed the extension check. '
            'A generic connected-component extent check now rejects both without raising the ink-fraction threshold. '
            'The combined final outputs match frozen pitches, durations and onsets in both songs.', '',
            'The other reviewed regression additions are visible printed heads: Farewell To All 393, '
            'Fillmore 81/360/489 and Salem 320/332/348. These songs already have system/part grouping failures; '
            'the existence of the printed notes is established, while their final part assignment, pitch and '
            'duration still need verification. [Review crops](regression-source-review.jpg), '
            '[review decisions](source-review.json).']
    if 'tests' in validation:
        lines += ['', f'Tests: **{validation["tests"]["passed"]} passed**. '
            'Coverage includes real source positives, four genuine scanned half rests, empty source boxes, '
            'hollow heads, short/broken stems, cross-bar ties, fixed shared pickup/final cuts, candidate isolation '
            'and exception-safe hook restoration. [Test command and code hashes](checks.json).']
    lines += ['', '## Limits and next step', '',
        'The 1911 sources and 2025 references can differ. Edit distances measure disagreement, not pure recognition '
        'accuracy. The 20 were already inspected for diagnosis; they are not an independent test for these corrections. '
        'A retained note with a changed duration can still regress. No songs were removed after scoring.', '',
        '**Recommended:** validate the best supported combined correction on a further unused, source-screened set '
        'selected before recognition/scoring, and review remaining duration regressions.', '',
        '**Alternative:** keep only the masking repair enabled and retain local recovery/note-rest evidence as '
        'opt-in experiments until broader source review is complete.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps({k:validation[k] for k in ('songs','predictions_checked','reviewed_heads',
        'selected_staff_bars','global_guard_fallbacks','positive_short_stem_evidence')}, indent=2))
    print(out/'REPORT.md')


if __name__ == '__main__':
    main()
