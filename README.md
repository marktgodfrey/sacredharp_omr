# Sacred Harp OMR

Research workspace for optical music recognition of the 1911 Original Sacred
Harp: source-based note and rhythm recovery, benchmark comparisons, shape-note
rendering, CoreML experiments, and an iOS reader prototype.

Start with [HANDOFF.md](HANDOFF.md) for the current checkpoint, known failures,
and reproduction commands. The rhythm-resolution stage remains opt-in; this
repository does not enable it by default or republish the gallery.

## Repository layout

- `copisteria/`: a Git submodule with our Python, CoreML, shape-note, writer,
  and native iOS changes. Its upstream is
  [KobiMusic/copisteria](https://github.com/kobimusic/copisteria).
- `benchmarks/sacred-harp-1911/`: benchmark source, tests, manifests, and reports.
- `diagnostics/`: research notes and handoff history.
- `examples/`: demonstration pages, crops, transcriptions, and sample manifests.
- `scripts/workspace_snapshot.py`: create, verify, and restore data snapshots.

## Clone and set up

```sh
git clone --recurse-submodules https://github.com/marktgodfrey/sacredharp_omr.git
cd sacredharp_omr
python3.12 -m venv copisteria/.venv
copisteria/.venv/bin/python -m pip install -e './copisteria[experiment,test]'
```

For an existing clone, run `git submodule update --init --recursive`.
The submodule commit pins the exact Copisteria source used here; updating it
is an explicit parent-repository change.

## Restore the complete workspace data

The `workspace-2026-11-26` GitHub Release holds checksummed archives of **all**
saved benchmark runs, scans and inputs, references, predictions, diagnostic
outputs, model weights, CoreML exports, and the existing gallery checkout's
files. Environments, caches, and Git metadata are excluded. These files are
ignored by Git so ordinary clones stay small. Nothing is deleted locally.

```sh
gh release download workspace-2026-11-26 --repo marktgodfrey/sacredharp_omr \
  --dir workspace-snapshots/workspace-2026-11-26
python3 scripts/workspace_snapshot.py verify \
  workspace-snapshots/workspace-2026-11-26/MANIFEST.json
python3 scripts/workspace_snapshot.py restore \
  workspace-snapshots/workspace-2026-11-26/MANIFEST.json \
  --destination .
```

Restoration skips identical files and refuses to replace different files.
Use `--dry-run` to inspect restoration first. Restore before running the
benchmark suite: several tests intentionally use frozen experiment artifacts.
Historical runs and provenance manifests must remain immutable.

```sh
copisteria/.venv/bin/python -m pytest -q benchmarks/sacred-harp-1911 \
  copisteria/tests/test_front_write.py copisteria/tests/test_read_layout.py
```

The snapshot contains the local model weights and CoreML build that are absent
from upstream Git. For fresh model downloads, see
[Copisteria's model notes](copisteria/models/README.md); CoreML export instructions
are in its README and docs. Snapshot checksums capture the existing artifacts,
but do not make the original model conversion environment reproducible.
Some historical provenance files record original absolute workstation paths;
preserve them as evidence rather than rewriting their hashes.

## Work on Copisteria

Commit and push changes inside `copisteria/` first, then commit and push its
new submodule pointer in this repository:

```sh
git -C copisteria switch sacred-harp
# Edit, test, and commit inside copisteria/.
git -C copisteria push origin sacred-harp
git add copisteria
git commit -m "Update Copisteria checkpoint"
git push
```

The personal Copisteria repository retains upstream history. Its `upstream`
remote should point to `https://github.com/kobimusic/copisteria.git`; clones
can add that remote manually. Review upstream changes on a separate branch
before merging them into `sacred-harp`.

## Attribution and data

Copisteria is developed by KobiMusic and distributed under Apache-2.0. Keep its
[LICENSE](copisteria/LICENSE) and [NOTICE](copisteria/NOTICE). Bravura is bundled
under its accompanying SIL Open Font License. Scan and comparison data retain
their source provenance and any applicable original terms; the software's
license does not grant rights to third-party data. No new blanket license is
assigned to the surrounding research workspace here.
