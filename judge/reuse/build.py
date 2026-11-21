"""Derive matching theorem signatures from the checksum-audited RH export."""
import argparse
from array import array
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

AXIOMS = {("propext",), ("Classical", "choice"), ("Quot", "sound")}
HERE = Path(__file__).resolve().parent


def selected_names(metadata, ids):
    """Resolve exact Lean name components only for selected library donors and axioms."""
    parents = array("I", [0])
    with metadata.open("rb") as source:
        for line in source:
            if line.startswith(b'{"in":'):
                row = json.loads(line)
                parents.append((row.get("str") or row["num"])["pre"])
    needed = set(ids)
    for name in ids:
        head = parents[name]
        while head and head not in needed:
            needed.add(head)
            head = parents[head]
    names = {0: ()}
    with metadata.open("rb") as source:
        for line in source:
            if line.startswith(b'{"in":') and int(line[6:line.index(b",")]) in needed:
                row = json.loads(line)
                part = row.get("str") or row["num"]
                names[row["in"]] = names[part["pre"]] + (part.get("str", part.get("i")),)
    return names


def build(work, output):
    owners = array("I")
    with (work / "owner.bin").open("rb") as stream:
        owners.fromfile(stream, (work / "owner.bin").stat().st_size // owners.itemsize)
    metadata = work / "declarations.ndjson"
    signatures = defaultdict(list)
    axioms = set()
    with metadata.open("rb") as source:
        for line in source:
            if line.startswith(b'{"thm":'):
                thm = json.loads(line)["thm"]
                signatures[thm["type"], tuple(thm["levelParams"])].append(thm["name"])
            elif line.startswith(b'{"axiom":'):
                axioms.add(json.loads(line)["axiom"]["name"])
    classes = sorted((key, members) for key, members in signatures.items()
                     if len(members) > 1 and any(owners[n] for n in members))
    del signatures
    libraries = {n for _, members in classes for n in members if owners[n] == 0}
    names = selected_names(metadata, libraries | axioms)
    if {names[n] for n in axioms} != AXIOMS:
        raise ValueError("The export declares a different axiom set")
    roots = sorted({key[0] for key, _ in classes})
    with (work / "reuse-types.txt").open("w") as roots_file:
        for root in roots:
            print(root, file=roots_file)
    with (work / "reuse-types.txt").open("rb") as inp, (work / "reuse-footprints.txt").open("wb") as out:
        subprocess.run([work / "measure", work, "--theorem-statements"], stdin=inp, stdout=out, check=True)
    digest = hashlib.sha256()
    total = 0
    baseline = json.loads((HERE.parent / "baseline.json").read_text())
    with output.open("wb") as raw, gzip.GzipFile(fileobj=raw, filename="", mode="wb", mtime=0) as packed:
        def emit(row):
            nonlocal total
            line = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            digest.update(line)
            total += len(line)
            packed.write(line)
        emit({"format": 1, "export": baseline["compressed_sha256"], "axioms": sorted(".".join(p) for p in AXIOMS)})
        with (work / "reuse-footprints.txt").open() as footprints:
            previous = None
            for (root, universes), members in classes:
                if root != previous:
                    measured, nodes, *deps = map(int, next(footprints).split())
                    if measured != root:
                        raise ValueError("Statement footprints out of order")
                    previous = root
                archive = [owners[n] for n in members if owners[n]]
                library = [names[n] for n in members if not owners[n]]
                emit([root, universes, nodes, deps, archive, library])
            if next(footprints, None) is not None:
                raise ValueError("Unexpected trailing statement")
    return {"bytes": total, "sha256": digest.hexdigest(), "export_sha256": baseline["compressed_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="Output of judge/baseline/reproduce.sh")
    parser.add_argument("output", type=Path)
    parser.add_argument("--write-pin", action="store_true")
    args = parser.parse_args()
    pin = build(args.work.resolve(), args.output)
    lock = HERE / "index.lock.json"
    if args.write_pin:
        lock.write_text(json.dumps(pin, indent=2) + "\n")
    elif json.loads(lock.read_text()) != pin:
        raise SystemExit("The rebuilt theorem reuse index differs from the audited pin")
    print(json.dumps(pin))
