"""Promote one complete solution using only CI evidence and the immutable score ledger."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit.candidate import SEASON, select
from audit.evidence_logs import archive_checker_logs
from post import update_ledger
from route_audit import subject_id, validate_attestation


def evidence(first, second, count, checks, subject, run, attempt, commit):
    if any(subject_id(build["subject"]) != subject_id(subject) for build in (first, second)):
        raise ValueError("The two builds did not select this frozen entry")
    receipt = {
        "schema": 1, "subject": subject, "solution_sha256": first["solution_sha256"],
        "reproductions": [first["solution_sha256"], second["solution_sha256"]],
        "measured_root": count["root"], "measured_nodes": count["nodes"],
        "measured_export_sha256": count["export_sha256"], "mathlib_inventory_sha256": count["mathlib_inventory_sha256"],
        "checker_receipt": checks, "run": run, "attempt": attempt, "commit": commit,
    }
    validate_attestation(receipt, subject)
    return receipt


def store_attestation(ledger, subject, attestation):
    """Keep the first valid receipt per policy, and allow identical-proof re-audits."""
    validate_attestation(attestation, subject)
    path = ledger / SEASON / "audits" / (subject_id(subject) + ".json")
    if path.exists():
        previous = json.loads(path.read_text())
        if (subject_id(previous["subject"]) != subject_id(subject)
                or previous["solution_sha256"] != attestation["solution_sha256"]):
            raise ValueError("Changed subject or solution for a previously certified route")
        old_policy = previous["checker_receipt"]["policy_sha256"]
        if not isinstance(old_policy, str) or not re.fullmatch("[a-f0-9]{64}", old_policy):
            raise ValueError("Previous receipt has no policy digest")
        if old_policy == attestation["checker_receipt"]["policy_sha256"]:
            validate_attestation(previous, subject)
            return
        # Both prior and replacement receipts remain in the ledger's Git history.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(attestation, sort_keys=True, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--build-a", type=Path, required=True)
    parser.add_argument("--build-b", type=Path, required=True)
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--checks", type=Path, required=True)
    args = parser.parse_args()
    inputs = [json.loads(p.read_text()) for p in (args.build_a, args.build_b, args.measurement, args.checks)]

    def write(ledger):
        subject = select(ledger, args.issue, None)["subject"]
        attestation = evidence(*inputs, subject, int(os.environ["GITHUB_RUN_ID"]),
                               int(os.environ["GITHUB_RUN_ATTEMPT"]), os.environ["GITHUB_SHA"])
        archive_checker_logs(attestation["checker_receipt"], args.checks.parent, ledger / SEASON / "audits/logs")
        store_attestation(ledger, subject, attestation)

    update_ledger(write, f"Certify the complete proof for entry #{args.issue}")


if __name__ == "__main__":
    main()
