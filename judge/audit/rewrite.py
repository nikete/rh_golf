"""Materialize verified exact theorem aliases as a complete Lean 3.1.0 NDJSON export."""
import argparse
from array import array
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from archive_graph import ArchiveGraph
from fetch_graph import read_pin
from reuse import verify_reuse
from reuse.portfolio import canonical, verify_portfolio


@contextmanager
def export_stream(path):
    if path.suffix == ".zst":
        with subprocess.Popen(["zstd", "-qdc", "--long=30", "--", str(path)], stdout=subprocess.PIPE) as process:
            try:
                yield process.stdout
            finally:
                process.stdout.close()
            if process.wait():
                raise ValueError("Export decompression failed")
    else:
        with path.open("rb") as source:
            yield source


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(4 << 20):
            digest.update(block)
    return digest.hexdigest()


def verify_inputs(graph, pairs):
    # Accept name-component arrays throughout; joining with dots loses numeric
    # components and literal periods. The audited table binds type and universes.
    aliases = [(canonical(graph.name_parts(t)), canonical(graph.name_parts(d))) for t, d in pairs]
    result = verify_portfolio(((json.loads(t), json.loads(d)) for t, d in aliases), graph)
    return dict(aliases), result


def split_original(path, destination, work, baseline):
    if path.suffix == ".zst" and hash_file(path) != baseline["compressed_sha256"]:
        raise ValueError("Compressed archive SHA-256 mismatch")
    splitter = work / "split"
    subprocess.run(["c++", "-O2", "-std=c++17", str(HERE / "rewrite_split.cpp"), "-o", str(splitter)], check=True)
    digest = hashlib.sha256()
    with export_stream(path) as source, destination.open("wb") as output:
        with subprocess.Popen([splitter, work], stdin=subprocess.PIPE, stdout=output) as process:
            try:
                while block := source.read(4 << 20):
                    digest.update(block)
                    process.stdin.write(block)
            finally:
                process.stdin.close()
            if process.wait():
                raise ValueError("Could not partition export primitives and declarations")
    if digest.hexdigest() != baseline["unpacked_sha256"]:
        raise ValueError("Unpacked archive SHA-256 mismatch")


def match_names(graph, aliases):
    # Follow only paths to archive declaration names and selected Mathlib donors.
    children, terminal = {}, {}
    def enter(key):
        node = 0
        for part in json.loads(key):
            edge = (node, part)
            if edge not in children:
                children[edge] = len(children) + 1
            node = children[edge]
        terminal[node] = key
    for key in graph.names:
        enter(key)
    for key in set(aliases.values()) - graph.names.keys():
        enter(key)
    return children, terminal


def declaration_order(graph, patches):
    """Sort all declarations, including components no longer needed by RH."""
    state = bytearray(graph.count)
    for group in range(1, graph.count):
        if state[group]:
            continue
        stack = [group]
        while stack:
            current = stack.pop()
            if current < 0:
                state[-current] = 2
                yield -current
                continue
            if state[current] == 2:
                continue
            if state[current] == 1:
                raise ValueError("Cyclic full-export declaration dependency")
            state[current] = 1
            stack.append(-current)
            deps = patches[current].dependencies if current in patches else graph._original(current)
            stack.extend(d for d in deps if state[d] != 2)


def locate(metadata, graph, aliases):
    children, terminal = match_names(graph, aliases)
    nodes = array("I", [0])
    unknown = 2**32 - 1
    needed = aliases.keys() | set(aliases.values())
    levels, selected = {}, {}
    library_offsets = array("Q")
    offsets = array("Q", [0])
    pos = 0
    for line in metadata:
        row = json.loads(line)
        if "in" in row:
            part = row.get("str") or row["num"]
            if row["in"] != len(nodes):
                raise ValueError("Nonconsecutive original name table")
            token = part.get("str", part.get("i"))
            parent = nodes[part["pre"]]
            nodes.append(children.get((parent, token), unknown) if parent != unknown else unknown)
        elif "il" in row:
            if "param" in row:
                levels[row["param"]] = row["il"]
        elif "meta" in row:
            if pos != 0 or row["meta"]["format"]["version"] != "3.1.0":
                raise ValueError("Unexpected Lean export format")
        else:
            kind, value = next(iter(row.items()))
            items = value["types"] + value["ctors"] + value["recs"] if kind == "inductive" else [value]
            groups = set()
            for item in items:
                key = terminal.get(nodes[item["name"]])
                groups.add(graph.names.get(key, 0))
                if key in needed:
                    if kind != "thm" or key in selected:
                        raise ValueError("Selected name is not a unique theorem in the original export")
                    selected[key] = (item["name"], item["type"], item["levelParams"])
            if groups == {0}:
                library_offsets.append(pos)
            elif groups == {len(offsets)}:
                offsets.append(pos)
            else:
                raise ValueError("Original declaration order or grouping disagrees with pinned graph")
        pos += len(line)
    if len(offsets) != graph.count or selected.keys() != needed:
        raise ValueError("Missing original archive group or selected theorem")
    return offsets, library_offsets, levels, selected


def write_declarations(work, output, graph, patches, aliases):
    expr_count, level_count = map(int, (work / "counts").read_text().split())
    with (work / "metadata").open("rb") as metadata:
        offsets, libraries, levels, selected = locate(metadata, graph, aliases)
        wanted = {}
        target_bodies = {}
        for target, donor in aliases.items():
            _, typ, params = selected[target]
            name, donor_type, donor_params = selected[donor]
            if (typ, params) != (donor_type, donor_params):
                raise ValueError("Actual target and donor signatures differ in the original export")
            for param in params:
                if param not in levels:
                    levels[param] = level_count
                    output.write(canonical({"il": level_count, "param": param}) + b"\n")
                    level_count += 1
            body = (name, tuple(levels[param] for param in params))
            wanted[body] = None
            target_bodies[graph.names[target]] = body
        with (work / "constants").open("rb") as consts:
            for line in consts:
                record = json.loads(line)
                term = record["const"]
                key = (term["name"], tuple(term["us"]))
                if key in wanted:
                    wanted[key] = record["ie"]
        for (name, us), expr in wanted.items():
            if expr is None:
                output.write(canonical({"const": {"name": name, "us": us}, "ie": expr_count}) + b"\n")
                wanted[name, us] = expr_count
                expr_count += 1
        # Mathlib has no archive dependencies. Preserve its original order.
        # Whole mutual inductives, their constructors/recursors, and quotient
        # records are copied verbatim. All five challenge statements survive.
        for pos in libraries:
            metadata.seek(pos)
            output.write(metadata.readline())
        for group in declaration_order(graph, patches):
            metadata.seek(offsets[group])
            original = metadata.readline()
            if group in target_bodies:
                row = json.loads(original)
                row["thm"]["value"] = wanted[target_bodies[group]]
                output.write(canonical(row) + b"\n")
            else:
                output.write(original)


def materialize(source, destination, graph, aliases, result, baseline):
    if source.resolve() == destination.resolve() or destination.exists():
        raise ValueError("Choose a new output file distinct from the original")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".rewrite-") as folder:
        work = Path(folder)
        staged = work / "candidate.ndjson"
        split_original(source, staged, work, baseline)
        with staged.open("ab") as output:
            write_declarations(work, output, graph, result["replacements"], aliases)
        digest = hash_file(staged)
        os.replace(staged, destination)
    return {"candidate_sha256": digest, "original_sha256": baseline["unpacked_sha256"],
            "certificate_sha256": result["certificate_sha256"], "expected_nodes": result["standalone_rh_nodes"],
            "coverage": result["coverage"], "output_bytes": destination.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Checksum-pinned MIT .ndjson or .ndjson.zst")
    parser.add_argument("--output", type=Path, help="New uncompressed candidate .ndjson")
    parser.add_argument("--graph", type=Path, default=HERE.parents[1] / ".out/archive-graph")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", type=Path, help="Gzipped JSONL of [target, donor] pairs")
    group.add_argument("--target")
    parser.add_argument("--donor")
    parser.add_argument("--plan-only", action="store_true", help="Check the substitution order without writing an export")
    args = parser.parse_args()
    if bool(args.target) != bool(args.donor):
        parser.error("--target and --donor must be specified together")
    if not args.plan_only and (args.input is None or args.output is None):
        parser.error("--input and --output are required to write a complete export")
    for filename, spec in read_pin()["files"].items():
        file = args.graph / filename
        if file.stat().st_size != spec["bytes"] or hash_file(file) != spec["sha256"]:
            raise ValueError(f"Dependency graph does not match the baseline pin: {filename}")
    graph = ArchiveGraph(args.graph)
    if args.manifest:
        with gzip.open(args.manifest, "rb") as source:
            aliases, result = verify_inputs(graph, map(json.loads, source))
    else:
        aliases, result = verify_inputs(graph, [(args.target, args.donor)])
        result["certificate_sha256"] = verify_reuse(args.target, args.donor, graph, "")["certificate_sha256"]
    if args.plan_only:
        size = sum(1 for _ in declaration_order(graph, result["replacements"]))
        if size != graph.count - 1:
            raise ValueError("Incomplete archive declaration ordering")
        print(json.dumps({"mode": "plan-only", "archive_groups": size, "coverage": result["coverage"],
                          "expected_nodes": result["standalone_rh_nodes"], "certificate_sha256": result["certificate_sha256"]}))
        return
    baseline = json.loads((HERE.parent / "baseline.json").read_text())
    receipt = materialize(args.input, args.output, graph, aliases, result, baseline)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
