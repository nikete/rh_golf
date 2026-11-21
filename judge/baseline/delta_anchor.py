"""Recheck the alias index and prove the excluded library boundary on the original export."""
import argparse
from array import array
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

JUDGE = Path(__file__).resolve().parents[1]
UNKNOWN = 0xFFFFFFFF


def copy_verified(source, dest, expected):
    digest = hashlib.sha256()
    while chunk := source.read(2 << 20):
        digest.update(chunk)
        dest.write(chunk)
    if digest.hexdigest() != expected:
        raise ValueError("Wrong SHA-256 for the decompressed baseline export")


def signature_members(path):
    """Build two independent lookups from the proposed index for the raw declaration scan."""
    archive = {}
    library = {}
    children = {}
    statements = {}
    pin = json.loads((JUDGE / "reuse/index.lock.json").read_bytes())
    baseline = json.loads((JUDGE / "baseline.json").read_bytes())
    with gzip.open(path, "rb") as f:
        contents = f.read(pin["bytes"] + 1)
    if (len(contents) != pin["bytes"] or hashlib.sha256(contents).hexdigest() != pin["sha256"]
            or pin["export_sha256"] != baseline["compressed_sha256"]):
        raise ValueError("The theorem signatures differ from the baseline pin")
    lines = iter(contents.splitlines())
    if json.loads(next(lines)) != {"format": 1, "export": pin["export_sha256"],
                                   "axioms": ["Classical.choice", "Quot.sound", "propext"]}:
        raise ValueError("Invalid theorem signature header")
    for line in lines:
        root, levels, nodes, deps, groups, names = json.loads(line)
        sig = root, tuple(levels)
        footprint = nodes, tuple(deps)
        if statements.setdefault(root, footprint) != footprint:
            raise ValueError("Inconsistent statement footprint")
        for group in groups:
            if group in archive:
                raise ValueError("Repeated archive member")
            archive[group] = sig
        for name in names:
            key = 0
            for part in name:
                key = children.setdefault((key, part), len(children) + 1)
            if key in library:
                raise ValueError("Repeated library member")
            library[key] = sig
    return archive, library, children, statements


def scan(work, signatures, measurement=None):
    arch, lib, children, statements = signature_members(signatures)
    summary = {"archive_theorems": len(arch), "library_theorems": len(lib),
               "distinct_statement_roots": len(statements), "library_decl_groups": 0}
    owner = array("I")
    with (work / "owner.bin").open("rb") as f:
        owner.fromfile(f, (work / "owner.bin").stat().st_size // 4)
    prefixes = array("I", [0])
    roots = set()
    with (work / "declarations.ndjson").open("rb") as f:
        for line in f:
            row = json.loads(line)
            if "in" in row:
                part = row.get("str") or row["num"]
                if row["in"] != len(prefixes):
                    raise ValueError("Nonconsecutive name ID")
                prefixes.append(children.get((prefixes[part["pre"]], part.get("str", part.get("i"))), UNKNOWN))
                continue
            kind, payload = next(iter(row.items()))
            if kind == "meta":
                continue
            items = (payload["types"] + payload["ctors"] + payload["recs"]
                     if kind == "inductive" else [payload])
            groups = {owner[r["name"]] for r in items}
            if len(groups) != 1 or UNKNOWN in groups:
                raise ValueError("Unresolved or mixed declaration group")
            group = next(iter(groups))
            if group == 0:
                summary["library_decl_groups"] += 1
            for r in items:
                witness = arch.pop(group, None) if group else lib.pop(prefixes[r["name"]], None)
                if witness is not None and (kind != "thm" or witness != (r["type"], tuple(r["levelParams"]))):
                    raise ValueError("Indexed declaration has incorrect kind, type, or ordered universe parameters")
                if group:
                    continue
                roots.add(r["type"])
                if "value" in r:
                    roots.add(r["value"])
                roots.update(rule["rhs"] for rule in r.get("rules", ()))
                refs = [*r.get("all", ()), *r.get("ctors", ()), *(rule["ctor"] for rule in r.get("rules", ()))]
                if "induct" in r:
                    refs.append(r["induct"])
                if any(owner[name] != 0 for name in refs):
                    raise ValueError("A library declaration metadata field references the archive")
    if arch or lib or len(prefixes) != len(owner):
        raise ValueError("Not all indexed theorem names and signatures occur in original declarations")
    if not roots or not summary["library_decl_groups"]:
        raise ValueError("The original library boundary is empty")
    # Group zero is an ownerless scratch group, so every nonlibrary reference,
    # including a projection's type name, is present in the reported dependency list.
    # Files avoid buffering the input and output of the measuring child in memory.
    with tempfile.TemporaryFile(mode="w+t") as requests, tempfile.TemporaryFile(mode="w+t") as answers:
        ordered = sorted(roots | statements.keys())
        for root in ordered:
            print(root, file=requests)
        requests.seek(0)
        subprocess.run([measurement or work / "measure", work, "--theorem-statements"], check=True,
                       stdin=requests, stdout=answers)
        answers.seek(0)
        for root in ordered:
            expr, weight, *deps = map(int, next(answers).split())
            if expr != root or (root in roots and deps):
                raise ValueError(f"Excluded library root {root} has archive dependencies or an incorrect index")
            if root in statements and statements[root] != (weight, tuple(deps)):
                raise ValueError(f"Wrong footprint or type dependency set for original theorem statement {root}")
        if next(answers, None) is not None:
            raise ValueError("Unexpected additional expression footprint")
    return {**summary, "library_expression_roots": len(roots), "library_to_archive_edges": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-raw", action="store_true", help="Hash and forward the decompressed baseline export")
    parser.add_argument("work", nargs="?", type=Path)
    parser.add_argument("signatures", nargs="?", type=Path)
    args = parser.parse_args()
    if args.verify_raw:
        copy_verified(sys.stdin.buffer, sys.stdout.buffer, json.loads((JUDGE / "baseline.json").read_bytes())["unpacked_sha256"])
        return
    if not args.work or not args.signatures:
        parser.error("supply the baseline workspace and the compressed signature file")
    receipt = scan(args.work.resolve(), args.signatures)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
