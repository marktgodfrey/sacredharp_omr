#!/usr/bin/env python3
"""Build local HTML and Markdown reports for visually confirmed miss cases."""
from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIR = ROOT / "diagnostics/miss-trace"
DATA = DIR / "confirmed-misses.json"

STAGE_LABELS = {
    "accepted_note_clipped": "Accepted note clipped",
    "note_candidate_not_accepted": "Note candidate not accepted",
    "rest_only_no_recorded_note_proposal": "Rest only; no recorded note proposal",
    "note_suppressed_by_conflict_rule": "Note suppressed by conflict rule",
}


def esc(value):
    return html.escape(str(value), quote=True)


def stage_counts(cases):
    return Counter(c["stage"] for c in cases)


def exact_replays(cases):
    return sum(c.get("replay_verification", {}).get("status") == "EXACT" for c in cases)


def render_chop(case):
    chops = case.get("chop_evidence", [])
    if not chops:
        return "<p>No chop trace was recorded for this case.</p>"
    bits = []
    for chop in chops:
        cut = chop.get("cut", "unknown")
        bits.append(f'<details class="chop"><summary>Cut {esc(cut)}'
                    f' · source note ID {esc(chop.get("source_note_id", "—"))}</summary>')
        for label in ("input", "kept", "dropped"):
            events = chop.get(label, [])
            bits.append(f'<h5>{esc(label.title())} ({len(events)})</h5><ul>')
            for e in events:
                kind = e.get("kind", "event")
                if kind == "note":
                    alter = e.get("alter", 0)
                    alter_text = f"{alter:+g}" if isinstance(alter, (int, float)) and alter else ""
                    pitch = f'{e.get("step", "?")}{alter_text}{e.get("octave", "?")}'
                    desc = f'{pitch} {e.get("typ", "")} · dur {e.get("dur", "?")}'
                else:
                    desc = f'{kind} {e.get("typ", "")} · dur {e.get("dur", "?")}'
                bits.append(f'<li>SI {esc(e.get("si", "—"))}: {esc(desc)} at x={esc(e.get("x", "?"))}</li>')
            bits.append("</ul>")
        bits.append("</details>")
    return "".join(bits)


def evidence_probabilities(case):
    symbols = case.get("symbols_at_glyph", [])
    if not symbols:
        return "No symbol probability values recorded."
    rows = []
    for s in symbols:
        real = s.get("real", {})
        rows.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(s.get("sym_id", "—")), esc(s.get("detector_cls", "—")), esc(s.get("final_cls", "—")),
            esc(real.get("p", "—")), esc(real.get("det", "—"))))
    return '<table><thead><tr><th>Symbol ID</th><th>Detector class</th><th>Final class</th><th>Note/rest p</th><th>Detection conf.</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>"


def html_case(case):
    cid, stage = case["case_id"], case["stage"]
    image = case.get("evidence_image", "")
    bar = case.get("bar_image", "")
    source_url = case.get("source_url", "")
    title = case.get("title", "")
    symbols = ", ".join(str(x.get("sym_id")) for x in case.get("symbols_at_glyph", [])) or "none"
    source_ids = ", ".join(str(x) for x in case.get("review_anchor_ids", [])) or "none"
    crop = case.get("crop_box", [])
    crop_txt = ", ".join(map(str, crop)) if crop else "not recorded"
    full_bar = (f'<details class="bar"><summary>Show full-bar image</summary><img loading="lazy" src="{esc(bar)}" alt="Full bar for {esc(cid)}"></details>'
                if bar else "")
    scan = f'<a href="{esc(source_url)}" target="_blank" rel="noopener">Open public 1911 scan</a>' if source_url else "No public scan URL recorded"
    return f'''<article class="case" data-stage="{esc(stage)}" data-search="{esc((cid+' '+title+' '+case.get('song_id','')+' '+case.get('part','')+' '+stage+' '+str(case.get('shape',''))).lower())}">
<header><h3>{esc(cid)} · {esc(title)}</h3><span class="stage">{esc(STAGE_LABELS.get(stage, stage))}</span></header>
<p>{esc(case.get('song_id',''))} · {esc(case.get('part',''))} · shape {esc(case.get('shape',''))} · staff {esc(case.get('staff','—'))}, system {esc(case.get('system_index','—'))}, bar {esc(case.get('bar_index_in_staff','—'))}</p>
<p>Reviewed anchor IDs: {esc(source_ids)} · same-glyph symbol IDs: {esc(symbols)} · crop box: {esc(crop_txt)}</p>
<div class="images"><figure><img loading="lazy" src="{esc(image)}" alt="Reviewed note-head crop for {esc(cid)}"><figcaption>Reviewed head crop · magenta marks the reviewed head</figcaption></figure>{full_bar}</div>
<p>{scan}</p><details><summary>Case probabilities and source IDs</summary>{evidence_probabilities(case)}<p>Anchor symbol ID: {esc(case.get('anchor_sym_id','—'))}; recorded detections: {esc(len(case.get('recorded_detections_at_glyph', [])))}.</p></details>
<details><summary>Expandable chop trace</summary>{render_chop(case)}</details>
</article>'''


def build_html(data):
    cases = data["cases"]
    stages = stage_counts(cases)
    counterfactual = data.get("counterfactual", {}).get("summary")
    optional_cf = ""
    if counterfactual is not None:
        recovered = counterfactual['remove_confirmed_false_rests']
        restored = counterfactual['remove_rests_restore_conflict_losers']
        optional_cf = f'<p class="notice"><strong>Diagnostic replay:</strong> Removing only visually confirmed false rests lets {recovered} reviewed note candidates reach XML. Restoring the note candidates suppressed by the conflict rule raises that to {restored}. This uses scan-reviewed labels, is not an automatic fix, and does not establish correct pitch or duration. <a href="counterfactual.json">Detailed replay data</a>.</p>'
    case_json = json.dumps(cases, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Sacred Harp confirmed miss audit</title>
<style>
:root{{color-scheme:light;--ink:#24212b;--muted:#615b69;--line:#ddd7e1;--paper:#fff;--wash:#f6f3f7;--accent:#7d3c84}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--wash);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:28px 20px 60px}}h1{{line-height:1.15}}.notice{{background:#fff;border-left:4px solid var(--accent);padding:12px 16px}}.counts{{display:flex;gap:12px;flex-wrap:wrap}}.count{{background:white;border:1px solid var(--line);padding:12px 16px;border-radius:8px}}.controls{{position:sticky;top:0;background:#f6f3f7ee;padding:12px 0;display:flex;gap:12px;z-index:2}}input,select{{font:inherit;padding:9px;border:1px solid #aaa;border-radius:6px}}input{{flex:1}}.case{{background:white;border:1px solid var(--line);border-radius:10px;padding:18px;margin:16px 0}}.case header{{display:flex;justify-content:space-between;gap:12px;align-items:start}}h3{{margin:0}}.stage{{background:#eee7f0;padding:4px 9px;border-radius:20px;white-space:nowrap}}.images{{display:grid;grid-template-columns:minmax(180px,270px) 1fr;gap:18px;align-items:start}}figure{{margin:0}}figure img{{max-width:100%;height:auto;border:1px solid var(--line)}}figcaption{{font-size:.88em;color:var(--muted)}}.bar img{{max-width:100%;height:auto;margin-top:10px}}details{{margin:12px 0}}summary{{cursor:pointer;font-weight:600}}table{{border-collapse:collapse;margin:8px 0}}th,td{{border:1px solid var(--line);padding:5px 9px;text-align:left}}.chop{{margin-left:12px;border-left:2px solid var(--line);padding-left:10px}}.empty{{padding:24px}}@media(max-width:650px){{.images{{grid-template-columns:1fr}}.case header{{display:block}}}}
</style></head><body><main><h1>Sacred Harp 1911 confirmed miss audit</h1>
<p class="notice"><strong>Selection:</strong> {esc(data.get('selection', 'Purposeful stage-stratified candidate audit; not random proportions.'))} Completely undetected glyphs are outside this candidate-based audit.</p>
<p>{len(cases)} visually confirmed printed notes without corresponding emitted notes across {len(data.get('summary',{}).get('by_song',{}))} songs. All five writer replays exactly match the saved emitted note sequences. Staff, system, and bar indices below are zero-based geometry labels, not reference-edition measure numbers.</p>
<div class="counts"><div class="count"><strong>{sum(c.get('shape')=='la' for c in cases)}</strong><br>square / la cases</div>{''.join(f'<div class="count"><strong>{stages[k]}</strong><br>{esc(STAGE_LABELS.get(k,k))}</div>' for k in STAGE_LABELS if stages[k])}</div>
{optional_cf}<h2>Cases</h2><div class="controls"><input id="search" type="search" placeholder="Search case, song, part, shape, or stage"><select id="stage"><option value="">All stages</option>{''.join(f'<option value="{esc(k)}">{esc(STAGE_LABELS.get(k,k))}</option>' for k in STAGE_LABELS)}</select></div>
<div id="cases">{''.join(html_case(c) for c in cases)}</div><p><a href="confirmed-misses.json">Source case JSON</a> · <a href="confirmed-misses.csv">Source CSV</a> · <span class="legend">Legend: magenta outline marks the visually reviewed note head.</span></p>
<p>Stage labels describe the observed pipeline state for each reviewed case. Probabilities are recorded case evidence and do not establish model correctness. The added conflict rule wrongly suppressed 3 notes in this audit. These counts are observational; no before/after production claim is made.</p>
<h2>Limitations</h2><ul>{''.join(f'<li>{esc(x)}</li>' for x in data.get('limitations',[]))}<li>All five writer replays were EXACT, verifying saved pitch, duration, sequence, and source-ID serialization for these cases.</li></ul>
</main><script>
const cases={case_json};
const search=document.getElementById('search'), stage=document.getElementById('stage');
function filter(){{const q=search.value.toLowerCase(), s=stage.value;document.querySelectorAll('.case').forEach(c=>{{c.hidden=!!((s&&c.dataset.stage!==s)||(q&&!c.dataset.search.includes(q)));}});}}
search.addEventListener('input',filter);stage.addEventListener('change',filter);
</script></body></html>'''


def build_markdown(data):
    cases = data["cases"]
    stages = stage_counts(cases)
    by_song = Counter(c.get("title", "") for c in cases)
    lines = ["# Sacred Harp 1911 confirmed miss audit", "",
             f"**{len(cases)} visually confirmed printed notes without corresponding emitted notes; {sum(c.get('shape') == 'la' for c in cases)} square / la cases.**",
             "", f"**Selection:** {data.get('selection', 'Purposeful stage-stratified candidate audit.')}", "",
             "This is a purposeful stage-stratified candidate audit, not a random sample and not an estimate of population error proportions. Completely undetected glyphs are unmeasured.", "",
             f"All five writer replays were EXACT ({exact_replays(cases)}/{len(cases)} cases). Probabilities and source IDs below are recorded case evidence, not correctness scores.", "",
             "The added conflict rule wrongly suppressed 3 notes in this audit. Counts are observational; no before/after production claim is made.", "",
             "## Counts by stage", "", "| Stage | Cases |", "|---|---:|"]
    for stage, count in stages.items(): lines.append(f"| {STAGE_LABELS.get(stage, stage)} | {count} |")
    lines += ["", "## Counts by song", "", "| Song | Cases |", "|---|---:|"]
    for song, count in by_song.most_common(): lines.append(f"| {song} | {count} |")
    cf = data.get('counterfactual', {}).get('summary')
    if cf:
        lines += ['', '## Diagnostic replay', '',
                  f"Removing only visually confirmed false rests lets {cf['remove_confirmed_false_rests']} reviewed note candidates reach XML. Restoring the note candidates suppressed by the conflict rule raises that to {cf['remove_rests_restore_conflict_losers']}.", '',
                  'This uses scan-reviewed labels, is not an automatic correction rule, and does not establish correct pitch or duration. No reference notes were inserted and saved benchmark predictions were not changed. See [counterfactual data](counterfactual.json).']
    lines += ["", "## Case index", "", "See [interactive local index](index.html) for head crops, expandable full-bar views, filters, source scan links, and chop traces.", "",
              "| ID | Song | Part | Stage | Shape | Symbols | Note/rest p |", "|---|---|---|---|---|---|---|"]
    for c in cases:
        syms = c.get("symbols_at_glyph", [])
        symbol_text = ", ".join(f"{s.get('sym_id')} {s.get('final_cls', s.get('detector_cls',''))}" for s in syms) or "—"
        probs = ", ".join(f"{s.get('sym_id')}: {s.get('real',{}).get('p','—')}" for s in syms) or "—"
        lines.append(f"| {c.get('case_id')} | {c.get('title')} | {c.get('part')} | {STAGE_LABELS.get(c.get('stage'),c.get('stage'))} | {c.get('shape')} | {symbol_text} | {probs} |")
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in data.get("limitations", [])]
    return "\n".join(lines) + "\n"


def main():
    data = json.loads(DATA.read_text())
    if len(data.get("cases", [])) != 95:
        raise ValueError(f"expected 95 confirmed cases, got {len(data.get('cases', []))}")
    if exact_replays(data["cases"]) != len(data["cases"]):
        raise ValueError("not all writer replays are EXACT")
    (DIR / "index.html").write_text(build_html(data))
    (DIR / "REPORT.md").write_text(build_markdown(data))
    print(f"Wrote {DIR / 'index.html'} and {DIR / 'REPORT.md'} for {len(data['cases'])} cases")


if __name__ == "__main__":
    main()
