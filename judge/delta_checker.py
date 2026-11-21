"""Independently check exact theorem substitutions relative to the pinned Lean export."""
import argparse
from array import array
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile

JUDGE = Path(__file__).resolve().parent
ROOT = "riemannHypothesis"
METRIC = "rh-declaration-nodes-v1"
AXIOMS = ["Classical.choice", "Quot.sound", "propext"]
METHOD = "rh-exact-theorem-delta-v1"
PORTFOLIO = "pinned-export-exact-reuse-portfolio-v1"
SINGLE = "pinned-export-exact-reuse-v1"
MEMBERS = {"groups.bin", "dependencies.bin", "names.tsv", "manifest.json"}
MAX_INPUT = 160 << 20
MAX_PACKED = 32 << 20
MAX_LINE = 64 << 10
MAX_PAIRS = 1_260_000


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(data, spec, name):
    if len(data) != spec["bytes"] or digest(data) != spec["sha256"]:
        raise ValueError(f"Checksum or byte count differs from the trusted pin for {name}")
    return data


def load_words(path, spec):
    raw = checked(path.read_bytes(), spec, path.name)
    if len(raw) % 4:
        raise ValueError("Truncated archive word table")
    if sys.byteorder == "little":
        return memoryview(raw).cast("I")
    values = array("I", raw)
    values.byteswap()
    return values


def name_key(name):
    if isinstance(name, str):
        if not name or len(name.encode()) > MAX_LINE:
            raise ValueError("Invalid Lean name length")
        parts = []
        i = 0
        while i < len(name):
            if name[i] == "«":
                end = name.find("»", i + 1)
                if end < 0:
                    raise ValueError("Unclosed quoted Lean name component")
                part = name[i + 1:end]
                i = end + 1
            else:
                end = name.find(".", i)
                i, part = (len(name), name[i:]) if end < 0 else (end, name[i:end])
                if not part:
                    raise ValueError("Empty Lean name component")
                if part.isascii() and part.isdecimal():
                    part = int(part)
            parts.append(part)
            if i == len(name):
                break
            if name[i] != "." or i + 1 == len(name):
                raise ValueError("Malformed Lean name separator")
            i += 1
    elif isinstance(name, (list, tuple)) and name and all(
            type(p) is str or type(p) is int and p >= 0 for p in name):
        parts = name
    else:
        raise ValueError("Expected a Lean name or a nonempty list of name components")
    return encode(parts)


def requested_names(pairs):
    requested = {}
    total = 0
    for index, pair in enumerate(pairs, 1):
        if index > MAX_PAIRS or not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("Invalid substitution pair or pair limit exceeded")
        target, donor = map(name_key, pair)
        size = len(target) + len(donor) + 4
        total += size
        if size > MAX_LINE or total > MAX_INPUT:
            raise ValueError("Substitution names exceed the input size limit")
        if target == donor or target in requested:
            raise ValueError(f"Self-reference or duplicate target on substitution {index}")
        requested[target] = donor
    if not requested:
        raise ValueError("No theorem substitutions")
    return requested


def resolve_groups(path, spec, requested, root):
    # Retain only names the submission refers to; hash the exact stream read.
    key_root = encode([ROOT])
    wanted = set(requested) | set(requested.values()) | {key_root}
    groups = {}
    sha = hashlib.sha256()
    with path.open("rb") as names:
        for line in names:
            sha.update(line)
            group, kind, key = line.rstrip(b"\n").split(b"\t", 2)
            if key in wanted:
                if kind != b"thm" or key in groups:
                    raise ValueError("Substitutions are restricted to uniquely named theorems")
                groups[key] = int(group)
        size = names.tell()
    if sha.hexdigest() != spec["sha256"] or size != spec["bytes"]:
        raise ValueError("Invalid archive name-table checksum")
    if groups.get(key_root) != root:
        raise ValueError("Archive root name and group disagree")
    by_id = {}
    for target, donor in requested.items():
        target_id = groups.get(target)
        if target_id is None or target_id in by_id:
            raise ValueError("Unknown or duplicated archive theorem target")
        # A byte key is an alleged library name; only the pinned signature
        # class can establish that it is an exported Mathlib theorem.
        by_id[target_id] = groups.get(donor, donor)
    return by_id


def read_patches(pending, signatures, pin, group_count, single_names):
    portfolio = hashlib.sha256(encode([PORTFOLIO, pin["export_sha256"], pin["sha256"]]) + b"\n")
    normalized = hashlib.sha256(encode([METHOD, pin["export_sha256"], pin["sha256"]]) + b"\n")
    single_result = {}
    patches = {}
    with gzip.open(signatures, "rb") as f:
        data = checked(f.read(pin["bytes"] + 1), pin, "expanded signature index")
    rows = io.BytesIO(data)
    if json.loads(rows.readline()) != {"format": 1, "export": pin["export_sha256"], "axioms": AXIOMS}:
        raise ValueError("The export or axiom inventory differs from the pinned baseline")
    for line in rows:
        statement, universes, size, type_dependencies, members, library = json.loads(line)
        targets = [g for g in members if g in pending]
        if not targets:
            continue
        if (type(statement) is not int or statement < 0 or type(size) is not int or size < 1
                or any(type(u) is not int or u <= 0 for u in universes) or len(set(universes)) != len(universes)
                or any(type(d) is not int or not 0 < d < min(targets) for d in type_dependencies)):
            raise ValueError("Invalid pinned theorem statement, universes or structural dependencies")
        eligible = set(members)
        libraries = {encode(name) for name in library}
        for g in targets:
            donor = pending.pop(g)
            if not 0 < g < group_count:
                raise ValueError("Unknown target group in signature table")
            if type(donor) is int:
                if not 0 < donor < group_count or donor == g or donor not in eligible:
                    raise ValueError("Donor is not a different archive theorem of the same instantiated signature")
                deps = tuple(sorted(set(type_dependencies) | {donor}))
                witness = donor
            elif donor in libraries:
                deps = tuple(sorted(set(type_dependencies)))
                witness = json.loads(donor)
            else:
                raise ValueError("Donor is not a library theorem of the same instantiated signature")
            # Each row certifies identical raw type and ordered level-parameter
            # IDs. Instantiating the donor at those parameters is the identity.
            # The one new constant is distinct from every node of its own type.
            patches[g] = (size + 1, deps)
            portfolio.update(encode([g, witness]) + b"\n")
            normalized.update(encode([g, statement, universes, ["const", witness, universes], size + 1, deps]) + b"\n")
            if single_names:
                target, source = single_names
                single_result = {"local_nodes": size + 1, "reuse_statement_id": statement,
                                 "reuse_universe_parameters": universes, "dependency_ids": deps}
                single_result["certificate_sha256"] = digest(encode({"verifier": SINGLE, "export": pin["export_sha256"],
                                              "index": pin["sha256"], "target": target, "donor": source,
                                              "statement": statement, "universe_parameters": universes}))
    if pending:
        raise ValueError("A target is not an eligible theorem with an exact signature match")
    return patches, portfolio.hexdigest(), normalized.hexdigest(), single_result


def measure(nodes, edges, patches, root, baseline):
    """Process a directed graph in dependency order; reject every residual cycle."""
    count = len(nodes) // 4
    if len(nodes) % 4 or not 0 < root < count:
        raise ValueError("Malformed original graph")
    inbound = array("I", [0]) * count
    old_live = bytearray(count)
    old_live[root] = 1
    old_cost = 0
    edge_end = len(edges)
    # The original archive uses ascending group IDs as a topological order.
    # Recompute its RH cost and the NEW incoming edge counts independently.
    for group in range(count - 1, 0, -1):
        offset = nodes[group * 4 + 1]
        if offset + nodes[group * 4 + 2] != edge_end:
            raise ValueError("Non-contiguous original dependency table")
        orig = edges[offset:edge_end]
        if nodes[group * 4] == 0 or any(d == 0 or d >= group for d in orig):
            raise ValueError("Invalid original group weight or dependency order")
        edge_end = offset
        if old_live[group]:
            old_cost += nodes[group * 4]
            for d in orig:
                old_live[d] = 1
        dependencies = patches[group][1] if group in patches else orig
        for d in dependencies:
            inbound[d] += 1
    if edge_end != 0 or old_cost != baseline:
        raise ValueError("Original root cost or dependency table does not match the pinned baseline")

    # Parents are processed before children. By the time a group is removed
    # from Kahn's queue, all paths from RH into it have been accounted for.
    live = bytearray(count)
    live[root] = 1
    queue = array("I", (g for g in range(1, count) if inbound[g] == 0))
    visited = reached = used = cost = changed_cost = 0
    while queue:
        group = queue.pop()
        visited += 1
        replacement = patches.get(group)
        if replacement is None:
            weight, offset, degree = nodes[group * 4:group * 4 + 3]
            dependencies = edges[offset:offset + degree]
        else:
            weight, dependencies = replacement
        if live[group]:
            reached += 1
            cost += weight
            if replacement is not None:
                used += 1
                changed_cost += weight
            for child in dependencies:
                live[child] = 1
        for child in dependencies:
            inbound[child] -= 1
            if inbound[child] == 0:
                queue.append(child)
    if visited != count - 1:
        raise ValueError("Cycle in the simultaneous theorem substitutions (including off-root components)")
    return cost, used, reached, changed_cost


def check_delta(graph_dir, pairs, *, single=False):
    """Verify exact aliases against locally pinned metadata, returning JSON-ready evidence."""
    folder = Path(graph_dir)
    baseline = json.loads((JUDGE / "baseline.json").read_bytes())
    graph_pin_bytes = (JUDGE / "archive_graph.lock.json").read_bytes()
    pin = json.loads(graph_pin_bytes)
    sig = json.loads((JUDGE / "reuse/index.lock.json").read_bytes())
    if (set(pin["files"]) != MEMBERS or pin["export_sha256"] != baseline["compressed_sha256"]
            or sig["export_sha256"] != pin["export_sha256"] or baseline["metric"] != METRIC or baseline["root"] != ROOT):
        raise ValueError("Incompatible pinned graph, signature index or baseline")
    files = pin["files"]
    meta = json.loads(checked((folder / "manifest.json").read_bytes(), files["manifest.json"], "graph manifest"))
    if (meta["version"] != 1 or meta["metric"] != METRIC or meta["export_sha256"] != pin["export_sha256"]
            or meta["baseline"] != baseline["archive_nodes"]):
        raise ValueError("Graph and baseline describe different proofs")
    nodes = load_words(folder / "groups.bin", files["groups.bin"])
    edges = load_words(folder / "dependencies.bin", files["dependencies.bin"])
    names = requested_names(pairs)
    if single and len(names) != 1:
        raise ValueError("Single-theorem mode requires one pair")
    single_names = tuple(json.loads(k) for k in next(iter(names.items()))) if single else None
    pending = resolve_groups(folder / "names.tsv", files["names.tsv"], names, meta["root"])
    del names
    patches, legacy, normalized, individual = read_patches(pending, JUDGE / "reuse/signatures.jsonl.gz", sig,
                                                         len(nodes) // 4, single_names)
    nodes_used, edits_used, reached, changed_cost = measure(nodes, edges, patches, meta["root"], meta["baseline"])
    if single:
        dependencies = individual.pop("dependency_ids")
        missing = set(dependencies)
        representatives = {}
        # A constructor and its recursor may have the same declaration group.
        # Match the canonical first representative in the signed name table.
        if missing:
            name_digest = hashlib.sha256()
            with (folder / "names.tsv").open("rb") as names_file:
                for line in names_file:
                    name_digest.update(line)
                    if not missing:
                        continue
                    group, _, name = line.rstrip(b"\n").split(b"\t", 2)
                    group = int(group)
                    if group in missing:
                        representatives[group] = json.loads(name)
                        missing.remove(group)
            if name_digest.hexdigest() != files["names.tsv"]["sha256"]:
                raise ValueError("Invalid archive name-table checksum for dependency representatives")
        if missing:
            raise ValueError("Missing declaration group representative in pinned name index")
        individual["archive_deps"] = [representatives[g] for g in dependencies]
    return {**individual, "schema": 1, "verifier": METHOD, "root": ROOT, "nodes": nodes_used, "standalone_rh_nodes": nodes_used,
            "baseline_nodes": meta["baseline"], "saved_nodes": meta["baseline"] - nodes_used,
            "coverage": {"submitted": len(patches), "reachable": edits_used, "bypassed": len(patches) - edits_used},
            "changed_live_nodes": changed_cost, "reachable_groups": reached, "archive_groups": len(nodes) // 4 - 1,
            "certificate_sha256": individual["certificate_sha256"] if single else legacy, "portfolio_certificate_sha256": legacy,
            "normalized_changes_sha256": normalized, "base_export_sha256": pin["export_sha256"],
            "signature_index_sha256": sig["sha256"], "graph_pin_sha256": digest(graph_pin_bytes),
            "axioms": AXIOMS, "axioms_scope": "pinned-export-upper-bound"}


def manifest_pairs(path, sha):
    if path.stat().st_size > MAX_PACKED:
        raise ValueError("Compressed manifest exceeds the size limit")
    packed = path.read_bytes()
    if sha and digest(packed) != sha:
        raise ValueError("Compressed manifest digest mismatch")
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        total = 0
        while line := stream.readline(MAX_LINE + 1):
            total += len(line)
            if len(line) > MAX_LINE or total > MAX_INPUT:
                raise ValueError("Expanded manifest exceeds the size limit")
            yield json.loads(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--manifest", type=Path)
    group.add_argument("--target")
    parser.add_argument("--donor")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if bool(args.target) != bool(args.donor) or (args.manifest_sha256 and not args.manifest):
        parser.error("Supply --target with --donor, or --manifest with an optional compressed SHA-256")
    pairs = manifest_pairs(args.manifest, args.manifest_sha256) if args.manifest else [(args.target, args.donor)]
    result = check_delta(args.graph, pairs, single=not args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=args.output.parent, delete=False) as f:
        json.dump(result, f, sort_keys=True)
        f.write("\n")
    os.replace(f.name, args.output)


if __name__ == "__main__":
    main()
