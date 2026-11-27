"""Test new visual note alternatives against the latest saved local recovery.

Reference XML is opened only after every prediction in the selected batch is
saved. All neural/source evidence and output files have provenance hashes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from run_local_recovery import (ROOT, read, save, sha, samples, load_frozen, local_write,
    observations_for, holdout_observations, physical_loss, conventional_score, compare)
from bar_recovery import capture_built
from replay_writer_trace import _reading
from reader_trace import serialize_reading
from missing_note_proposals import (proposal_sites, visual_alternative, append_alternative,
    decode_appended, suppress_measure_rest_conflicts)
from forced_visual_probe import probe, PinnedInputs
from summarize_local_recovery import reviewed_status

LATEST = ROOT/'experiments/local-recovery/final-0996d2a689dc'


def baseline(s, source, image, frozen):
    sid = s['id']
    original = read(ROOT/s['baseline_trace'])
    obs = observations_for(sid) if s['dataset'] == 'development100' else holdout_observations(
        ROOT/'experiments/bar-fitting/unused20/cache', sid)
    old = _reading(copy.deepcopy(original), source)
    with capture_built() as passes:
        xml, _, _ = frozen.write_variant(old, image, obs, verification=True, rhythm=True, bar_fit=True)
    old_pass = next(p for p in reversed(passes) if p['xml'] == xml)
    rd = _reading(copy.deepcopy(original), source)
    with capture_built() as passes:
        xml, emitted, details = local_write(rd, image, obs, old_pass, note_rest=True)
    expected = LATEST/'note_rest'/f'{sid}.musicxml'
    assert xml == expected.read_text(), sid+' latest baseline replay mismatch'
    prior = read(expected.with_suffix('.trace.json'))
    assert emitted == prior['writer'], sid+' latest trace replay mismatch'
    return rd, obs, next(p for p in reversed(passes) if p['xml'] == xml), prior


def validate(xml, emitted, prior, rd, baseline_xml):
    root, old = ET.fromstring(xml), ET.fromstring(baseline_xml)
    pitched = [(n.findtext('pitch/step'), int(n.findtext('pitch/octave')),
        int(n.findtext('pitch/alter', '0')), int(n.findtext('duration', '0')))
        for n in root.findall('.//note') if n.find('pitch') is not None]
    assert pitched == [(e['step'], e['octave'], e['alter'], e['dur'])
                       for e in emitted['emitted'] if e['kind'] == 'note']
    assert not physical_loss(prior, emitted, rd.layout)
    assert [ET.tostring(t) for t in root.findall('.//attributes/time')] == [
        ET.tostring(t) for t in old.findall('.//attributes/time')]
    assert [len(p.findall('measure')) for p in root.findall('part')] == [
        len(p.findall('measure')) for p in old.findall('part')]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--titles', nargs='+')
    p.add_argument('--tag', default='pilot')
    p.add_argument('--probe-cache', type=Path, nargs='+', default=[])
    p.add_argument('--scales', type=float, nargs='+', default=[16., 20., 24.])
    args = p.parse_args()
    cache_paths = [f for path in args.probe_cache for f in
                   (sorted(path.glob('*.json')) if path.is_dir() else [path])]
    torch.set_num_threads(4)
    selected = [s for s in samples() if not args.titles or s['title'] in args.titles]
    # Cover the runtime, decoder, layout, policy, observation helpers and scorer.
    code = list(ROOT.glob('*.py')) + list((ROOT.parents[1]/'copisteria/src/copisteria').rglob('*.py'))
    model_files = [f for f in (ROOT.parents[1]/'copisteria/out/coreml').rglob('*') if f.is_file()]
    inputs = [ROOT.parents[1]/'copisteria/models/yolo_v7_taxonomy.json',
              ROOT/'diagnostics/miss-trace/confirmed-misses.json',
              LATEST/'results.json', ROOT/'reader-gallery/results.json',
              ROOT/'experiments/bar-fitting/unused20/manifest.json',
              ROOT/'experiments/bar-fitting/unused20/results.json',
              ROOT/'experiments/reader-v2/replay_bar_fit/results.json']
    for s in selected:
        inputs += [ROOT/s['input'], ROOT/s['baseline_trace'], ROOT/s['old_prediction'],
                   LATEST/'note_rest'/f"{s['id']}.musicxml",
                   LATEST/'note_rest'/f"{s['id']}.trace.json"]
        cache = ROOT/('reader-gallery/cache' if s['dataset'] == 'development100'
                     else 'experiments/bar-fitting/unused20/cache')
        inputs += [cache/f"{s['id']}.{v}.json" for v in ('base','staff16')]
    inputs += [p.resolve() for p in cache_paths]
    provenance = {str(f.relative_to(ROOT.parents[1])): sha(f) for f in sorted(set(code+inputs+model_files))}
    key = hashlib.sha256(json.dumps({'sha256': provenance, 'scales': args.scales}, sort_keys=True).encode()).hexdigest()
    out = ROOT/'experiments/missing-proposals'/f'{args.tag}-{key[:12]}'
    for f in code:
        dest = out/'source-snapshots'/f.relative_to(ROOT.parents[1])
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(f, dest)
    cached, cached_files = {}, {}
    for cache_path in cache_paths:
        match = re.fullmatch(r'(.+)-(\d+)-sp([\d.]+)\.json', cache_path.name)
        if match:
            cached_files[(match[1], int(match[2]), float(match[3]))] = cache_path
            continue
        raw = read(cache_path)
        for entry in raw.get('probes', [raw]):
            ck = (str(Path(entry['image']).resolve()), tuple(entry['head_box']), float(entry['target_spacing_px']))
            cached[ck] = entry
    frozen = load_frozen()
    detector = model = None
    cases = read(ROOT/'diagnostics/miss-trace/confirmed-misses.json')['cases']
    results = []
    for j, s in enumerate(selected, 1):
        sid = s['id']; dest = out/'predictions'/f'{sid}.musicxml'
        rec_path = out/'records'/f'{sid}.json'
        if rec_path.exists():
            row = read(rec_path); assert row['experiment_key'] == key
            assert sha(dest) == row['sha256']; results.append(row); continue
        print(f'[{j}/{len(selected)}] {s["title"]}', flush=True)
        start = time.perf_counter()
        source = Image.open(ROOT/s['input']).convert('L')
        image = source
        if s['layout_choice'] == 'normalized':
            from copisteria.front import clean_page
            image = Image.fromarray(clean_page(np.asarray(source)))
        rd, obs, prior_pass, prior = baseline(s, source, image, frozen)
        sites = proposal_sites(rd, image)
        additions = []
        for site in sites:
            alternatives = []
            for scale in args.scales:
                ck = (str((ROOT/s['input']).resolve()), tuple(site['box']), scale)
                visual = cached.get(ck)
                cache_file = cached_files.get((sid, site['anchor_id'], scale))
                if visual is None and cache_file:
                    visual = read(cache_file)
                    assert str(Path(visual['image']).resolve()) == ck[0]
                    assert tuple(visual['head_box']) == ck[1]
                if visual is None:
                    if detector is None:
                        from copisteria.coreml_runtime import CoreMLDetector
                        detector = CoreMLDetector(ROOT.parents[1]/'copisteria/out/coreml', units='CPU_ONLY')
                        detector.model.backbone = PinnedInputs(detector.model.backbone)
                        detector.model.verifier = PinnedInputs(detector.model.verifier)
                    visual = probe(detector, ROOT/s['input'], site['box'], site['staff_space'], str(site['anchor_id']), scale)
                alt = visual_alternative(visual, site)
                if alt:
                    alternatives.append({**alt, 'target_spacing': scale})
                # Keep full raw posteriors for matching head ROIs. The neural
                # verifier still saw all natural peaks; unrelated output rows
                # cannot enter selection and need not bloat each saved probe.
                from reader_policy import near_head
                def matching(r):
                    bb = r['refined_source_xyxy']; sp = site['staff_space']
                    return (near_head(site['box'], bb, .6*sp)
                        and .45*sp <= bb[2]-bb[0] <= 1.9*sp and .4*sp <= bb[3]-bb[1] <= 1.9*sp)
                retained = [r for r in visual['records'] if matching(r)]
                save(out/'probes'/f'{sid}-{site["anchor_id"]}-sp{scale:g}.json',
                     {**visual, 'full_record_count': visual.get('verifier_cell_count'),
                      'retained_record_count': len(retained),
                      'probe_natural_peak_cap': min(visual.get('model_max_candidates', 2000), 2000)
                          - visual['forced_unique_cell_count'], 'records': retained})
            alternative = max(alternatives, key=lambda a: a['position_weighted_selection_score'], default=None)
            entry = {**site, 'visual_alternative': alternative, 'proposal_id': None}
            if alternative:
                entry['proposal_id'] = append_alternative(rd, site, alternative)
            additions.append(entry)
        ids = [a['proposal_id'] for a in additions if a['proposal_id'] is not None]
        if ids:
            if model is None:
                from copisteria.coreml_runtime import CoreMLEvidence
                model = CoreMLEvidence(ROOT.parents[1]/'copisteria/out/coreml', units='CPU_ONLY')
                model.native = PinnedInputs(model.native)
            decode_appended(rd, ids, model)
        # A contextual note reading still needs independent visual support and
        # a staff-position reading compatible with its physical box.
        proposal_verifications = {}
        for a in additions:
            i = a['proposal_id']
            if i is None:
                a['decision'] = 'no_matching_visual_roi'; continue
            r = rd.tok[i]
            a['context_reading'] = copy.deepcopy(r)
            # A strong symbolic context can overcome even the near-zero prior
            # of an incompatible duration. Enforce the independent source ink
            # constraint, retaining the rejected context reading above.
            sym = rd.layout.syms[i]
            from copisteria.vocab import CLS_ID
            if r['cls']['v'].startswith('note_') and CLS_ID[r['cls']['v']] not in sym.post:
                a['duration_constraint'] = {'from': r['cls']['v'], 'to': sym.cls,
                    'reason': 'source_head_fill', 'calibrated_probability': False}
                r['cls'] = {'v': sym.cls, 'p': max(sym.post.values()), 'det': sym.cls,
                    'source_constraint': True}
            st = rd.layout.staves[a['staff']]
            pos = round((st.mid-(a['box'][1]+a['box'][3])/2)*2/st.sp)
            stem = a['head_evidence']['stem_found'] or a['short_stem_evidence']['found']
            supported = (a['visual_alternative']['visual_note_probability'] >= .05
                and r['cls']['v'].startswith('note_') and r.get('pos', {}).get('p', 0) >= .6
                and abs(r['pos']['v']-pos) <= 1)
            a['decision'] = 'visual_context_supported' if supported else 'abstain'
            filled_support = (supported and a['head_evidence']['head_ink_fraction'] >= .55
                and a['visual_alternative']['visual_note_probability'] >= .1)
            hollow_support = supported and a['head_morphology']['hollow_head']
            if not supported:
                r['real']['proposal_original_p'] = r['real']['p']; r['real']['p'] = 0
                r['real']['det'] = 0  # prevents the existing admission helper bypassing this visual gate
            elif (stem or filled_support or hollow_support) and r['real']['p'] < .5:
                # Explicit image-supported writer admission, not a calibrated
                # probability. The raw visual/context values remain above.
                r['real']['proposal_original_p'] = r['real']['p']; r['real']['p'] = .51
            if supported and (stem or filled_support or hollow_support):
                proposal_verifications[i] = {'note_proposal_supported': True,
                    'proposal_support_kind': ('head_and_stem' if stem else
                        'hollow_head_and_visual_note' if hollow_support else 'filled_head_and_visual_note'),
                    'visual_note_probability': a['visual_alternative']['visual_note_probability']}
                # Replace only the mutually exclusive interpretation at this
                # same physical head; unrelated rests remain intact.
                rest = rd.tok[a['anchor_id']]
                if rest['real']['p'] >= .5:
                    rest['real']['proposal_original_p'] = rest['real']['p']; rest['real']['p'] = 0
            if supported:
                v = a['visual_alternative']['record']
                obs += [{'cls': k, 'xyxy': a['box'], 'conf': v['objectness_probability']*prob}
                    for k, prob in v['class_probabilities'].items() if k.startswith('note_')]
        rest_conflicts = suppress_measure_rest_conflicts(rd, proposal_verifications)
        from copisteria.vocab import CLASSES
        duration_constraints = {i: {CLASSES[c].split('_', 1)[1] for c in rd.layout.syms[i].post}
                                for i in ids}
        xml, emitted, details = local_write(rd, image, obs, prior_pass, note_rest=True,
            proposal_verifications=proposal_verifications, duration_constraints=duration_constraints)
        details['whole_measure_rest_conflicts'] = rest_conflicts
        details['proposal_duration_constraints'] = {str(i): sorted(v) for i, v in duration_constraints.items()}
        lost = physical_loss(prior, emitted, rd.layout)
        assert not lost, (sid, lost)
        validate(xml, emitted, prior, rd, prior_pass['xml'])
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(xml)
        trace = {**serialize_reading(rd), 'writer': emitted, **details, 'new_note_proposals': additions}
        save(dest.with_suffix('.trace.json'), trace)
        row = {'id': sid, 'title': s['title'], 'dataset': s['dataset'], 'experiment_key': key,
            'prediction': str(dest.relative_to(ROOT)), 'sha256': sha(dest),
            'sites': len(sites), 'proposals': len(ids),
            'supported': sum(a['decision'] == 'visual_context_supported' for a in additions),
            'new_notes_emitted': sum(e['kind'] == 'note' and e['e.si'] in ids for e in emitted['emitted']),
            'reviewed': reviewed_status(trace, [c for c in cases if c['song_id'] == sid]),
            'latest_exact_replay': True, 'seconds': time.perf_counter()-start}
        save(rec_path, row); results.append(row)
        print(f"  sites={row['sites']} proposals={row['proposals']} supported={row['supported']} emitted={row['new_notes_emitted']} ({row['seconds']:.1f}s)", flush=True)
    save(out/'predictions-complete.json', {'experiment_key': key, 'sha256': provenance,
        'references_opened_during_generation': False, 'ids': [s['id'] for s in selected]})
    latest = {s['id']: s for s in read(LATEST/'results.json')['samples']}
    for row, s in zip(results, selected):
        reference = ROOT/s['reference']; assert sha(reference) == s['reference_sha256']
        row['baseline_comparison'] = latest[s['id']]['variants']['note_rest']['comparison']
        row['comparison'] = compare(conventional_score(reference, s['voice_count']),
                                   conventional_score(ROOT/row['prediction'], s['voice_count']))
    save(out/'results.json', {'experiment_key': key, 'samples': results, 'provenance': provenance})
    print(out, flush=True)


if __name__ == '__main__':
    main()
