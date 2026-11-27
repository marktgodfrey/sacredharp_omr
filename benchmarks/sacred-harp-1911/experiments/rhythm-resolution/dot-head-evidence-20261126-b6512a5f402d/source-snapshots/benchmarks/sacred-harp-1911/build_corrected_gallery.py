#!/usr/bin/env python3
"""Build corrected saved results and viewers from the frozen bar-fit replay."""
from __future__ import annotations

import json
import shutil
import base64
import html
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import io

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "experiments" / "bar-fitting" / "gallery-source"
REPLAY = ROOT / "experiments" / "reader-v2" / "replay_bar_fit"
FROZEN_RESULTS = REPLAY / "results.json"
ORIGINAL_RESULTS = ROOT / "reader-gallery" / "results.json"



def actual_layout(xml_path: Path, trace: dict) -> dict:
    root = ET.parse(xml_path).getroot()
    parts = root.findall(".//part")
    # The trace is the saved final reading and records the actual emitted staff structure.
    return {"staves": len(trace.get("staves", [])), "systems": len(trace.get("systems", [])),
            "parts": len(parts)}


def make_viewer(image_path: Path, xml_path: Path, trace: dict, title: str) -> str:
    """Build an image viewer whose only highlighted boxes come from final writer events."""
    emitted = trace.get("writer", {}).get("emitted", [])
    boxes = {int(s["i"]): s["box"] for s in trace.get("syms", [])}
    symbols = [{"id": int(e["e.si"]), "kind": e.get("kind", "event"), "label": f"{e.get('kind','event')}, {e.get('typ','')} {int(e.get('dots',0))*'·'}".strip(", "), "box": boxes[int(e["e.si"])]}
               for e in emitted if int(e.get("e.si", -1)) in boxes]
    with Image.open(image_path) as source:
        width, height = source.size
    with Image.open(image_path) as source:
        source = source.convert("RGB")
        source.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        preview_width, preview_height = source.size
        preview = io.BytesIO()
        source.save(preview, "JPEG", quality=65, optimize=True)
    encoded = base64.b64encode(preview.getvalue()).decode("ascii")
    xml_name = xml_path.name
    score_svg = ""
    try:
        import verovio
        toolkit = verovio.toolkit()
        toolkit.setOptions({"pageWidth": 2100, "pageHeight": 2970, "scale": 40,
                            "adjustPageHeight": True, "footer": "none", "header": "auto"})
        if toolkit.loadFile(str(xml_path)):
            score_svg = "".join(f'<div class="score">{toolkit.renderToSVG(page)}</div>'
                                for page in range(1, toolkit.getPageCount() + 1))
    except ImportError:
        pass
    if not score_svg:
        score_svg = '<p>Score preview is unavailable in this build; download the MusicXML file to view the score.</p>'
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · transcription viewer</title><style>
*{{box-sizing:border-box}}body{{margin:0;font:16px/1.45 system-ui;background:#f6f5f1;color:#202929}}header{{padding:12px 18px;background:#fff;border-bottom:1px solid #ddd}}main{{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(330px,.85fr);min-height:calc(100vh - 86px)}}.pane{{overflow:auto;padding:14px}}#scan{{position:relative;width:min(100%,1200px);margin:auto}}#scan img{{display:block;width:100%;height:auto}}#overlay{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}}#overlay rect{{fill:#e02445;fill-opacity:.08;stroke:#c91535;stroke-width:3;vector-effect:non-scaling-stroke}}.score svg{{display:block;width:100%;height:auto;background:white;margin:0 0 10px;border:1px solid #ddd}}table{{border-collapse:collapse;width:100%;background:white;font-size:14px}}td,th{{padding:6px;border-bottom:1px solid #ddd;text-align:left}}a{{color:#075d65}}.note{{background:#fff;padding:12px;margin:0 0 12px}}@media(max-width:760px){{main{{display:block;height:auto}}.pane{{min-height:60vh}}}}
</style><header><strong>{html.escape(title)}</strong> · final transcription <span style="float:right"><a href="{html.escape(xml_name)}">Download MusicXML</a></span></header>
<main><section class="pane"><p class="note">Red boxes mark printed symbols linked by the final saved writer trace to emitted notes or rests. Generated padding rests have no source box.</p><label>Scan zoom <input id="zoom" type="range" min="500" max="2400" value="1200"></label><div id="scan"><img src="data:image/jpeg;base64,{encoded}" width="{preview_width}" height="{preview_height}" alt="{html.escape(title)} scan"><svg id="overlay" viewBox="0 0 {width} {height}" aria-label="Final emitted symbols">{''.join(f'<rect x="{b[0]}" y="{b[1]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}"><title>{html.escape(s["label"])}</title></rect>' for s in symbols for b in [s["box"]])}</svg></div></section>
<section class="pane"><h2>Transcribed score</h2><div class="score">{score_svg}</div><h3>Emitted events ({len(symbols)})</h3><table><thead><tr><th>Symbol</th><th>Event</th></tr></thead><tbody>{''.join(f'<tr><td>{s["id"]}</td><td>{html.escape(s["label"])}</td></tr>' for s in symbols)}</tbody></table></section></main><script>document.getElementById('zoom').addEventListener('input',e=>document.getElementById('scan').style.width=e.target.value+'px')</script></html>'''


def build() -> int:
    original = json.loads(ORIGINAL_RESULTS.read_text())
    replay = json.loads(FROZEN_RESULTS.read_text())
    by_id = {x["id"]: x for x in replay["samples"]}
    out_samples = []
    (OUT / "transcriptions").mkdir(parents=True, exist_ok=True)
    for old in original["samples"]:
        sid = old["id"]
        result = by_id[sid]
        variant = result["variants"]["verification_rhythm"]
        prediction_rel = variant["prediction"]
        xml_path = REPLAY / Path(prediction_rel).relative_to("replay_bar_fit")
        trace_path = xml_path.with_suffix(".trace.json")
        trace = json.loads(trace_path.read_text())
        input_path = ROOT / old["input"]
        viewer_xml = OUT / "transcriptions" / f"{sid}.musicxml"
        shutil.copyfile(xml_path, viewer_xml)
        viewer_html = make_viewer(input_path, xml_path, trace, old["title"])
        viewer_name = f"{sid}.html"
        (OUT / "transcriptions" / viewer_name).write_text(viewer_html, encoding="utf-8")
        layout = actual_layout(xml_path, trace)
        report = dict(old.get("report", {}))
        report.update(layout)
        report["layout_source"] = "final replay trace and MusicXML"
        out_samples.append({**old, "artifact_root": "experiments/bar-fitting/gallery-source",
                            "comparison": variant["comparison"], "report": report,
                            "prediction": f"transcriptions/{sid}.musicxml", "viewer": f"transcriptions/{viewer_name}",
                            "failed": False})
    raw = {"samples": out_samples, "aggregates": {
        "songs": replay["aggregates"]["verification_rhythm"]["songs"],
        "reference_notes": sum(s["comparison"]["totals"]["reference_notes"] for s in out_samples),
        "prediction_notes": sum(s["comparison"]["totals"]["prediction_notes"] for s in out_samples),
        "pitch_duration_edits": replay["aggregates"]["verification_rhythm"]["edits"],
        "denominator": replay["aggregates"]["verification_rhythm"]["denominator"],
        "pitch_duration_error_rate": replay["aggregates"]["verification_rhythm"]["rate"],
        "pitch_error_rate": sum(s["comparison"]["totals"]["pitch_edit_distance"] for s in out_samples) /
                            max(1, sum(s["comparison"]["totals"]["pitch_rate_denominator"] for s in out_samples)),
        "layout_count_failures": sum(s["report"]["staves"] != s.get("expected_staves") or
                                      s["report"]["systems"] != s.get("expected_systems") for s in out_samples),
        "part_count_failures": sum(s["report"]["parts"] != len(s["comparison"].get("line_order", [])) for s in out_samples),
        "failures": 0}}
    (OUT / "results.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(out_samples)


if __name__ == "__main__":
    print(f"Built corrected saved gallery source for {build()} songs at {OUT}")
