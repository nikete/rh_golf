"""Search one local round of the RH exact-theorem-reuse tournament."""
import argparse
import gzip
import hashlib
import heapq
import json
import os
from pathlib import Path
import random
import secrets
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "judge"))
from archive_graph import ArchiveGraph, IncompatibleReplacements, Replacement
from reuse import signature_index
from reuse.manifest import MAX_COMPRESSED, MAX_EXPANDED, MAX_LINE, MAX_PAIRS, fetch_pairs
from reuse.portfolio import METHOD, canonical, verify_portfolio

SCORES = "https://nikete.github.io/rh_golf/scores.json"
OUT = ROOT / ".out"


def load_seed(graph, row):
    """Retain compact JSON for editing, and verify the published seed receipt."""
    encoded = {}
    if row is None:
        return encoded, {}, graph.baseline

    def pairs():
        for target, donor in fetch_pairs(row["portfolio_url"], row["portfolio_sha256"]):
            encoded[graph.target(target)] = canonical([target, donor])
            yield target, donor

    result = verify_portfolio(pairs(), graph)
    if (result["standalone_rh_nodes"] != row["standalone_rh_nodes"]
            or result["certificate_sha256"] != row["certificate_sha256"]):
        raise ValueError("The published seed receipt differs from the local verification")
    return encoded, result["replacements"], result["standalone_rh_nodes"]


def proposals(graph, patches):
    """Try the other original proof in a two-theorem signature class."""
    _, _, signatures = signature_index()
    for _, _, statement_size, deps, members, library in signatures:
        if len(members) != 2 or library:
            continue
        target, donor = members
        if patches:
            # With no library donor, the only possible alias in this class
            # points at its other member. Reverse it and restore the old body.
            if target in patches:
                target, donor = donor, target
            if donor not in patches or target in patches:
                continue
            estimate = graph.nodes[4*target] - graph.nodes[4*donor]
        else:
            # Before the first portfolio, start with an untouched archive.
            target, donor = sorted(members, key=lambda g: graph.nodes[4*g], reverse=True)
            estimate = graph.nodes[4*target] - statement_size - 1
        if estimate > 0 and target not in graph._original(donor):
            yield estimate, target, donor, statement_size + 1, deps


def search(graph, encoded, patches, best, trials, seed):
    # Try the most promising local savings first, then sample other classes.
    # The local estimate ignores dependency sharing. Only whole-RH cost decides.
    ranked = heapq.nlargest(10 * trials, proposals(graph, patches))
    top = min(len(ranked), (trials + 1) // 2)
    rest = ranked[top:]
    choices = ranked[:top] + random.Random(seed).sample(rest, min(len(rest), trials - top))
    wanted = {g for _, target, donor, _, _ in choices for g in (target, donor)}
    names = {g: name for name, g in graph.names.items() if g in wanted}
    if not choices:
        print("No eligible pair in this search strategy.")
    closest = None
    for i, (_, target, donor, nodes, deps) in enumerate(choices, 1):
        edited = patches.copy()
        edited.pop(donor, None)
        edited[target] = Replacement(nodes, {}, tuple(sorted({*deps, donor})))
        try:
            # The same graph traversal as the bulk verifier, including cycle
            # checks on substitutions outside the currently reachable proof.
            cost, _ = graph._full_measure(edited, {})
        except IncompatibleReplacements:
            print(f"Trial {i}: cyclic substitution", flush=True)
            continue
        closest = cost if closest is None else min(closest, cost)
        print(f"Trial {i}: {cost:,} nodes ({best - cost:+,} vs local best)", flush=True)
        if cost < best:
            label = ".".join(str(part) for part in json.loads(names[target]))
            print(f"  Improved {label}", flush=True)
            patches, best = edited, cost
            encoded.pop(donor, None)
            encoded[target] = b"[" + names[target] + b"," + names[donor] + b"]"
    return best, closest


def write_candidate(encoded):
    folder = OUT / "agent-round"
    folder.mkdir(parents=True, exist_ok=True)
    if (len(encoded) > MAX_PAIRS or sum(len(line)+1 for line in encoded.values()) > MAX_EXPANDED
            or any(len(line)+1 > MAX_LINE for line in encoded.values())):
        raise ValueError("Candidate exceeds the tournament manifest limits")
    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as temp:
        path = Path(temp.name)
    try:
        with path.open("wb") as output, gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0, compresslevel=9) as packed:
            for group in sorted(encoded):
                packed.write(encoded[group] + b"\n")
        if path.stat().st_size > MAX_COMPRESSED:
            raise ValueError("Candidate exceeds the compressed manifest size limit")
        with path.open("rb") as content:
            digest = hashlib.file_digest(content, "sha256").hexdigest()
        candidate = folder / f"candidate-{digest}.jsonl.gz"
        os.replace(path, candidate)
        return candidate, digest
    finally:
        path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, help="repeat a run with this seed (default: generate a fresh seed)")
    parser.add_argument("--trials", type=int, default=6, help="maximum number of whole-proof trials (default: 6)")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("Python 3.11 or later is required")
    if args.trials < 1:
        parser.error("--trials must be positive")
    seed = args.seed if args.seed is not None else secrets.randbits(32)
    print(f"Seed {seed}, up to {args.trials} trials.", flush=True)
    with urlopen(Request(SCORES, headers={"User-Agent": "RH-Golf-agent-round"}), timeout=30) as response:
        board = json.load(response)
    project = board.get("provisional_project", board["project"])
    record = project["current_nodes"]
    portfolios = [row for row in board["accepted"] if row.get("verifier") == METHOD]
    row = min(portfolios, key=lambda r: (r["standalone_rh_nodes"], r["issue"]), default=None)
    source = f"portfolio #{row['issue']}" if row else "the untouched archive"
    print(f"Best measured RH proof: {record:,} nodes. Starting from {source}.", flush=True)
    subprocess.run([sys.executable, str(ROOT / "judge/fetch_graph.py")], check=True)
    graph = ArchiveGraph(OUT / "archive-graph")
    if graph.baseline != project["archive_nodes"] or project["metric"] != "rh-declaration-nodes-v1":
        raise ValueError("The published board uses a different baseline or metric; update this checkout")
    encoded, patches, start = load_seed(graph, row)
    print(f"Verified starting proof: {start:,} nodes.", flush=True)
    cost, closest = search(graph, encoded, patches, start, args.trials, seed)
    if cost >= record:
        print(f"No new record. Best local proof: {cost:,} nodes. Best measured RH proof: {record:,}.")
        print(f"Closest valid trial: {closest:,} nodes." if closest is not None else "No valid trial in this sample.")
        return
    result = verify_portfolio((json.loads(line) for line in encoded.values()), graph)
    if result["standalone_rh_nodes"] != cost:
        raise RuntimeError("Final verification differs from the search measurement")
    path, digest = write_candidate(encoded)
    print(f"Measured {record - cost:,} nodes saved against the best public measurement ({cost:,} nodes).")
    print(f"Total saved from original: {graph.baseline - cost:,} nodes ({1 - cost / graph.baseline:.6%}).")
    print(f"Candidate: {path}\nSHA-256: {digest}\nCertificate: {result['certificate_sha256']}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        sys.exit(f"Round failed: {exc}")
