"""Bind a delta attestation to the approved checker, original export and verified data files."""
import gzip
import hashlib
import json
from pathlib import Path

JUDGE = Path(__file__).resolve().parent
POLICY = JUDGE / "delta_policy.json"


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _verify_file(path, size, expected, *, compressed=False):
    digest = hashlib.sha256()
    total = 0
    with (gzip.open(path, "rb") if compressed else path.open("rb")) as f:
        while chunk := f.read(min(1 << 20, size + 1 - total)):
            total += len(chunk)
            if total > size:
                raise ValueError(f"Unexpected data size for {path.name}")
            digest.update(chunk)
    if total != size or digest.hexdigest() != expected:
        raise ValueError(f"Incorrect SHA-256 or size for {path.name}")


def _policy_and_identity():
    raw = POLICY.read_bytes()
    policy = json.loads(raw)
    if policy["schema"] != 1 or policy["root"] != "riemannHypothesis":
        raise ValueError("Unsupported delta validation policy")
    for name, sha in policy["source_files"].items():
        if _digest((JUDGE.parent / name).read_bytes()) != sha:
            raise ValueError(f"Trusted delta verification input changed: {name}")
    baseline = json.loads((JUDGE / "baseline.json").read_bytes())
    graph_pin = json.loads((JUDGE / "archive_graph.lock.json").read_bytes())
    sig_pin = json.loads((JUDGE / "reuse/index.lock.json").read_bytes())
    if (graph_pin["export_sha256"] != baseline["compressed_sha256"]
            or sig_pin["export_sha256"] != baseline["compressed_sha256"]
            or baseline["unpacked_sha256"] != policy["upstream"]["raw_sha256"]
            or policy["boundary"]["library_to_archive_edges"] != 0):
        raise ValueError("Mismatched original proof, library boundary, graph or theorem index")
    receipt = (json.dumps(policy["boundary"], sort_keys=True) + "\n").encode()
    if _digest(receipt) != policy["boundary_reproduction"]["receipt_sha256"]:
        raise ValueError("Library boundary differs from the original-source audit receipt")
    identity = {
        "baseline_sha256": baseline["unpacked_sha256"],
        "baseline_compressed_sha256": baseline["compressed_sha256"],
        "graph_sha256": policy["source_files"]["judge/archive_graph.lock.json"],
        "signatures_sha256": sig_pin["sha256"],
        "policy_sha256": _digest(raw),
        "checker_sha256": policy["source_files"]["judge/delta_checker.py"],
    }
    return identity, graph_pin, sig_pin, policy["signature_distribution"]


def policy_identity():
    """Return the evidence identifiers required by the trusted publishing job."""
    return _policy_and_identity()[0]


def authenticate_inputs(graph_dir, signatures_path=None):
    """Check all untrusted asset bytes and return their corresponding trusted evidence identifiers."""
    identity, graph, signatures, distribution = _policy_and_identity()
    for name, spec in graph["files"].items():
        _verify_file(Path(graph_dir) / name, spec["bytes"], spec["sha256"])
    signatures_path = Path(signatures_path) if signatures_path is not None else JUDGE / "reuse/signatures.jsonl.gz"
    _verify_file(signatures_path, distribution["bytes"], distribution["sha256"])
    _verify_file(signatures_path, signatures["bytes"], signatures["sha256"], compressed=True)
    return identity
