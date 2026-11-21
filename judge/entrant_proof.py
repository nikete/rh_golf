"""Generate a portable substitution witness locally, or verify one against the audited RH archive."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

import delta_witness
from delta_entry import score_from_report
from delta_policy import authenticate_inputs, policy_identity
from reuse import manifest
import run

FORMAT = "rh-golf-local-witness-v1"
GRAPH = run.ROOT / ".out/archive-graph"
HEX = re.compile(r"[0-9a-f]{64}")
ISSUE_BYTES = 65536


def sha(data):
    return hashlib.sha256(data).hexdigest()


def package_bytes(value):
    return (json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode()


def _unique(pairs):
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise ValueError("Duplicate fields in entrant proof")
    return obj


def _source(text):
    try:
        return run.validate_source(text)
    except run.Rejected as exc:
        raise ValueError(str(exc)) from exc


def parse_package(raw, target, source, policy_hash):
    if not isinstance(raw, (str, bytes)) or len(raw) > 2 * delta_witness.MAX_PACKED:
        raise ValueError("Invalid entrant proof size")
    try:
        pkg = json.loads(raw, object_pairs_hook=_unique)
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("Invalid entrant proof JSON") from exc
    fields = {"format", "target", "source_sha256", "policy_sha256", "claimed_nodes", "witness_sha256"}
    if not isinstance(pkg, dict) or set(pkg) not in (fields | {"witness_base64"}, fields | {"witness_url"}):
        raise ValueError("Supply exactly one inline or linked witness and all required proof fields")
    if (pkg["format"] != FORMAT or not run.valid_target(target) or pkg["target"] != target
            or pkg["source_sha256"] != sha(_source(source).encode()) or pkg["policy_sha256"] != policy_hash
            or not isinstance(pkg["witness_sha256"], str) or not HEX.fullmatch(pkg["witness_sha256"])
            or type(pkg["claimed_nodes"]) is not int or not 0 < pkg["claimed_nodes"] <= 2**63 - 1):
        raise ValueError("Entrant proof target, source, policy, witness digest or claimed size is invalid")
    if "witness_url" in pkg:
        manifest.validate_url(pkg["witness_url"], suffix=".rhproof.gz")
    else:
        if not isinstance(pkg["witness_base64"], str):
            raise ValueError("Expected a base64 witness")
        check_binary(pkg, base64.b64decode(pkg["witness_base64"], validate=True))
    return pkg


def check_binary(pkg, data):
    if not 0 < len(data) <= delta_witness.MAX_PACKED or sha(data) != pkg["witness_sha256"]:
        raise ValueError("Supplied witness size or SHA-256 differs from its receipt")


def limited_file(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{path.name} exceeds the size limit")
    return data


def _instance(target, source, local_manifest):
    if not run.valid_target(target):
        raise ValueError("Invalid target")
    try:
        nominees, body = run.directives(_source(source))
    except run.Rejected as exc:
        raise ValueError(str(exc)) from exc
    donor = run.REUSE.fullmatch(body)
    portfolio = run.PORTFOLIO.fullmatch(body)
    if donor and not local_manifest:
        return True, lambda: [(target, donor[1].strip())]
    if portfolio and target == "riemannHypothesis" and not nominees:
        url, digest = portfolio.groups()
        manifest.validate_url(url)
        data = (limited_file(local_manifest, manifest.MAX_COMPRESSED) if local_manifest
                else manifest._download(url).getvalue())
        return False, lambda: manifest.read_pairs(io.BytesIO(data), digest)
    raise ValueError("Local witnesses cover exact theorem reuse or a complete reuse-file portfolio")


def _graph(directory):
    if not (directory / "manifest.json").is_file():
        subprocess.run([sys.executable, str(run.ROOT / "judge/fetch_graph.py"), "--directory", str(directory)], check=True)
    return authenticate_inputs(directory)


def verify(raw, target, source, graph=GRAPH, *, witness=None, local_manifest=None):
    inputs = policy_identity()
    pkg = parse_package(raw, target, source, inputs["policy_sha256"])
    if witness is not None:
        data = limited_file(witness, delta_witness.MAX_PACKED)
    elif "witness_base64" in pkg:
        data = base64.b64decode(pkg["witness_base64"], validate=True)
    else:
        data = manifest._download(pkg["witness_url"]).getvalue()
    check_binary(pkg, data)
    single, pairs = _instance(target, source, local_manifest)
    _graph(graph)
    report = delta_witness.verify_witness(graph, pairs(), data, single=single)
    if pkg["claimed_nodes"] != report["standalone_rh_nodes"]:
        raise ValueError("The supplied node count differs from the checked witness")
    score = score_from_report(target, source, report)
    return pkg, inputs, report, score, data


def receive(raw, target, source, output):
    pkg, inputs, report, score, data = verify(raw, target, source)
    output.mkdir(parents=True, exist_ok=True)
    (output / "entrant.rhproof.gz").write_bytes(data)
    evidence = {"receipt_sha256": sha(package_bytes(pkg)), "inputs": inputs, "report": report}
    (output / "witness-result.json").write_bytes(package_bytes(evidence))
    return score


def write_issue(output, source, pkg):
    raw = package_bytes(pkg)
    (output / "entrant-proof.json").write_bytes(raw)
    body = "```lean\n" + source + "```\n\n```rh-proof\n" + raw.decode() + "```\n"
    issue = output / "issue.md"
    if len(body.encode()) > ISSUE_BYTES:
        issue.unlink(missing_ok=True)
        print("Witness verified locally. Publish entrant.rhproof.gz at a commit-pinned raw GitHub URL, then use the link command.")
    else:
        issue.write_text(body, encoding="utf-8")
        print(f"Ready to submit: {output / 'title.txt'} and {issue}")


def make(target, source, output, graph=GRAPH, *, local_manifest=None, witness_url=None):
    source = _source(source)
    if witness_url:
        manifest.validate_url(witness_url, suffix=".rhproof.gz")
    single, pairs = _instance(target, source, local_manifest)
    inputs = _graph(graph)
    data = delta_witness.make_witness(graph, pairs(), single=single)
    report = delta_witness.verify_witness(graph, pairs(), data, single=single)
    score = score_from_report(target, source, report)
    pkg = {"format": FORMAT, "target": target, "source_sha256": score["source_sha256"],
           "policy_sha256": inputs["policy_sha256"], "claimed_nodes": score["standalone_rh_nodes"],
           "witness_sha256": sha(data)}
    pkg.update({"witness_url": witness_url} if witness_url else {"witness_base64": base64.b64encode(data).decode()})
    output.mkdir(parents=True, exist_ok=True)
    (output / "entrant.rhproof.gz").write_bytes(data)
    (output / "title.txt").write_text("[entry] " + target + "\n", encoding="utf-8")
    (output / "Entry.lean").write_text(source, encoding="utf-8")
    write_issue(output, source, pkg)
    print(f"{pkg['claimed_nodes']:,} RH nodes verified locally. Witness {len(data):,} bytes, SHA-256 {sha(data)}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    create = commands.add_parser("make", help="Generate and check a witness on this machine")
    check = commands.add_parser("verify", help="Verify a supplied witness independently")
    for cmd in (create, check):
        cmd.add_argument("--target", required=True)
        cmd.add_argument("--source", type=Path, required=True)
        cmd.add_argument("--manifest", type=Path, help="Use locally available bytes of the pinned reuse-file")
        cmd.add_argument("--graph", type=Path, default=GRAPH)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--witness-url", help="Commit-pinned raw GitHub URL for the generated .rhproof.gz")
    check.add_argument("--proof", type=Path, required=True)
    check.add_argument("--witness", type=Path, help="Use locally available witness bytes")
    link = commands.add_parser("link", help="Prepare a shorter issue from an already generated witness")
    link.add_argument("--output", type=Path, required=True)
    link.add_argument("--witness-url", required=True)
    args = parser.parse_args()
    if args.action == "link":
        folder = args.output
        source = (folder / "Entry.lean").read_text(encoding="utf-8")
        target = (folder / "title.txt").read_text(encoding="utf-8").rstrip("\n").removeprefix("[entry] ")
        pkg = parse_package((folder / "entrant-proof.json").read_bytes(), target, source, policy_identity()["policy_sha256"])
        check_binary(pkg, limited_file(folder / "entrant.rhproof.gz", delta_witness.MAX_PACKED))
        pkg.pop("witness_base64", None)
        pkg["witness_url"] = manifest.validate_url(args.witness_url, suffix=".rhproof.gz")
        write_issue(folder, source, pkg)
    elif args.action == "make":
        make(args.target, args.source.read_text(encoding="utf-8"), args.output, args.graph,
             local_manifest=args.manifest, witness_url=args.witness_url)
    else:
        result = verify(limited_file(args.proof, 2 * delta_witness.MAX_PACKED), args.target,
                        args.source.read_text(encoding="utf-8"), args.graph, witness=args.witness, local_manifest=args.manifest)
        print(json.dumps(result[3], indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as err:
        raise SystemExit(str(err)) from err
