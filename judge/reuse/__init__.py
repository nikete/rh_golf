"""Verify a one-constant theorem body against the pinned, previously checked Lean export."""
import gzip
import hashlib
import json
from pathlib import Path

from archive_graph import Replacement

HERE = Path(__file__).resolve().parent
METHOD = "pinned-export-exact-reuse-v1"
AXIOMS = ["Classical.choice", "Quot.sound", "propext"]


def read_index(path, pin):
    # The pin covers the decompressed bytes, independent of gzip implementation.
    with gzip.open(path, "rb") as stream:
        payload = stream.read(pin["bytes"] + 1)
    if len(payload) != pin["bytes"] or hashlib.sha256(payload).hexdigest() != pin["sha256"]:
        raise RuntimeError("The installed theorem reuse index does not match the pinned digest")
    return payload


def signature_index():
    pin = json.loads((HERE / "index.lock.json").read_text())
    baseline = json.loads((HERE.parent / "baseline.json").read_text())
    if pin["export_sha256"] != baseline["compressed_sha256"]:
        raise RuntimeError("The theorem reuse pin differs from the archive baseline")
    packed = HERE / "signatures.jsonl.gz"
    data = read_index(packed, pin)
    lines = iter(data.splitlines())
    header = json.loads(next(lines))
    if header != {"format": 1, "export": pin["export_sha256"], "axioms": AXIOMS}:
        raise RuntimeError("Unexpected theorem reuse signature header")
    return pin, header, map(json.loads, lines)


def verify_reuse(target, donor, graph, source):
    """Return a scored receipt for replacing a theorem's body with its named donor.

    The kernel constant typing rule gives the donor's original statement
    instantiated at the target universe parameters. Class membership certifies
    both the very same statement expression and the same ordered parameters.
    """
    pin, header, signatures = signature_index()
    target_id = graph.target(target)
    donor_parts = list(graph.name_parts(donor))
    donor_key = json.dumps(donor_parts, ensure_ascii=False, separators=(",", ":")).encode()
    donor_id = graph.names.get(donor_key)
    if donor_id == target_id:
        raise ValueError("A theorem cannot reuse itself")
    for expr, params, nodes, deps, theorems, library in signatures:
        if target_id not in theorems:
            continue
        if donor_id not in theorems and (donor_id is not None or donor_parts not in library):
            break
        if donor_id:
            deps = sorted({*deps, donor_id})
        # The donor cannot occur in its own original type. Its constant
        # expression therefore adds exactly one distinct node to the statement.
        nodes += 1
        patch = Replacement(nodes, {}, tuple(deps))
        cost, _ = graph.measure({target_id: patch})
        by_group = {}
        needed = set(deps)
        for name, group in graph.names.items():
            if group in needed:
                by_group[group] = json.loads(name)
                needed.remove(group)
                if not needed:
                    break
        if needed:
            raise RuntimeError("Missing dependency in the audited name table")
        certificate = {"verifier": METHOD, "export": header["export"], "index": pin["sha256"],
                       "target": graph.name_parts(target), "donor": donor_parts,
                       "statement": expr, "universe_parameters": params}
        encoded = json.dumps(certificate, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return {"verifier": METHOD, "reuse_donor": donor, "reuse_statement_id": expr,
                "reuse_universe_parameters": params, "nodes": nodes, "helpers": 0, "axioms": AXIOMS,
                "axioms_scope": "pinned-export-upper-bound", "impact": {"version": 1, "private_nodes": nodes, "shared": {}},
                "archive_deps": [by_group[g] for g in deps], "standalone_rh_nodes": cost,
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "certificate_sha256": hashlib.sha256(encoded).hexdigest()}
    raise ValueError("No exact match for these theorems' exported statements and ordered universe parameters")
