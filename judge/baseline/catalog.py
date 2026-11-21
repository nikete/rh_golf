"""Resolve exported declaration names against the complete Mathlib environment at the pin."""
from array import array
import gzip
import json
from pathlib import Path
import sys

UNKNOWN = 0xFFFFFFFF
ROOTS = ("riemannHypothesis", "rhOfAll", "Formalism.VW.rh_of_every",
         "Formalism.VW.rh_of_right", "allChi")


def catalog(folder):
    # An exact trie preserves numeric and string name components and avoids storing
    # a fully qualified copy of every internal binder name in the giant export.
    children = {}
    is_library = bytearray([0])

    def insert(parts):
        parent = 0
        for component in parts:
            key = (parent, component)
            child = children.get(key)
            if child is None:
                child = len(is_library)
                children[key] = child
                is_library.append(0)
            parent = child
        return parent

    with gzip.open(folder / "mathlib-names.jsonl.gz", "rb") as names:
        for line in names:
            is_library[insert(json.loads(line))] = 1
    interest = {insert(n.split(".")): n for n in ROOTS}
    targets = {}
    mapped = array("I", [0])
    owner = array("I", [UNKNOWN])
    count = 0
    with (folder / "declarations.ndjson").open("rb") as stream, (folder / "groups.bin").open("wb") as groups:
        for line in stream:
            obj = json.loads(line)
            if "in" in obj:
                assert obj["in"] == len(mapped)
                if "str" in obj:
                    v = obj["str"]
                    component = v["str"]
                else:
                    v = obj["num"]
                    component = v["i"]
                part = children.get((mapped[v["pre"]], component), UNKNOWN)
                mapped.append(part)
                owner.append(0 if part != UNKNOWN and is_library[part] else UNKNOWN)
                continue
            kind, payload = next(iter(obj.items()))
            if kind == "meta":
                assert payload["format"]["version"] == "3.1.0"
                continue
            if kind == "inductive":
                rows = payload["types"] + payload["ctors"] + payload["recs"]
            elif kind in ("def", "opaque", "thm", "axiom", "quot"):
                rows = [payload]
            else:
                raise ValueError(f"Unknown declaration {kind}")
            names = [row["name"] for row in rows]
            if all(owner[n] == 0 for n in names):
                continue
            if any(owner[n] != UNKNOWN for n in names):
                raise ValueError("Mixed or duplicated non-library declaration group")
            count += 1
            # For ordinary declarations, the exporter's "all" is elaboration
            # bookkeeping. Only expression references are kernel dependencies.
            # Inductive blocks already contain all their types, constructors and recursors.
            expressions = []
            for name, row in zip(names, rows):
                owner[name] = count
                if mapped[name] in interest:
                    targets[interest[mapped[name]]] = count
                expressions.append(row["type"])
                if "value" in row:
                    expressions.append(row["value"])
                expressions.extend(rule["rhs"] for rule in row.get("rules", []))
            array("I", [len(expressions), *expressions]).tofile(groups)
    if set(targets) != set(ROOTS):
        raise ValueError(f"Missing named theorem: {targets}")
    with (folder / "owner.bin").open("wb") as f:
        owner.tofile(f)
    (folder / "targets.json").write_text(json.dumps(targets, indent=2) + "\n")
    print(f"{count:,} non-library declaration groups, {len(mapped):,} registered names", flush=True)


if __name__ == "__main__":
    catalog(Path(sys.argv[1]))
