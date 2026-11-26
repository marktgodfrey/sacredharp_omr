# Preserved workspace snapshot

[`workspace-2026-11-26.manifest.json`](workspace-2026-11-26.manifest.json)
records the 29,829 files in the complete saved data snapshot: 10,181,785,755
uncompressed bytes in eleven independently readable tar.gz archives
(2,990,154,309 compressed bytes).

Download the assets from the
[`workspace-2026-11-26` release](https://github.com/marktgodfrey/sacredharp_omr/releases/tag/workspace-2026-11-26).
Use the release's `MANIFEST.json` alongside its archive parts, following the
[root README](../README.md#restore-the-complete-workspace-data).
`SHA256SUMS` also supports ordinary `shasum -a 256 -c SHA256SUMS` verification.

Source checkpoint: parent repository `8e82a79`, Copisteria submodule
`8db7c33747203e466203b61e1aa59a20f8f991bc`. The snapshot includes the current
rhythm-resolution final, every earlier saved experiment, source scans and
crops, references, model weights, CoreML exports, and the existing gallery
files. Git history is in the repositories; environments, caches, and personal
Xcode settings are excluded. The gallery's hosting is unchanged.

The manifest includes a SHA-256 for each file and each archive. Restoring the
snapshot refuses to replace a different existing file. Preserve historical
artifact contents and provenance hashes when continuing research.

Validation: a fresh clone from GitHub checked out the pinned submodule and
restored all 29,829 data files. The restored checkout passed 196 tests across
the benchmark, writer/layout, and snapshot utility suites. All eleven archive
checksums and every archived member checksum were verified before publication.
