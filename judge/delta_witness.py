"""Generate and check portable exact-reuse certificates against the pinned original archive."""
import argparse
from array import array
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import zlib

import delta_checker as delta


MAGIC = b"RHGWIT1\0"
HEADER = struct.Struct("<8s32s32sBII")
OVERRIDE = struct.Struct("<II")
MAX_PACKED = 32 << 20


@dataclass
class Instance:
    nodes: object
    edges: object
    patches: dict
    root: int
    single: bool
    report: dict

    @property
    def count(self):
        return len(self.nodes) // 4 - 1

    def dependencies(self, group):
        patch = self.patches.get(group)
        if patch is not None:
            return patch[1]
        offset = self.nodes[4 * group + 1]
        return self.edges[offset:offset + self.nodes[4 * group + 2]]


def _representatives(path, pin, groups):
    if not groups:
        return []
    missing = set(groups)
    representatives = {}
    sha = hashlib.sha256()
    with path.open("rb") as names:
        for line in names:
            sha.update(line)
            if missing:
                group, _, name = line.rstrip(b"\n").split(b"\t", 2)
                group = int(group)
                if group in missing:
                    representatives[group] = json.loads(name)
                    missing.remove(group)
    if missing or sha.hexdigest() != pin["sha256"]:
        raise ValueError("Invalid dependency representatives in pinned name index")
    return [representatives[g] for g in groups]


def _load(graph_dir, pairs, single):
    folder = Path(graph_dir)
    graph_bytes = (delta.JUDGE / "archive_graph.lock.json").read_bytes()
    graph = json.loads(graph_bytes)
    sig = json.loads((delta.JUDGE / "reuse/index.lock.json").read_bytes())
    base = json.loads((delta.JUDGE / "baseline.json").read_bytes())
    files = graph["files"]
    manifest = json.loads(delta.checked((folder / "manifest.json").read_bytes(), files["manifest.json"], "graph manifest"))
    if (set(files) != delta.MEMBERS or base["root"] != delta.ROOT or base["metric"] != delta.METRIC
            or manifest["version"] != 1 or manifest["metric"] != delta.METRIC
            or manifest["baseline"] != base["archive_nodes"]
            or not (manifest["export_sha256"] == graph["export_sha256"] == sig["export_sha256"] == base["compressed_sha256"])):
        raise ValueError("Incompatible pinned graph, signature index or baseline")
    nodes = delta.load_words(folder / "groups.bin", files["groups.bin"])
    edges = delta.load_words(folder / "dependencies.bin", files["dependencies.bin"])
    count = len(nodes) // 4 - 1
    if len(nodes) % 4 or not 0 < manifest["root"] <= count < 2**31:
        raise ValueError("Malformed pinned archive graph")
    requested = delta.requested_names(pairs)
    if single and len(requested) != 1:
        raise ValueError("Single-theorem mode requires one pair")
    single_names = tuple(map(json.loads, next(iter(requested.items())))) if single else None
    pending = delta.resolve_groups(folder / "names.tsv", files["names.tsv"], requested, manifest["root"])
    del requested
    patches, portfolio, normalized, detail = delta.read_patches(
        pending, delta.JUDGE / "reuse/signatures.jsonl.gz", sig, count + 1, single_names)
    if single:
        detail["archive_deps"] = _representatives(folder / "names.tsv", files["names.tsv"], detail.pop("dependency_ids"))
    report = {"schema": 1, "verifier": delta.METHOD, "root": delta.ROOT, "baseline_nodes": base["archive_nodes"],
              "archive_groups": count, "portfolio_certificate_sha256": portfolio, "certificate_sha256": portfolio,
              "normalized_changes_sha256": normalized, "base_export_sha256": graph["export_sha256"],
              "signature_index_sha256": sig["sha256"], "graph_pin_sha256": delta.digest(graph_bytes),
              "axioms": delta.AXIOMS, "axioms_scope": "pinned-export-upper-bound", **detail}
    return Instance(nodes, edges, patches, manifest["root"], single, report)


def _produced_ranks_and_live(instance):
    n = instance.count
    live = bytearray(n + 1)
    live[instance.root] = 1
    # The original ID order is already a witness unless an edit adds a forward edge.
    if all(child < group for group, (_, deps) in instance.patches.items() for child in deps):
        for group in range(n, 0, -1):
            if live[group]:
                for child in instance.dependencies(group):
                    live[child] = 1
        return b"", live

    # Produce an order, including disconnected groups, to construct ranks for forward references.
    incoming = array("I", [0]) * (n + 1)
    for group in range(1, n + 1):
        for child in instance.dependencies(group):
            incoming[child] += 1
    order = array("I", (g for g in range(1, n + 1) if not incoming[g]))
    cursor = 0
    while cursor < len(order):
        group = order[cursor]
        cursor += 1
        for child in instance.dependencies(group):
            if live[group]:
                live[child] = 1
            incoming[child] -= 1
            if not incoming[child]:
                order.append(child)
    if len(order) != n:
        raise ValueError("Cyclic theorem substitutions, including off-root declarations")
    # Minimal pointwise rank >= original ID. Incomparable groups may share a rank.
    ranks = array("I", range(n + 1))
    for group in reversed(order):
        rank = group
        for child in instance.dependencies(group):
            if ranks[child] >= rank:
                rank = ranks[child] + 1
        ranks[group] = rank
    changes = bytearray()
    for group in range(1, n + 1):
        if ranks[group] != group:
            changes.extend(OVERRIDE.pack(group, ranks[group]))
    return changes, live


def _bitset(live):
    bits = bytearray((len(live) + 7) // 8)
    for group, present in enumerate(live):
        if present:
            bits[group >> 3] |= 1 << (group & 7)
    return bits


def make_witness(graph_dir, pairs, *, single=False):
    """Return a portable gzip witness bound to the exact submitted aliases and graph."""
    instance = _load(graph_dir, pairs, single)
    changes, live = _produced_ranks_and_live(instance)
    header = HEADER.pack(MAGIC, bytes.fromhex(instance.report["graph_pin_sha256"]),
                         bytes.fromhex(instance.report["normalized_changes_sha256"]), single,
                         instance.count, len(changes) // OVERRIDE.size)
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", filename="", mtime=0, compresslevel=9) as f:
        f.write(header)
        f.write(changes)
        f.write(_bitset(live))
    return out.getvalue()


def _decode(instance, packed):
    n = instance.count
    if not isinstance(packed, bytes) or not len(packed) <= MAX_PACKED:
        raise ValueError("Portable witness exceeds the compressed size limit")
    bits_size = (n + 8) // 8
    max_size = HEADER.size + OVERRIDE.size * n + bits_size
    try:
        z = zlib.decompressobj(16 + zlib.MAX_WBITS)
        raw = z.decompress(packed, max_size + 1)
        if not z.eof or z.unused_data or z.unconsumed_tail or not HEADER.size <= len(raw) <= max_size:
            raise ValueError("Malformed witness length or trailing gzip data")
    except zlib.error as err:
        raise ValueError("Malformed compressed witness") from err
    magic, pin, aliases, single, count, overrides = HEADER.unpack_from(raw)
    if (magic != MAGIC or count != n or single != int(instance.single)
            or pin.hex() != instance.report["graph_pin_sha256"] or aliases.hex() != instance.report["normalized_changes_sha256"]):
        raise ValueError("Witness does not match the graph, mode or submitted theorem substitutions")
    stop = HEADER.size + OVERRIDE.size * overrides
    if len(raw) != stop + bits_size:
        raise ValueError("Incorrect number of rank overrides or closure bits")
    ranks = array("I", range(n + 1))
    prev = 0
    for group, rank in OVERRIDE.iter_unpack(memoryview(raw)[HEADER.size:stop]):
        if not prev < group <= n or not 1 <= rank <= 2 * n or rank == group:
            raise ValueError("Invalid or duplicate topological rank override")
        prev = group
        ranks[group] = rank
    bits = raw[stop:]
    if bits[0] & 1 or bits[-1] >> ((n % 8) + 1):
        raise ValueError("Nonzero reserved or padding coverage bits")
    return ranks, bits


def verify_witness(graph_dir, pairs, witness, *, single=False):
    """Check a supplied proof linearly and return the same score report as check_delta."""
    instance = _load(graph_dir, pairs, single)
    ranks, bits = _decode(instance, witness)
    n = instance.count
    live = bytearray((bits[g >> 3] >> (g & 7)) & 1 for g in range(n + 1))
    justified = bytearray(n + 1)
    justified[instance.root] = 1
    cost = reached = edited = local = 0
    for group in range(1, n + 1):
        rank = ranks[group]
        present = live[group]
        for child in instance.dependencies(group):
            # Every edge in every component must strictly descend. No permission
            # to skip unchanged edges: their endpoints may have been reranked.
            if not 1 <= child <= n or ranks[child] >= rank:
                raise ValueError("A dependency does not strictly decrease the supplied ranks")
            if present:
                justified[child] = 1
        if present:
            reached += 1
            patch = instance.patches.get(group)
            if patch is None:
                cost += instance.nodes[4 * group]
            else:
                cost += patch[0]
                local += patch[0]
                edited += 1
    # S={root} ∪ children(S) gives both containment directions. In a finite DAG
    # every member justified by a live parent traces back to the distinguished root.
    if live != justified:
        raise ValueError("Claimed coverage is not exactly the ordinary RH dependency closure")
    return {**instance.report, "nodes": cost, "standalone_rh_nodes": cost,
            "saved_nodes": instance.report["baseline_nodes"] - cost, "changed_live_nodes": local,
            "reachable_groups": reached, "coverage": {"submitted": len(instance.patches),
                    "reachable": edited, "bypassed": len(instance.patches) - edited}}


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
        out.write(data)
    os.replace(out.name, path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["create", "verify"])
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--witness", type=Path, required=True)
    p.add_argument("--witness-sha256", help="Expected digest of the compressed witness on verification")
    p.add_argument("--output", type=Path, help="Write the successful JSON report on verification")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--manifest", type=Path)
    g.add_argument("--target")
    p.add_argument("--manifest-sha256")
    p.add_argument("--donor")
    args = p.parse_args()
    if bool(args.target) != bool(args.donor) or (args.manifest_sha256 and not args.manifest):
        p.error("Use --target with --donor, or --manifest with an optional compressed SHA-256")
    pairs = delta.manifest_pairs(args.manifest, args.manifest_sha256) if args.manifest else [(args.target, args.donor)]
    if args.action == "create":
        if args.witness_sha256 or args.output:
            p.error("--witness-sha256 and --output apply to verification")
        data = make_witness(args.graph, pairs, single=not args.manifest)
        _atomic(args.witness, data)
        print(json.dumps({"bytes": len(data), "sha256": delta.digest(data)}, sort_keys=True))
    else:
        with args.witness.open("rb") as f:
            data = f.read(MAX_PACKED + 1)
        if args.witness_sha256 and delta.digest(data) != args.witness_sha256:
            raise ValueError("Compressed witness SHA-256 mismatch")
        report = verify_witness(args.graph, pairs, data, single=not args.manifest)
        result = delta.encode(report) + b"\n"
        if args.output:
            _atomic(args.output, result)
        else:
            print(result.decode().rstrip())


if __name__ == "__main__":
    main()
