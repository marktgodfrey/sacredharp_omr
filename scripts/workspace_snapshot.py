#!/usr/bin/env python3
"""Pack, verify, and restore selected workspace data as checksummed tar.gz parts.

Examples: workspace_snapshot.py pack --output /backup/snapshot
          workspace_snapshot.py verify /backup/snapshot/MANIFEST.json
          workspace_snapshot.py restore /backup/snapshot/MANIFEST.json --destination /restore
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile
from typing import BinaryIO, Iterable

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
PRUNE = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".DS_Store"}
EXACT_DIRS = (
    "benchmarks/sacred-harp-1911/experiments", "benchmarks/sacred-harp-1911/diagnostics",
    "benchmarks/sacred-harp-1911/sources", "benchmarks/sacred-harp-1911/reader-gallery",
    "benchmarks/sacred-harp-1911/reference", "benchmarks/sacred-harp-1911/predictions",
    "benchmarks/sacred-harp-1911/inputs", "benchmarks/sacred-harp-1911/error-examples",
    "copisteria/out", "sites/sacred-harp-reader-1911",
)
CHUNK = 1024 * 1024


class SnapshotError(Exception):
    pass


def _sha_stream(stream: BinaryIO) -> tuple[str, int]:
    h = hashlib.sha256(); size = 0
    while True:
        block = stream.read(CHUNK)
        if not block: break
        h.update(block); size += len(block)
    return h.hexdigest(), size


def _selected(root: Path) -> list[Path]:
    root = root.resolve()
    candidates: set[Path] = set()
    for rel in EXACT_DIRS:
        base = root / rel
        if not base.exists(): continue
        if base.is_symlink(): raise SnapshotError(f"refusing symlink data root: {base}")
        for current, dirs, files in os.walk(base, topdown=True, followlinks=False):
            here = Path(current)
            keep_dirs = []
            for name in sorted(dirs):
                p = here / name
                if name in PRUNE: continue
                if p.is_symlink(): raise SnapshotError(f"refusing symlink directory: {p}")
                keep_dirs.append(name)
            dirs[:] = keep_dirs
            for name in sorted(files):
                p = here / name
                if name in PRUNE: continue
                if p.is_symlink(): raise SnapshotError(f"refusing symlink file: {p}")
                if not p.is_file(): continue
                candidates.add(p)
    models = root / "copisteria/models"
    if models.exists():
        if models.is_symlink(): raise SnapshotError(f"refusing symlink data root: {models}")
        for current, dirs, files in os.walk(models, topdown=True, followlinks=False):
            here = Path(current); kept=[]
            for name in sorted(dirs):
                p=here/name
                if name in PRUNE: continue
                if p.is_symlink(): raise SnapshotError(f"refusing symlink directory: {p}")
                kept.append(name)
            dirs[:]=kept
            for name in sorted(files):
                p=here/name
                if name in PRUNE: continue
                if p.is_symlink(): raise SnapshotError(f"refusing symlink file: {p}")
                if p.suffix == ".pt" and p.is_file(): candidates.add(p)
    return sorted(candidates, key=lambda p: p.relative_to(root).as_posix())


def _safe_rel(value: str) -> str:
    p = PurePosixPath(value)
    if p.is_absolute() or not p.parts or any(x in ("", ".", "..") for x in p.parts) or "\\" in value:
        raise SnapshotError(f"unsafe manifest path: {value!r}")
    return p.as_posix()


class _HashingReader:
    def __init__(self, stream: BinaryIO): self.stream=stream; self.hash=hashlib.sha256(); self.count=0
    def read(self, n=-1):
        b=self.stream.read(n)
        if b: self.hash.update(b); self.count+=len(b)
        return b


def pack(output: Path, root: Path = DEFAULT_ROOT, prefix: str = "workspace-2026-11-26", max_part_mib: int = 900) -> Path:
    root=root.resolve(); output=output.expanduser().resolve()
    if max_part_mib < 1: raise SnapshotError("--max-part-mib must be positive")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", prefix) or ".." in prefix:
        raise SnapshotError("prefix must be a simple basename slug")
    if output.exists(): raise SnapshotError(f"output already exists: {output}")
    selected=_selected(root)
    for p in selected:
        if output == p or output in p.parents: raise SnapshotError("output is inside selected data")
    # Also reject output within any configured tree, including currently absent/empty trees.
    for rel in (*EXACT_DIRS, "copisteria/models"):
        data=root/rel
        if output == data or data in output.parents: raise SnapshotError(f"output is inside archived tree: {data}")
    limit=max_part_mib*1024*1024
    groups=[]; group=[]; total=0
    for p in selected:
        n=p.stat().st_size
        if group and total+n > limit: groups.append(group); group=[]; total=0
        group.append((p,n)); total+=n
    if group: groups.append(group)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    assets=[]
    try:
        for i, group in enumerate(groups, 1):
            name=f"{prefix}.part-{i:04d}.tar.gz"; dest=output/name
            members=[]
            with dest.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=3, mtime=0) as gz, tarfile.open(fileobj=gz, mode="w|", format=tarfile.PAX_FORMAT) as tf:
                for p, expected_size in group:
                    rel=p.relative_to(root).as_posix(); before=p.stat()
                    info=tarfile.TarInfo(rel); info.size=expected_size; info.mode=before.st_mode & 0o777; info.mtime=0
                    with p.open("rb") as src:
                        reader=_HashingReader(src); tf.addfile(info, reader)
                    after=p.stat()
                    if reader.count != expected_size or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
                        raise SnapshotError(f"file changed while packing: {rel}")
                    members.append({"path":rel,"bytes":reader.count,"sha256":reader.hash.hexdigest()})
            assets.append({"path":name,"bytes":dest.stat().st_size,"sha256":_file_sha(dest),"members":members})
            print(f"Packed {name}: {len(members)} files", file=sys.stderr)
        manifest={"format":"workspace-snapshot-v1","root":str(root),"assets":assets,
                  "counts":{"assets":len(assets),"files":sum(len(a["members"]) for a in assets),
                            "bytes":sum(m["bytes"] for a in assets for m in a["members"])}}
        mp=output/"MANIFEST.json"
        mp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        return mp
    except Exception:
        shutil.rmtree(output,ignore_errors=True)
        raise


def _file_sha(p: Path) -> str:
    with p.open("rb") as f: return _sha_stream(f)[0]


def _load_manifest(manifest_path: Path) -> tuple[dict, Path]:
    try: doc=json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e: raise SnapshotError(f"cannot read manifest: {e}")
    if doc.get("format") != "workspace-snapshot-v1" or not isinstance(doc.get("assets"),list): raise SnapshotError("unsupported manifest format")
    base=manifest_path.resolve().parent
    seen=set(); members_seen=set()
    for a in doc["assets"]:
        name=_safe_rel(a.get("path",""))
        if "/" in name or name in seen: raise SnapshotError(f"invalid or duplicate asset path: {name}")
        seen.add(name)
        for member in a.get("members",[]):
            rel=_safe_rel(member.get("path", ""))
            if rel in members_seen: raise SnapshotError(f"duplicate member across assets: {rel}")
            members_seen.add(rel)
    return doc,base


def _verified_assets(doc: dict, base: Path):
    for asset in doc["assets"]:
        ap=base/asset["path"]
        if ap.is_symlink() or not ap.is_file(): raise SnapshotError(f"missing or unsafe archive asset: {asset['path']}")
        if ap.stat().st_size != asset.get("bytes") or _file_sha(ap) != asset.get("sha256"):
            raise SnapshotError(f"archive checksum mismatch: {asset['path']}")
        expected={}
        for m in asset.get("members",[]):
            rel=_safe_rel(m.get("path",""))
            if rel in expected: raise SnapshotError(f"duplicate member path: {rel}")
            expected[rel]=m
        found=set()
        try:
            with tarfile.open(ap,"r:gz") as tf:
                for ti in tf:
                    rel=_safe_rel(ti.name)
                    if not ti.isfile() or ti.issym() or ti.islnk() or ti.isdev(): raise SnapshotError(f"non-regular archive member: {ti.name}")
                    if rel not in expected or rel in found: raise SnapshotError(f"unexpected/duplicate archive member: {rel}")
                    m=expected[rel]
                    f=tf.extractfile(ti)
                    if f is None: raise SnapshotError(f"unreadable archive member: {rel}")
                    digest,size=_sha_stream(f)
                    if size != m.get("bytes") or digest != m.get("sha256"): raise SnapshotError(f"member checksum mismatch: {rel}")
                    found.add(rel)
        except (tarfile.TarError,OSError) as e: raise SnapshotError(f"invalid archive {asset['path']}: {e}")
        if found != set(expected): raise SnapshotError(f"manifest members missing from archive: {asset['path']}")


def verify(manifest_path: Path) -> dict:
    doc,base=_load_manifest(manifest_path); _verified_assets(doc,base); return doc


def restore(manifest_path: Path, destination: Path, dry_run: bool=False) -> list[str]:
    doc,base=_load_manifest(manifest_path); _verified_assets(doc,base)
    dest=destination.expanduser().resolve()
    if dest.exists() and not dest.is_dir(): raise SnapshotError(f"destination is not a directory: {dest}")
    entries=[]
    for a in doc["assets"]:
        for member in a["members"]:
            rel=_safe_rel(member["path"]); target=dest.joinpath(*PurePosixPath(rel).parts)
            cur=dest
            for part in PurePosixPath(rel).parts[:-1]:
                cur=cur/part
                if cur.is_symlink(): raise SnapshotError(f"symlink in destination path: {cur}")
                if cur.exists() and not cur.is_dir(): raise SnapshotError(f"destination ancestor is not a directory: {cur}")
            if target.is_symlink(): raise SnapshotError(f"destination is a symlink: {target}")
            status="write"
            if target.exists():
                if not target.is_file(): raise SnapshotError(f"destination conflict: {target}")
                with target.open("rb") as f: digest,size=_sha_stream(f)
                if size != member["bytes"] or digest != member["sha256"]: raise SnapshotError(f"destination conflict: {target}")
                status="skip-identical"
            entries.append((a["path"],rel,status,member))
    if dry_run: return [f"{s}: {p}" for _,p,s,_ in entries]
    results=[]
    by_asset={a["path"]:{rel:(status,member) for name,rel,status,member in entries if name==a["path"]} for a in doc["assets"]}
    # One sequential archive pass per asset; every extracted member is hashed again before commit.
    for asset in doc["assets"]:
        statuses=by_asset[asset["path"]]
        with tarfile.open(base/asset["path"],"r|gz") as tf:
            for ti in tf:
                rel=_safe_rel(ti.name); status,member=statuses[rel]
                if status == "skip-identical":
                    results.append(f"skip-identical: {rel}"); continue
                target=dest.joinpath(*PurePosixPath(rel).parts)
                cur=dest
                for part in PurePosixPath(rel).parts[:-1]:
                    cur=cur/part
                    if cur.is_symlink(): raise SnapshotError(f"symlink in destination path: {cur}")
                target.parent.mkdir(parents=True,exist_ok=True)
                src=tf.extractfile(ti)
                if src is None: raise SnapshotError(f"unreadable archive member: {rel}")
                fd,tmp=tempfile.mkstemp(prefix=".snapshot-",dir=target.parent)
                h=hashlib.sha256(); count=0
                try:
                    with os.fdopen(fd,"wb") as out:
                        while True:
                            block=src.read(CHUNK)
                            if not block: break
                            out.write(block); h.update(block); count+=len(block)
                    if count!=member["bytes"] or h.hexdigest()!=member["sha256"]:
                        raise SnapshotError(f"member checksum mismatch during restore: {rel}")
                    # Recheck immediately before an atomic no-replace link commit.
                    if target.is_symlink(): raise SnapshotError(f"destination became a symlink: {target}")
                    cur=dest
                    for part in PurePosixPath(rel).parts[:-1]:
                        cur=cur/part
                        if cur.is_symlink() or (cur.exists() and not cur.is_dir()):
                            raise SnapshotError(f"destination path changed during restore: {cur}")
                    if target.exists():
                        if not target.is_file(): raise SnapshotError(f"destination conflict: {target}")
                        with target.open("rb") as existing: digest,size=_sha_stream(existing)
                        if size!=member["bytes"] or digest!=member["sha256"]: raise SnapshotError(f"destination conflict: {target}")
                        results.append(f"skip-identical: {rel}")
                    else:
                        try: os.link(tmp,target)
                        except FileExistsError:
                            with target.open("rb") as existing: digest,size=_sha_stream(existing)
                            if size!=member["bytes"] or digest!=member["sha256"]: raise SnapshotError(f"destination conflict: {target}")
                            results.append(f"skip-identical: {rel}")
                        else: results.append(f"write: {rel}")
                finally:
                    if os.path.exists(tmp): os.unlink(tmp)
    return results


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("pack"); p.add_argument("--output",type=Path,required=True); p.add_argument("--prefix",default="workspace-2026-11-26"); p.add_argument("--max-part-mib",type=int,default=900); p.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    v=sub.add_parser("verify"); v.add_argument("manifest",type=Path)
    r=sub.add_parser("restore"); r.add_argument("manifest",type=Path); r.add_argument("--destination",type=Path,default=Path.cwd()); r.add_argument("--dry-run",action="store_true")
    args=parser.parse_args(argv)
    try:
        if args.command=="pack": print(pack(args.output,args.root,args.prefix,args.max_part_mib))
        elif args.command=="verify":
            doc=verify(args.manifest); print(f"Verified {doc['counts']['assets']} assets, {doc['counts']['files']} files")
        else:
            lines=restore(args.manifest,args.destination,args.dry_run); print("\n".join(lines) if lines else "Nothing to restore")
        return 0
    except (SnapshotError,OSError) as e:
        print(f"error: {e}",file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
