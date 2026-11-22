"""Measure an exact-reuse change against a pinned incumbent and export the combined entry."""
import argparse
import gzip
import json
from pathlib import Path

from delta_checker import MAX_INPUT, MAX_PACKED, check_delta, digest, manifest_pairs, requested_names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--base-sha256", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path)
    source.add_argument("--target")
    parser.add_argument("--donor")
    parser.add_argument("--output", type=Path, required=True, help="New combined .jsonl.gz manifest")
    args = parser.parse_args()
    if bool(args.target) != bool(args.donor):
        parser.error("--target and --donor must be used together")
    if args.output.exists():
        parser.error("--output must be a new file")

    base = requested_names(manifest_pairs(args.base, args.base_sha256))
    pairs = manifest_pairs(args.manifest, None) if args.manifest else [(args.target, args.donor)]
    candidate = requested_names(pairs)

    def measure(changes):
        return check_delta(args.graph, ((json.loads(t), json.loads(d)) for t, d in changes.items()))["nodes"]

    before = measure(base)
    base.update(candidate)
    after = measure(base)
    rows = (b"[" + t + b"," + d + b"]\n" for t, d in base.items())
    raw = b"".join(rows)
    if len(raw) > MAX_INPUT:
        raise ValueError("Combined manifest exceeds the expanded entry limit")
    packed = gzip.compress(raw, mtime=0)
    if len(packed) > MAX_PACKED:
        raise ValueError("Combined manifest exceeds the compressed entry limit")
    with args.output.open("xb") as output:
        output.write(packed)
    print(json.dumps({"base_nodes": before, "combined_nodes": after, "marginal_nodes_saved": before - after,
                      "base_sha256": args.base_sha256, "combined_sha256": digest(packed)}))


if __name__ == "__main__":
    main()
