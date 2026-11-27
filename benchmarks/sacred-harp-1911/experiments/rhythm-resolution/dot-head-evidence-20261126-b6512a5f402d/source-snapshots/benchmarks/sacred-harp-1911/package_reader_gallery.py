#!/usr/bin/env python3
"""Package the saved reader-gallery results as an offline, self-contained site.

This script copies existing artifacts only; it does not run transcription or inference.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path

from PIL import Image

import build_reader_gallery


ROOT = Path(__file__).resolve().parent
DEFAULT_SITE_DIR = Path("/Users/mark/code/sh_omr/sites/sacred-harp-reader-1911")
EXPECTED_SAMPLES = 100
ZIP_LIMIT = 24 * 1024 * 1024


def _safe_id(value: str) -> str:
    if not value or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError(f"unsafe sample id: {value!r}")
    return value


def _copy_input(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as im:
        im.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        im.convert("RGB").save(destination, "JPEG", quality=65, optimize=True)


def _copy_viewer(source: Path, destination: Path, input_rel: str) -> None:
    text = source.read_text(encoding="utf-8")
    text, replacements = re.subn(
        r'(?<=src=")data:image/jpeg;base64,[A-Za-z0-9+/=]+(?=")',
        "../" + input_rel,
        text,
        count=1,
    )
    if replacements != 1:
        raise ValueError(f"expected one embedded JPEG in viewer {source}, found {replacements}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def _relative_source(root: Path, value: str, label: str) -> Path:
    p = Path(value)
    if p.is_absolute():
        raise ValueError(f"{label} must be a relative path in results.json: {value}")
    resolved = (root / p).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{label} escapes benchmark root: {value}")
    return resolved


def _zip_dist(dist: Path, archive: Path) -> int:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(dist.rglob("*")):
            if path.is_file() and "downloads" not in path.relative_to(dist).parts:
                zf.write(path, path.relative_to(dist).as_posix())
    return archive.stat().st_size


def package(site_dir: Path, results_path: Path, *, allow_partial: bool = False) -> tuple[int, int]:
    site_dir = site_dir.resolve()
    dist = site_dir / "dist"
    raw = json.loads(results_path.read_text(encoding="utf-8"))
    samples = raw.get("samples", [])
    if not allow_partial and len(samples) != EXPECTED_SAMPLES:
        raise ValueError(f"expected exactly {EXPECTED_SAMPLES} results, found {len(samples)} (use --allow-partial for preview QA)")
    if not samples:
        raise ValueError("results.json contains no samples")
    # Preserve any host identity/configuration; only replace the generated dist tree.
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)

    clean_samples = []
    clean_manifest_samples = []
    for sample in samples:
        sid = _safe_id(str(sample["id"]))
        input_rel = f"assets/inputs/{sid}.jpg"
        reference_rel = f"assets/references/{sid}.musicxml"
        preview_rel = f"assets/reference-previews/{sid}.html"
        prediction_rel = f"transcriptions/{sid}.musicxml"
        viewer_rel = f"transcriptions/{sid}.html"

        input_src = _relative_source(ROOT, sample["input"], f"input for {sid}")
        reference_src = _relative_source(ROOT, sample["reference"], f"reference for {sid}")
        preview_src = _relative_source(ROOT, f"reference/previews/{sid}.html", f"reference preview for {sid}")
        artifact_root = sample.get("artifact_root", "reader-gallery")
        prediction_src = _relative_source(ROOT, artifact_root + "/" + sample["prediction"], f"prediction for {sid}")
        viewer_src = _relative_source(ROOT, artifact_root + "/" + sample["viewer"], f"viewer for {sid}")
        for label, path in (("input", input_src), ("reference", reference_src), ("reference preview", preview_src),
                            ("prediction", prediction_src), ("viewer", viewer_src)):
            if not path.is_file():
                raise FileNotFoundError(f"missing {label} for {sid}: {path}")

        _copy_input(input_src, dist / input_rel)
        for source, target in ((reference_src, dist / reference_rel), (prediction_src, dist / prediction_rel),
                               (preview_src, dist / preview_rel)):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        _copy_viewer(viewer_src, dist / viewer_rel, input_rel)

        source_url = sample.get("source_url")
        if not isinstance(source_url, str) or not source_url.startswith(("https://", "http://")):
            raise ValueError(f"missing public full-scan URL for {sid}")
        clean = {
            "id": sid,
            "title": sample.get("title", sid),
            "printed_page_1911": sample.get("printed_page_1911", ""),
            "reference_page_2025": sample.get("reference_page_2025", ""),
            "scan_id": sample.get("scan_id", ""),
            "source_url": source_url,
            "source": source_url,
            "input": input_rel,
            "reference": reference_rel,
            "reference_preview": preview_rel,
            "expected_staves": sample.get("expected_staves"),
            "expected_systems": sample.get("expected_systems"),
            "comparison": sample.get("comparison", {}),
            "report": sample.get("report", {}),
            "prediction": prediction_rel,
            "viewer": viewer_rel,
            "failed": bool(sample.get("failed", False)),
        }
        clean_samples.append(clean)
        clean_manifest_samples.append({k: clean[k] for k in (
            "id", "title", "printed_page_1911", "reference_page_2025", "scan_id", "source_url", "source",
            "input", "reference", "reference_preview", "expected_staves", "expected_systems")})

    # Keep only presentation metrics; provenance can contain machine-local paths.
    aggregate_keys = ("songs", "reference_notes", "prediction_notes", "pitch_duration_edits", "denominator",
                      "pitch_duration_error_rate", "pitch_error_rate", "layout_count_failures", "part_count_failures", "failures")
    aggregates = {k: raw.get("aggregates", {})[k] for k in aggregate_keys if k in raw.get("aggregates", {})}
    clean_results = {"samples": clean_samples, "aggregates": aggregates}
    clean_manifest = {"samples": clean_manifest_samples}
    results_out = dist / "results.json"
    manifest_out = dist / "manifest.json"
    results_out.write_text(json.dumps(clean_results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_out.write_text(json.dumps(clean_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_reader_gallery.build(results_out, manifest_out, dist / "index.html")
    index_path = dist / "index.html"
    index_path.write_text(index_path.read_text(encoding="utf-8").replace("../assets/", "assets/"), encoding="utf-8")
    readme = (
        "Sacred Harp reader gallery\n"
        "==========================\n\n"
        "Open index.html in a browser to browse the saved transcriptions.\n"
        "Input scans, reference previews, reference MusicXML, and transcription files are included for offline use.\n"
        "The Full scan links point to the public Readux source and need an internet connection.\n"
    )
    (dist / "README.txt").write_text(readme, encoding="utf-8")

    archive = site_dir / "sacred-harp-gallery.zip"
    archive_size = _zip_dist(dist, archive)
    if archive_size < ZIP_LIMIT:
        downloads = dist / "downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive, downloads / archive.name)
        link = '<p><a href="downloads/sacred-harp-gallery.zip">Download this gallery as a ZIP</a></p>'
        # The hosted dist gets the download link after packaging, keeping the ZIP finite.
        index_path.write_text(index_path.read_text(encoding="utf-8").replace("<h1>1911 Sacred Harp · reader gallery</h1>",
                            "<h1>1911 Sacred Harp · reader gallery</h1>\n" + link), encoding="utf-8")
    return len(clean_samples), archive_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
    parser.add_argument("--results", type=Path, default=ROOT / "reader-gallery/results.json")
    parser.add_argument("--allow-partial", action="store_true", help="allow fewer than 100 samples for preview QA")
    args = parser.parse_args()
    count, size = package(args.site_dir, args.results.resolve(), allow_partial=args.allow_partial)
    print(f"Packaged {count} songs at {args.site_dir.resolve() / 'dist'}; ZIP {size:,} bytes at {args.site_dir.resolve() / 'sacred-harp-gallery.zip'}")


if __name__ == "__main__":
    main()
