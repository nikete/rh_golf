"""Verify frozen exact-reuse entries on a read-only runner and record their evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from archive_portfolio import PORTFOLIO_VERIFIER
from audit.candidate import BASELINE, read_entry
from delta_checker import check_delta
from delta_policy import authenticate_inputs, policy_identity
from post import update_ledger
from reuse import METHOD as SINGLE_REUSE
from reuse.manifest import fetch_pairs
from route_audit import (make_subject, subject_id, validate_delta_attestation, validate_delta_report,
                         validate_delta_source, validate_stored_entrant_proof)
from run import (PORTFOLIO, REUSE, ROOT, SEASON, Rejected, directives, valid_target,
                 validate_score, validate_source)

METHODS = (SINGLE_REUSE, PORTFOLIO_VERIFIER)
BATCH = "checked.json"


def _equal(left, right):
    # JSON booleans must not stand in for numeric zero or one.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def _instruction(row, source):
    if isinstance(source, Path):
        source = source.read_bytes()
    elif isinstance(source, str):
        source = source.encode()
    return validate_delta_source(row, source)


def derive(row, source, graph_dir, inputs):
    """Check a normalized entrant source and fast receipt; no public issue is required."""
    instruction = _instruction(row, source)
    if inputs != policy_identity():
        raise ValueError("Delta input identities differ from the active checkout")
    single = row["verifier"] == SINGLE_REUSE
    pairs = (instruction,) if single else fetch_pairs(*instruction)
    report = check_delta(graph_dir, pairs, single=single)
    validate_delta_report(report, row, inputs, BASELINE)
    return report


def score_from_report(hole, source, report):
    """Reconstruct the primary score from the independently verified witness and submitted instruction."""
    if not valid_target(hole) or not isinstance(report, dict):
        raise ValueError("Missing theorem target or verified delta report")
    if isinstance(source, bytes):
        source = source.decode("utf-8")
    try:
        original = validate_source(source)
        nominations, body = directives(original)
    except Rejected as exc:
        raise ValueError(str(exc)) from exc
    score = {"status": "accepted", "season": SEASON, "hole": hole, "helpers": 0,
             "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
             "certificate_sha256": report["certificate_sha256"], "axioms": report["axioms"],
             "axioms_scope": report["axioms_scope"], "standalone_rh_nodes": report["standalone_rh_nodes"]}
    donor = REUSE.fullmatch(body)
    manifest = PORTFOLIO.fullmatch(body)
    if donor:
        local = report["local_nodes"]
        score.update(verifier=SINGLE_REUSE, reuse_donor=donor[1].strip(), nodes=local,
                     reuse_statement_id=report["reuse_statement_id"],
                     reuse_universe_parameters=report["reuse_universe_parameters"], archive_deps=report["archive_deps"],
                     impact={"version": 1, "private_nodes": local, "shared": {}})
        if nominations:
            score["combine"] = nominations
    elif manifest:
        score.update(verifier=PORTFOLIO_VERIFIER, nodes=report["changed_live_nodes"],
                     portfolio_url=manifest[1], portfolio_sha256=manifest[2], portfolio_coverage=report["coverage"])
    else:
        raise ValueError("Expected one exact theorem reuse or immutable portfolio instruction")
    validate_delta_source(score, original.encode())
    validate_score(score)
    validate_delta_report(report, score, policy_identity(), BASELINE)
    return score


def subject_for(row):
    if row.get("verifier") not in METHODS:
        raise ValueError("This proof requires whole-export verification")
    route = "archive-portfolio" if row["verifier"] == PORTFOLIO_VERIFIER else "standalone-replacement"
    return make_subject([row], route, [row["issue"]], row["standalone_rh_nodes"], BASELINE)


def envelope(row, inputs, report, run, attempt, commit, entrant_proof=None):
    """Bind a verified delta to this exact issue and its publication run."""
    subject = subject_for(row)
    evidence = {"schema": 1, "verification_kind": "exact-reuse-delta", "subject": subject,
                "inputs": inputs, "report": report, "run": run, "attempt": attempt, "commit": commit}
    if entrant_proof is not None:
        evidence["entrant_proof"] = entrant_proof
    validate_delta_attestation(evidence, subject, row, BASELINE)
    return evidence


def _sidecar(ledger, subject):
    return ledger / SEASON / "deltas" / (subject_id(subject) + ".json")


def _verified(ledger, row, subject):
    path = _sidecar(ledger, subject)
    if not path.is_file():
        return False
    try:
        prior = json.loads(path.read_text())
        validate_delta_attestation(prior, subject, row, BASELINE)
        if "entrant_proof" in prior:
            validate_stored_entrant_proof(ledger / SEASON / str(row["issue"]), row, prior)
    except (ValueError, TypeError, KeyError, FileNotFoundError):
        return False
    return True


def _should_backfill(ledger, row, subject):
    if _verified(ledger, row, subject):
        return False
    folder = ledger / SEASON / str(row["issue"])
    attached = (folder / "entrant-proof.json").exists() or (folder / "entrant.rhproof.gz").exists()
    path = _sidecar(ledger, subject)
    if path.exists():
        try:
            existing = json.loads(path.read_bytes())
            attached = attached or not isinstance(existing, dict) or "entrant_proof" in existing
        except ValueError:
            # An unreadable receipt may be the only surviving record of a local witness.
            attached = True
    if attached:
        print(f"Issue #{row['issue']} remains pending because its local evidence needs repair.", file=sys.stderr)
        return False
    return True


def _origin():
    run = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    commit = os.environ.get("GITHUB_SHA")
    if not any((run, attempt, commit)):
        return None
    if (not re.fullmatch(r"[1-9][0-9]*", run or "") or not re.fullmatch(r"[1-9][0-9]*", attempt or "")
            or not re.fullmatch(r"[0-9a-f]{40}", commit or "")):
        raise ValueError("Incomplete GitHub Actions provenance")
    return {"run": int(run), "attempt": int(attempt), "commit": commit}


def _selected(ledger, issue, run):
    if issue is not None:
        if type(issue) is not int or issue < 1:
            raise ValueError("Expected a positive issue number")
        return [issue]
    paths = (ledger / SEASON).glob("*/score.json")
    if run is not None:
        if type(run) is not int or run < 1:
            raise ValueError("Expected a positive original judge run")
        paths = [path for path in paths if _equal(json.loads(path.read_text()).get("run"), run)]
        if len(paths) > 1:
            raise ValueError("The original judge run identifies more than one frozen entry")
    return sorted(int(p.parent.name) for p in paths)


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False)
    try:
        with tmp as out:
            json.dump(data, out, sort_keys=True, indent=2, allow_nan=False)
            out.write("\n")
        os.replace(tmp.name, path)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def check(ledger, graph, output, issue=None, run=None):
    output.mkdir(parents=True, exist_ok=True)
    batch_path = output / BATCH
    batch_path.unlink(missing_ok=True)
    pending = []
    for n in _selected(ledger, issue, run):
        row, source = read_entry(ledger, n)
        if row.get("verifier") not in METHODS:
            continue
        _instruction(row, source)
        subject = subject_for(row)
        if _should_backfill(ledger, row, subject):
            pending.append((row, source, subject))
    entries = []
    if pending:
        # A fully backfilled ledger never downloads the graph or a manifest.
        if not (graph / "manifest.json").is_file():
            subprocess.run([sys.executable, str(ROOT / "judge/fetch_graph.py"), "--directory", str(graph)], check=True)
        inputs = authenticate_inputs(graph)
        for row, source, subject in pending:
            report = derive(row, source, graph, inputs)
            entries.append({"issue": row["issue"], "subject": subject, "inputs": inputs, "report": report})
    _write_json(batch_path, {"schema": 1, "origin": _origin(), "entries": entries})
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            print(f"verified_count={len(entries)}", file=stream)
    return len(entries)


def apply_batch(ledger, batch, origin):
    if (not isinstance(batch, dict) or set(batch) != {"schema", "origin", "entries"}
            or not _equal(batch["schema"], 1) or not isinstance(batch["entries"], list)
            or not origin or not _equal(batch["origin"], origin)):
        raise ValueError("Invalid delta batch or mismatched GitHub verification run")
    seen = set()
    writes = []
    for item in batch["entries"]:
        if not isinstance(item, dict) or set(item) != {"issue", "subject", "inputs", "report"}:
            raise ValueError("Unexpected delta batch entry")
        issue = item["issue"]
        if type(issue) is not int or issue <= 0 or issue in seen:
            raise ValueError("Invalid or duplicated issue in delta batch")
        seen.add(issue)
        row, source = read_entry(ledger, issue)
        _instruction(row, source)
        evidence = envelope(row, item["inputs"], item["report"], **origin)
        if not _equal(item["subject"], evidence["subject"]):
            raise ValueError("The verified delta refers to a different immutable ledger subject")
        if _should_backfill(ledger, row, evidence["subject"]):
            writes.append((_sidecar(ledger, evidence["subject"]), evidence))
    for path, evidence in writes:
        _write_json(path, evidence)


def record(input_dir):
    batch = json.loads((input_dir / BATCH).read_text())
    origin = _origin()
    if not isinstance(batch, dict) or not origin or not _equal(batch.get("origin"), origin):
        raise ValueError("Only an artifact produced by this GitHub workflow run can be recorded")
    if batch.get("entries") == []:
        apply_batch(Path("."), batch, origin)
        return
    update_ledger(lambda ledger: apply_batch(ledger, batch, origin), "Record verified incremental proof deltas")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("check")
    validate.add_argument("--ledger", type=Path, required=True)
    validate.add_argument("--graph", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    select = validate.add_mutually_exclusive_group()
    select.add_argument("--issue", type=int)
    select.add_argument("--run", type=int)
    select.add_argument("--backfill", action="store_true")
    publish = commands.add_parser("record")
    publish.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "check":
        print(f"{check(args.ledger, args.graph, args.output, args.issue, args.run)} verified delta(s)")
    else:
        record(args.input)


if __name__ == "__main__":
    main()
