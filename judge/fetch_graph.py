"""Fetch or stage the audited per-declaration RH graph on a GitHub runner."""
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ASSET = "archive-graph.tar.gz"
UPSTREAM = "nikete/rh_golf"
MEMBERS = {"manifest.json", "groups.bin", "dependencies.bin", "names.tsv"}


def read_pin():
    pin = json.loads((HERE / "archive_graph.lock.json").read_text())
    baseline = json.loads((HERE / "baseline.json").read_text())
    if pin["export_sha256"] != baseline["compressed_sha256"] or set(pin["files"]) != MEMBERS:
        raise ValueError("Graph pin differs from the archive or expected file set")
    return pin


def release_tag(pin):
    payload = json.dumps(pin, sort_keys=True, separators=(",", ":")).encode()
    return "rh-graph-" + hashlib.sha256(payload).hexdigest()[:20]


def matches(path, spec):
    if not path.is_file() or path.stat().st_size != spec["bytes"]:
        return False
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest() == spec["sha256"]


def unpack(bundle, stage, files):
    seen = set()
    with tarfile.open(bundle, mode="r|gz") as archive:
        for member in archive:
            name = member.name
            if (name not in files or name in seen or not member.isfile()
                    or member.size != files[name]["bytes"]):
                raise ValueError(f"Unexpected graph asset member {name!r}")
            seen.add(name)
            target = stage / name
            with archive.extractfile(member) as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            if not matches(target, files[name]):
                raise ValueError(f"RH graph checksum mismatch for {name}")
    if seen != set(files):
        raise ValueError("Incomplete graph asset")


def download(bundle, tag, repository):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid release repository")
    for source in dict.fromkeys((repository, UPSTREAM)):
        url = f"https://github.com/{source}/releases/download/{tag}/{ASSET}"
        result = subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                                 "--retry", "3", "--connect-timeout", "20", "--max-time", "300",
                                 "--output", str(bundle), url])
        if result.returncode == 0:
            return
    raise RuntimeError(f"Could not fetch the audited graph release {tag}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=HERE.parent / ".out/archive-graph")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", UPSTREAM),
                        help="Try this public release repository before the canonical upstream")
    parser.add_argument("--bundle", type=Path, help="Install a locally reproduced graph archive")
    parser.add_argument("--verify", type=Path, help="Verify a bundle without installing it")
    parser.add_argument("--tag", action="store_true", help="Print the immutable release tag")
    args = parser.parse_args()
    pin = read_pin()
    tag = release_tag(pin)
    if args.tag:
        print(tag)
        return
    if args.verify:
        with tempfile.TemporaryDirectory() as tmp:
            unpack(args.verify, Path(tmp), pin["files"])
        return
    dest = args.directory
    dest.parent.mkdir(parents=True, exist_ok=True)
    with (dest.parent / (dest.name + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if all(matches(dest / name, spec) for name, spec in pin["files"].items()):
            return
        with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
            stage = Path(tmp)
            bundle = args.bundle
            if bundle is None:
                bundle = stage / ASSET
                download(bundle, tag, args.repository)
            unpack(bundle, stage, pin["files"])
            dest.mkdir(exist_ok=True)
            for name in pin["files"]:
                os.replace(stage / name, dest / name)


if __name__ == "__main__":
    main()
