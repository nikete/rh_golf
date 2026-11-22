"""Recount the candidate archive graph with the saved replacement footprints."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="RH Golf checkout")
    parser.add_argument("--graph", required=True, type=Path, help="Pinned graph directory")
    parser.add_argument("--portfolio", required=True, type=Path, help="Compressed #18 substitution manifest")
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve() / "judge"))
    from archive_graph import ArchiveGraph, Replacement
    from delta_checker import manifest_pairs
    from delta_policy import authenticate_inputs
    from reuse.portfolio import verify_portfolio

    measurements = json.loads(Path(__file__).with_name("measurements.json").read_bytes())
    authenticate_inputs(args.graph)
    graph = ArchiveGraph(args.graph)
    digest = measurements["portfolio_sha256"]
    result = verify_portfolio(manifest_pairs(args.portfolio, digest), graph)
    before = result["standalone_rh_nodes"]
    if before != measurements["certified_nodes"]:
        raise ValueError("Unexpected starting portfolio")
    patches = result["replacements"].copy()
    for name, row in measurements["replacements"].items():
        path = Path(__file__).with_name(name.split(".")[-1] + "-entry.lean")
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["source_sha256"]:
            raise ValueError("Unexpected replacement source for " + name)
        target = graph.target(name)
        if target in patches:
            raise ValueError("An entry overlaps the exact-reuse portfolio")
        footprint = row["impact"]
        edges = tuple(sorted({graph.lookup(dep) for dep in row["archive_deps"]}))
        patches[target] = Replacement(footprint["private_nodes"], footprint["shared"], edges)
    after, _ = graph.measure(patches)
    print(f"Starting portfolio: {before:,} nodes")
    print(f"Mixed proof projection: {after:,} nodes ({before - after:,} saved)")
    if after != measurements["projected_nodes"]:
        raise ValueError("Projection and recorded measurement disagree")

if __name__ == "__main__":
    main()
