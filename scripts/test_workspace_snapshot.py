import json
from pathlib import Path
import sys
import tarfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workspace_snapshot as ws


def fixture_tree(tmp_path):
    root=tmp_path/"root"
    (root/"benchmarks/sacred-harp-1911/experiments/run").mkdir(parents=True)
    (root/"benchmarks/sacred-harp-1911/experiments/run/result.bin").write_bytes(b"result"*1000)
    (root/"copisteria/models/nested").mkdir(parents=True)
    (root/"copisteria/models/nested/model.pt").write_bytes(b"weights")
    (root/"sites/sacred-harp-reader-1911/.git").mkdir(parents=True)
    (root/"sites/sacred-harp-reader-1911/index.html").write_text("site")
    (root/"sites/sacred-harp-reader-1911/.git/secret").write_text("omit")
    (root/"benchmarks/sacred-harp-1911/experiments/run/.DS_Store").write_text("omit")
    return root


def snapshot(tmp_path):
    root=fixture_tree(tmp_path)
    manifest=ws.pack(tmp_path/"archives",root,prefix="test",max_part_mib=1)
    return root,manifest


def test_roundtrip_and_skip_identical(tmp_path):
    root,manifest=snapshot(tmp_path)
    doc=ws.verify(manifest)
    assert doc["counts"]["files"] == 3
    dest=tmp_path/"restore"
    ws.restore(manifest,dest)
    assert (dest/"benchmarks/sacred-harp-1911/experiments/run/result.bin").read_bytes()==b"result"*1000
    actions=ws.restore(manifest,dest,dry_run=True)
    assert len(actions)==3 and all(x.startswith("skip-identical:") for x in actions)
    ws.restore(manifest,dest)


def test_conflict_preflight_leaves_other_files_unwritten(tmp_path):
    _,manifest=snapshot(tmp_path); dest=tmp_path/"restore"
    (dest/"sites/sacred-harp-reader-1911").mkdir(parents=True)
    (dest/"sites/sacred-harp-reader-1911/index.html").write_text("different")
    with pytest.raises(ws.SnapshotError,match="destination conflict"):
        ws.restore(manifest,dest)
    assert not (dest/"benchmarks/sacred-harp-1911/experiments/run/result.bin").exists()


def test_tamper_rejected(tmp_path):
    _,manifest=snapshot(tmp_path)
    doc=json.loads(manifest.read_text())
    with (manifest.parent/doc["assets"][0]["path"]).open("ab") as f: f.write(b"tamper")
    with pytest.raises(ws.SnapshotError,match="checksum mismatch"):
        ws.verify(manifest)


def test_manifest_path_traversal_rejected(tmp_path):
    _,manifest=snapshot(tmp_path)
    doc=json.loads(manifest.read_text())
    doc["assets"][0]["members"][0]["path"]="../escape"
    manifest.write_text(json.dumps(doc))
    with pytest.raises(ws.SnapshotError,match="unsafe manifest path"):
        ws.verify(manifest)


def test_symlink_inputs_rejected(tmp_path):
    root=fixture_tree(tmp_path)
    outside=tmp_path/"outside"; outside.write_text("no")
    (root/"benchmarks/sacred-harp-1911/experiments/run/external").symlink_to(outside)
    with pytest.raises(ws.SnapshotError,match="symlink file"):
        ws.pack(tmp_path/"archives",root)


def test_pack_refuses_existing_output_and_archived_subdirectory(tmp_path):
    root=fixture_tree(tmp_path); existing=tmp_path/"present"; existing.mkdir()
    with pytest.raises(ws.SnapshotError,match="already exists"):
        ws.pack(existing,root)
    with pytest.raises(ws.SnapshotError,match="inside archived tree"):
        ws.pack(root/"benchmarks/sacred-harp-1911/experiments/backup",root)


def test_pack_rejects_unsafe_prefix(tmp_path):
    root=fixture_tree(tmp_path)
    with pytest.raises(ws.SnapshotError,match="prefix"):
        ws.pack(tmp_path/"archives",root,prefix="../escape")


def test_restore_preflights_file_ancestor(tmp_path):
    _,manifest=snapshot(tmp_path); dest=tmp_path/"restore"
    (dest/"benchmarks").parent.mkdir(parents=True,exist_ok=True)
    (dest/"benchmarks").write_text("blocking file")
    with pytest.raises(ws.SnapshotError,match="ancestor is not a directory"):
        ws.restore(manifest,dest)
    assert (dest/"benchmarks").is_file()
