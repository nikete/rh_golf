"""Resolve an immutable tournament entry and materialize its complete proof for an audit."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "judge"))
from archive_portfolio import PORTFOLIO_VERIFIER, REFLECTION
from board import historic_measurements, read_ledger_row
from impact import footprint_size
from reuse import METHOD as SINGLE_REUSE
from reuse.manifest import fetch_pairs
from route_audit import make_subject, subject_id
from run import PORTFOLIO, REUSE, SEASON, directives, validate_source

BASELINE = json.loads((ROOT / "judge/baseline.json").read_text())


def read_entry(ledger, issue):
    if type(issue) is not int or issue < 1:
        raise ValueError("Expected a positive issue number")
    folder = ledger / SEASON / str(issue)
    row = read_ledger_row(folder / "score.json", historic_measurements())
    if row["issue"] != issue or hashlib.sha256((folder / "Entry.lean").read_bytes()).hexdigest() != row["source_sha256"]:
        raise ValueError("Immutable entry identity mismatch")
    return row, folder / "Entry.lean"


def route(row):
    if row.get("verifier") == PORTFOLIO_VERIFIER:
        return "portfolio", "archive-portfolio", row["standalone_rh_nodes"]
    if row.get("verifier") == SINGLE_REUSE:
        return "reuse", "standalone-replacement", row["standalone_rh_nodes"]
    if row["hole"] in ("riemannHypothesis", "riemann"):
        if "standalone_rh_nodes" not in row and "impact" not in row:
            return None
        size = row["standalone_rh_nodes"] if "standalone_rh_nodes" in row else footprint_size(row["impact"])
        return "root-lean", "standalone-replacement", size
    if row.get("standalone_rh_nodes") and row["hole"] not in ("prime-window", "prime-supply", "window-logic"):
        return "named-lean", "standalone-replacement", row["standalone_rh_nodes"]
    if row["hole"] in ("reflection", REFLECTION) and "impact" in row:
        return "named-lean", "standalone-replacement", BASELINE["spine_nodes"] + footprint_size(row["impact"])
    return None


def best_standalone(ledger):
    choices = []
    for path in (ledger / SEASON).glob("*/score.json"):
        issue = int(path.parent.name)
        row, _ = read_entry(ledger, issue)
        proposal = route(row)
        if proposal and proposal[2] < BASELINE["archive_nodes"]:
            choices.append((proposal[2], issue))
    return min(choices)[1] if choices else None


def select(ledger, issue, originating_run):
    if not issue:
        matches = [p for p in (ledger / SEASON).glob("*/score.json")
                   if json.loads(p.read_text())["run"] == originating_run]
        if not matches:
            return None
        if len(matches) != 1:
            raise ValueError("The judge run does not identify a unique receipt")
        issue = int(matches[0].parent.name)
    row, _ = read_entry(ledger, issue)
    kind = route(row)
    if kind is None:
        return {"issue": issue, "state": "pending", "reason": "This route requires a complete linked export."}
    method, name, size = kind
    subject = make_subject([row], name, [issue], size, BASELINE)
    return {"issue": issue, "method": method, "state": "ready", "subject": subject,
            "hosted": method == "root-lean" and not row.get("archive_module"),
            "subject_id": subject_id(subject)}


def reuse_arguments(row, source, work):
    nominations, body = directives(validate_source(source.read_text(encoding="utf-8")))
    if nominations != row.get("combine", []):
        raise ValueError("The frozen nomination differs from the receipt")
    if row["verifier"] == SINGLE_REUSE:
        match = REUSE.fullmatch(body)
        if not match or match[1].strip() != row["reuse_donor"]:
            raise ValueError("The frozen instruction and recorded donor differ")
        return ["--target", row["hole"], "--donor", match[1].strip()]
    match = PORTFOLIO.fullmatch(body)
    if (not match or nominations or row["hole"] != "riemannHypothesis" or row["verifier"] != PORTFOLIO_VERIFIER
            or match.groups() != (row["portfolio_url"], row["portfolio_sha256"])):
        raise ValueError("The frozen instruction and recorded portfolio differ")
    # fetch_pairs verifies the submitted compressed bytes and line format once.
    manifest = work / "pairs.jsonl.gz"
    with gzip.open(manifest, "wt", encoding="utf-8") as out:
        for pair in fetch_pairs(*match.groups()):
            out.write(json.dumps(pair, ensure_ascii=False, separators=(",", ":")) + "\n")
    return ["--manifest", str(manifest)]


def check_rewrite(row, report, solution_hash):
    if (report["certificate_sha256"] != row["certificate_sha256"]
            or type(report["expected_nodes"]) is not int or report["expected_nodes"] != row["standalone_rh_nodes"]
            or report["candidate_sha256"] != solution_hash or report["original_sha256"] != BASELINE["unpacked_sha256"]
            or row["verifier"] == PORTFOLIO_VERIFIER and report["coverage"] != row["portfolio_coverage"]):
        raise ValueError("The regenerated exact-reuse proof differs from the frozen receipt")


def materialize(ledger, issue, work):
    row, source = read_entry(ledger, issue)
    selected = select(ledger, issue, None)
    if selected["state"] != "ready":
        raise ValueError(selected["reason"])
    solution = work / "solution.ndjson"
    method = selected["method"]
    if method in ("root-lean", "named-lean"):
        cert = work / "certificate.json"
        replay = work / "replay.json"
        subprocess.run([sys.executable, "judge/run.py", "--target", row["hole"], "--source", str(source),
                        "--certificate-output", str(cert), "--output", str(replay)], check=True)
        receipt = json.loads(replay.read_text())
        if any(row[key] != receipt[key] for key in ("source_sha256", "certificate_sha256")):
            raise ValueError("The replay did not reproduce this entry's frozen certificate")
        program = "judge/export_candidate.py" if method == "root-lean" else "judge/audit/source_build.py"
        args = [sys.executable, program, "--target", row["hole"], "--source", str(source),
                "--certificate", str(cert), "--receipt", str(replay), "--output", str(solution)]
        if method == "root-lean":
            # This diagnostic reference is never used as the independent challenge.
            args.extend(["--challenge", str(work / "local-reference.ndjson"),
                         "--max-export-bytes", str(256 << 30), "--timeout-seconds", "64800"])
        subprocess.run(args, check=True)
    else:
        instruction = reuse_arguments(row, source, work)
        archive = work / "original.ndjson.zst"
        subprocess.run(["curl", "-fsSL", "--retry", "3", "--output", str(archive), BASELINE["export_url"]], check=True)
        args = [sys.executable, "judge/audit/rewrite.py", "--input", str(archive), "--output", str(solution),
                "--graph", str(ROOT / ".out/archive-graph"), *instruction]
        subprocess.run([sys.executable, "judge/fetch_graph.py"], check=True)
        rewrite_report = json.loads(subprocess.check_output(args, text=True))
        archive.unlink()
    with solution.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    if method in ("portfolio", "reuse"):
        check_rewrite(row, rewrite_report, digest)
    record = {"subject": selected["subject"], "solution_sha256": digest}
    (work / "build.json").write_text(json.dumps(record) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("select", "build"))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--issue", type=int)
    parser.add_argument("--run", type=int)
    parser.add_argument("--best", action="store_true")
    parser.add_argument("--work", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        materialize(args.ledger.resolve(), args.issue, args.work.resolve())
        return
    issue = best_standalone(args.ledger) if args.best else args.issue
    result = select(args.ledger, issue, args.run) if issue or args.run else None
    print(json.dumps(result, indent=2))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as out:
            print("state=" + (result["state"] if result else "no-entry"), file=out)
            if result:
                print(f"issue={result['issue']}", file=out)
                print(f"method={result.get('method', '')}", file=out)
                print("hosted=" + str(result.get("hosted", False)).lower(), file=out)


if __name__ == "__main__":
    main()
