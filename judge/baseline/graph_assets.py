"""Write the exact Lean-name index and deterministically package the audited graph."""
from array import array
import gzip
import json
from pathlib import Path
import sys
import tarfile

UNKNOWN = 0xFFFFFFFF


def name_index(work, output):
    owners = array("I")
    with (work / "owner.bin").open("rb") as stream:
        owners.fromfile(stream, (work / "owner.bin").stat().st_size // owners.itemsize)
    parents = array("I", [0])
    kinds = {}
    # Build the ancestry of *declaration* names. Most of the 14 million
    # registered names in the export are binders and need no string storage.
    with (work / "declarations.ndjson").open("rb") as stream:
        for line in stream:
            row = json.loads(line)
            if "in" in row:
                part = row.get("str") or row["num"]
                parents.append(part["pre"])
                continue
            kind, payload = next(iter(row.items()))
            if kind == "meta":
                continue
            names = payload["types"] if kind == "inductive" else [payload]
            for record in names:
                owner = owners[record["name"]]
                if 0 < owner < UNKNOWN:
                    kinds[owner] = kind
    if len(owners) != len(parents):
        raise ValueError("Name table size mismatch")
    prefix = bytearray(len(owners))
    for i in range(len(owners) - 1, 0, -1):
        if prefix[i] or 0 < owners[i] < UNKNOWN:
            prefix[parents[i]] = 1
    # A canonical JSON array distinguishes string and numeric name components,
    # including components containing a literal dot or newline.
    prefixes = {0: b"["}
    with (work / "declarations.ndjson").open("rb") as stream, output.open("wb") as names:
        for line in stream:
            if not line.startswith(b'{"in":'):
                continue
            row = json.loads(line)
            i = row["in"]
            group = owners[i]
            if not prefix[i] and group in (0, UNKNOWN):
                continue
            part = row.get("str") or row["num"]
            component = part.get("str", part.get("i"))
            token = json.dumps(component, ensure_ascii=False, separators=(",", ":")).encode()
            name = prefixes[parents[i]] + token
            if prefix[i]:
                prefixes[i] = name + b","
            if group not in (0, UNKNOWN):
                names.write(f"{group}\t{kinds[group]}\t".encode() + name + b"]\n")


def pack_graph(work, baseline_file):
    output = work / "archive-graph"
    baseline = json.loads(Path(baseline_file).read_text())
    targets = json.loads((work / "targets.json").read_text())
    manifest = dict(version=1, root=targets[baseline["root"]], baseline=baseline["archive_nodes"],
                    metric=baseline["metric"], export_sha256=baseline["compressed_sha256"])
    (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    with (work / "archive-graph.tar.gz").open("wb") as sink:
        with gzip.GzipFile(fileobj=sink, filename="", mode="wb", mtime=0, compresslevel=6) as gz:
            with tarfile.open(fileobj=gz, mode="w|", format=tarfile.USTAR_FORMAT) as tar:
                for name in ("dependencies.bin", "groups.bin", "manifest.json", "names.tsv"):
                    path = output / name
                    info = tarfile.TarInfo(path.name)
                    info.size = path.stat().st_size
                    with path.open("rb") as contents:
                        tar.addfile(info, contents)


if __name__ == "__main__":
    work = Path(sys.argv[1])
    name_index(work, work / "archive-graph" / "names.tsv")
    pack_graph(work, sys.argv[2])
