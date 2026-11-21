"""Publish an immutable score with an optimistic, fast-forward-only ledger update."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
from board import record

BRANCH = "golf-scores"

def git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", str(cwd), *args], check=check, text=True, capture_output=True)

def update_ledger(write, message):
    """Apply a trusted writer against the newest ledger on every push retry."""
    for attempt in range(12):
        with tempfile.TemporaryDirectory() as dirname:
            work = Path(dirname)
            # Use the main checkout's credential via git worktree, never expose it to entries.
            home = Path.cwd()
            result = git(home, "ls-remote", "--exit-code", "origin", "refs/heads/" + BRANCH, check=False)
            if result.returncode not in (0, 2):
                raise RuntimeError("Could not read score ledger: " + result.stderr)
            if result.returncode == 0:
                git(home, "fetch", "--depth=1", "origin", "refs/heads/" + BRANCH)
                git(home, "worktree", "add", "--detach", str(work), "FETCH_HEAD")
            else:
                git(home, "worktree", "add", "--detach", str(work), "HEAD")
            try:
                if result.returncode == 2:
                    git(work, "switch", "--orphan", "scores-init-" + os.environ["GITHUB_RUN_ID"])
                write(work / "ledger")
                git(work, "add", "ledger")
                if git(work, "diff", "--cached", "--quiet", check=False).returncode == 0:
                    return
                git(work, "-c", "user.name=RH Golf", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                    "commit", "-m", message)
                pushed = git(work, "push", "origin", "HEAD:refs/heads/" + BRANCH, check=False)
                if not pushed.returncode:
                    return
                if "rejected" not in pushed.stderr and "cannot lock ref" not in pushed.stderr:
                    raise RuntimeError(pushed.stderr)
            finally:
                git(home, "worktree", "remove", "--force", str(work))
                if result.returncode == 2:
                    git(home, "branch", "-D", "scores-init-" + os.environ["GITHUB_RUN_ID"], check=False)
        time.sleep(min(12, attempt + 1))
    raise RuntimeError("Ledger was busy; rerun this workflow to record the verified entry.")

def publish(event, receipt):
    from run import event_submission, issue_blocks
    from delta_policy import policy_identity
    from entrant_proof import check_binary, limited_file, package_bytes, parse_package, sha
    from delta_entry import score_from_report
    from delta_witness import MAX_PACKED

    raw = issue_blocks(event)[1]
    checked = None
    if raw is not None:
        target, source, _ = event_submission(event)
        inputs = policy_identity()
        pkg = parse_package(raw, target, source, inputs["policy_sha256"])
        data = limited_file(receipt.with_name("entrant.rhproof.gz"), MAX_PACKED)
        check_binary(pkg, data)
        # This artifact comes from the read-only verification job in this run.
        evidence = json.loads(receipt.with_name("witness-result.json").read_bytes())
        score = json.loads(receipt.read_bytes())
        digest = sha(package_bytes(pkg))
        report = evidence["report"]
        if (evidence["inputs"] != inputs or evidence["receipt_sha256"] != digest
                or pkg["claimed_nodes"] != report["standalone_rh_nodes"]
                or package_bytes(score_from_report(target, source, report)) != package_bytes(score)):
            raise ValueError("Verified evidence differs from the submission or published score")
        checked = (pkg, data, inputs, report, {"kind": "local-witness-v1", "receipt_sha256": digest})

    def write(ledger):
        record(event, receipt, ledger)
        if checked is not None:
            save_entrant_evidence(ledger, event["issue"]["number"], *checked)

    update_ledger(write, f"Record issue #{event['issue']['number']}")


def save_entrant_evidence(ledger, issue, package, data, inputs, report, origin):
    from audit.candidate import read_entry
    from delta_entry import envelope
    from entrant_proof import package_bytes
    from route_audit import subject_id
    from run import SEASON
    row, source = read_entry(ledger, issue)
    audit = envelope(row, inputs, report, int(os.environ["GITHUB_RUN_ID"]),
                     int(os.environ["GITHUB_RUN_ATTEMPT"]), os.environ["GITHUB_SHA"], entrant_proof=origin)
    path = ledger / SEASON / "deltas" / (subject_id(audit["subject"]) + ".json")
    for filename, payload in (("entrant-proof.json", package_bytes(package)), ("entrant.rhproof.gz", data)):
        asset = source.with_name(filename)
        if asset.exists() and asset.read_bytes() != payload:
            raise ValueError("A previously accepted entrant proof has changed")
        asset.write_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = json.loads(path.read_bytes())
        if any(package_bytes(previous.get(key)) != package_bytes(audit[key]) for key in ("subject", "report", "inputs")):
            raise ValueError("A previous certificate disagrees with the verified local witness")
        if previous.get("entrant_proof") == origin:
            return
    path.write_bytes(package_bytes(audit))


if __name__ == "__main__":
    publish(json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()), Path(sys.argv[1]))
