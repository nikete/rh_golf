"""Derive the ordinary-RH reference from MIT's independently published Mathlib-only challenge."""
import argparse
import hashlib
import json
from pathlib import Path

THEOREMS = {"riemannHypothesis", "riemannZeta_eq_zero_re", "LFunction_ne_zero_of_half_lt_re",
            "LFunction_eq_zero_re", "LFunction_eq_zero_re_of_isPrimitive"}


def project(source, destination):
    # Keep all Mathlib declarations, name/level/expression indices, and RH's
    # original type and placeholder intact. Omit only four unrelated obligations.
    found, declarations = {}, set()
    digest = hashlib.sha256()
    with source.open("rb") as src, destination.open("wb") as dst:
        for line in src:
            digest.update(line)
            if line.startswith(b'{"in":') and b'"pre":0,' in line:
                row = json.loads(line)
                name = row.get("str", {}).get("str")
                if name in THEOREMS:
                    found[row["in"]] = name
            elif line.startswith(b'{"thm":'):
                row = json.loads(line)["thm"]
                if row["name"] in found:
                    name = found[row["name"]]
                    if name in declarations or row["all"] != [row["name"]]:
                        raise ValueError("Unexpected declaration group in the audited challenge")
                    declarations.add(name)
                    if name != "riemannHypothesis":
                        continue
            dst.write(line)
    if digest.hexdigest() != "bd484ac9886a96f26b1d9a7a59ebd45b7a70d102c015d4f31f9302bbdd6ab2b9" or declarations != THEOREMS:
        raise ValueError("Unexpected upstream Mathlib reference")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    project(args.source, args.destination)
