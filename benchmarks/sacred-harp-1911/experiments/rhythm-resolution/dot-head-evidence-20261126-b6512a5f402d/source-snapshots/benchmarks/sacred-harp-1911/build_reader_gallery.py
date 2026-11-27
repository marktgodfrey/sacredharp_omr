#!/usr/bin/env python3
"""Build a searchable gallery from saved single-run reader results; performs no inference."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
GALLERY = ROOT / "reader-gallery"


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def href(path, base_dir, *, original_root=False):
    if not path:
        return ""
    # Result artifacts are rooted in reader-gallery; manifest paths are rooted in the benchmark.
    path = str(path)
    if path.startswith(("http://", "https://")):
        return path
    return quote(("../" if original_root else "") + path.lstrip("/"), safe="/.-_~")


def link(path, label, base_dir, *, original_root=False):
    if not path:
        return esc(label)
    return f'<a href="{esc(href(path, base_dir, original_root=original_root))}">{esc(label)}</a>'


def percent(value):
    return f"{100 * float(value):.1f}%"


def part_table(comparison):
    lines = ['<table class="parts"><thead><tr><th>Part</th><th>Reference notes</th><th>Transcribed notes</th><th>Pitch</th><th>Pitch + duration</th></tr></thead><tbody>']
    per_part = comparison.get("per_line", {})
    order = comparison.get("line_order", list(per_part))
    for name in order:
        item = per_part.get(name, {})
        if not item.get('reference_notes') and not item.get('prediction_notes'):
            continue
        lines.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            esc(name), esc(item.get("reference_notes", 0)), esc(item.get("prediction_notes", 0)),
            percent(item.get("pitch_error_rate", 0)), percent(item.get("pitch_duration_error_rate", 0))))
    lines.append("</tbody></table>")
    return "".join(lines)


def build(results_path=GALLERY / 'results.json', manifest_path=GALLERY / 'manifest.json', output_path=GALLERY / 'index.html'):
    results_path, manifest_path, output_path = map(lambda p: Path(p).resolve(), (results_path, manifest_path, output_path))
    results = json.loads(results_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    manifest_by_id = {s["id"]: s for s in manifest.get("samples", [])}
    samples = results.get("samples", [])
    aggregates = results.get("aggregates", {})

    rows, sections = [], []
    for sample in samples:
        sid = sample["id"]
        meta = {**manifest_by_id.get(sid, {}), **sample}
        title, page = meta.get("title", sid), meta.get("printed_page_1911", "")
        comparison, report = sample.get("comparison", {}), sample.get("report", {})
        totals = comparison.get("totals", {})
        rate = totals.get("pitch_duration_error_rate", 0)
        parts = report.get("parts", "")
        if isinstance(parts, list):
            parts = len(parts)
        systems = report.get("systems", "")
        anchor = quote(sid, safe="-_.")
        rows.append(f'<tr data-title="{esc(title.casefold())}" data-page="{esc(page)}" data-rate="{float(rate)}" data-parts="{esc(parts)}" data-systems="{esc(systems)}"><td><a href="#{anchor}">{esc(title)}</a></td><td>{esc(page)}</td><td>{percent(rate)}</td><td>{esc(parts)} / {esc(systems)}</td></tr>')

        source, input_image = meta.get("source"), meta.get("input")
        reference = meta.get("reference")
        preview = meta.get("reference_preview", f"reference/previews/{sid}.html")
        links = [link(source, "Full scan", ROOT, original_root=True),
                 link(input_image, "Model input", ROOT, original_root=True),
                 link(sample.get("viewer"), "Transcription viewer", GALLERY),
                 link(sample.get("prediction"), "Transcription XML", GALLERY),
                 link(reference, "2025 reference XML", ROOT, original_root=True),
                 link(preview, "2025 engraved score", ROOT, original_root=True)]
        image = (f'<details class="scan"><summary>Show input image</summary><img loading="lazy" src="{esc(href(input_image, GALLERY, original_root=True))}" alt="{esc(title)} input image"></details>'
                 if input_image else "")
        metadata = [f'{esc(report.get("staves", ""))} staves · {esc(systems)} systems · {esc(parts)} parts'
                    if report.get("staves") is not None else ""]
        meta_text = " · ".join(x for x in metadata if x)
        sections.append(f'<section id="{anchor}"><h2>{esc(title)} <small>· {esc(page)}</small></h2><p class="links">{" · ".join(links)}</p><p class="meta">{meta_text}</p>{image}{part_table(comparison)}</section>')

    n = aggregates.get("songs", len(samples))
    total_edits = aggregates.get("pitch_duration_edits", 0)
    denom = aggregates.get("denominator", 0)
    rate = aggregates.get("pitch_duration_error_rate", total_edits / denom if denom else 0)
    pitch_rate = aggregates.get("pitch_error_rate")
    pitch_text = f" Pitch-only disagreement is {percent(pitch_rate)}." if pitch_rate is not None else ""
    html_doc = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>1911 Sacred Harp · reader gallery</title>
<style>
:root{{--ink:#202c2c;--teal:#136b70;--line:#d9dfdc;--paper:#faf9f5;--head:#e6eeeb}}
body{{max-width:1100px;margin:40px auto;padding:0 24px;font:16px/1.55 system-ui;background:var(--paper);color:var(--ink)}}
h1,h2,h3{{line-height:1.2}}a{{color:var(--teal)}}table{{border-collapse:collapse;width:100%;background:#fff;margin:20px 0}}td,th{{padding:9px 13px;border-bottom:1px solid #ddd;text-align:left}}th{{background:var(--head)}}section{{margin:48px 0;border-top:2px solid var(--line);padding-top:20px}}img{{max-width:100%;height:auto}}summary{{cursor:pointer}}small{{font-size:.75em;color:#596664}}.meta{{color:#52605e}}.links{{line-height:1.9}}.parts{{font-size:.94rem}}.parts th{{font-weight:600}}input{{padding:9px;font:inherit;width:260px;max-width:80%}}button{{font:inherit;background:transparent;border:0;color:inherit;cursor:pointer;text-decoration:underline}}.summary{{padding:12px 16px;background:#fff;border-left:4px solid var(--teal)}}
</style></head><body>
<h1>1911 Sacred Harp · reader gallery</h1>
<p>Transcriptions of {esc(n)} songs from the 1911 <i>Original Sacred Harp</i>, produced with a shape-note reading workflow and reviewed against the supplied 2025 edition.</p>
<p>Pitch + duration disagreement counts the per-part sequence edits needed to match written pitch and notated duration: {esc(total_edits)} edits across {esc(denom)} positions ({percent(rate)}). Lower means fewer sequence edits.{pitch_text} The 2025 files are edition references, not fully proofread 1911 ground truth; edition differences can contribute to disagreement.</p>
<p class="summary">{esc(aggregates.get('layout_count_failures', 0))} songs have a staff/system count mismatch; {esc(aggregates.get('part_count_failures', 0))} have a part count mismatch; {esc(aggregates.get('failures', 0))} transcriptions failed.</p>
<p>{link('results.json','Results JSON',GALLERY)} · {link('manifest.json','Dataset manifest',GALLERY)}</p>
<p><label>Find a song <input id="filter" type="search" placeholder="Title or printed page"></label> Click a column heading to sort.</p>
<table><thead><tr><th><button data-sort="title">Song</button></th><th><button data-sort="page">1911 page</button></th><th><button data-sort="rate">Pitch + duration</button></th><th><button data-sort="parts">Parts / systems</button></th></tr></thead><tbody id="summary-rows">{"".join(rows)}</tbody></table>
{"".join(sections)}
<script>
const tbody=document.getElementById('summary-rows');document.getElementById('filter').addEventListener('input',e=>{{const q=e.target.value.toLowerCase();for(const r of tbody.rows)r.hidden=!r.textContent.toLowerCase().includes(q)}});
let direction=1,last='';for(const b of document.querySelectorAll('[data-sort]'))b.addEventListener('click',()=>{{const key=b.dataset.sort;direction=key===last?-direction:1;last=key;[...tbody.rows].sort((a,c)=>{{const av=a.dataset[key],cv=c.dataset[key],an=Number(av),cn=Number(cv);return direction*(Number.isNaN(an)||Number.isNaN(cn)?av.localeCompare(cv,undefined,{{numeric:true,sensitivity:'base'}}):an-cn)}}).forEach(r=>tbody.append(r))}});
</script></body></html>'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc)
    return len(samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=GALLERY / "results.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "manifest.json")
    parser.add_argument("--output", type=Path, default=GALLERY / "index.html")
    args = parser.parse_args()
    print(f"Built gallery for {build(args.results, args.manifest, args.output)} songs: {args.output}")


if __name__ == "__main__":
    main()
