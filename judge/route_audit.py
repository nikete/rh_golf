"""Bind independent checker evidence to one measured, complete ordinary-RH proof."""
import hashlib
import json
from pathlib import Path
import re

from archive_portfolio import PORTFOLIO_VERIFIER, REFLECTION, ROOT, portfolio_nodes, replacement_for

POLICY = Path(__file__).resolve().parent / "audit/policy.json"
CHECKS = {"lean_kernel", "nanoda", "con_leche", "comparator", "con_leche_compare"}
AXIOMS = {"Classical.choice", "Quot.sound", "propext"}
TARGETS = {"reflection": REFLECTION, "riemann": ROOT}


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _hash(value):
    return isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value) is not None


def _positive(value):
    return type(value) is int and value > 0


def binding(row):
    _require(_hash(row.get("source_sha256")) and _hash(row.get("certificate_sha256")),
             "Missing immutable proof identity")
    result = {key: row[key] for key in ("hole", "source_sha256", "certificate_sha256")}
    if "issue" in row:
        result["issue"] = row["issue"]
    if row.get("verifier") == PORTFOLIO_VERIFIER:
        _require(_hash(row.get("portfolio_sha256")), "Missing manifest identity")
        result["portfolio_sha256"] = row["portfolio_sha256"]
    return result


def make_subject(rows, route, issue_ids, nodes, baseline, *, refs=None, course_reflection=False, graph=None):
    """Reconstruct a route and its exact cost. Only use rows from the immutable ledger."""
    from impact import footprint_size, validate_impact
    _require(_positive(nodes) and _hash(baseline.get("compressed_sha256")) and _hash(baseline.get("mathlib_inventory_sha256")),
             "Invalid baseline, inventory or node count")
    ids = list(issue_ids)
    _require(all(_positive(i) for i in ids) and len(set(ids)) == len(ids), "Invalid or duplicate route issue")
    by_issue = {row["issue"]: row for row in rows}
    _require(all(i in by_issue for i in ids), "Route includes a missing issue")
    selected = [by_issue[i] for i in sorted(ids)]
    target = lambda r: TARGETS.get(r["hole"], r["hole"])
    course = refs["reflection"] if course_reflection and refs else None
    _require(type(course_reflection) is bool and (not course_reflection or course is not None),
             "Missing course reflection reference")
    if course_reflection:
        _require(route in ("course-reflection", "archive-replacement"), "Unexpected course proof")
    if route == "archive-portfolio":
        _require(len(selected) == 1 and target(selected[0]) == ROOT, "Expected a single root portfolio")
        measured = portfolio_nodes(selected[0])
    elif route == "course-reflection":
        _require(not selected and course is not None, "Invalid course opening")
        measured = baseline["spine_nodes"] + footprint_size(course["impact"])
    elif route == "prime-pair":
        _require(len(selected) == 2 and {r["hole"] for r in selected} == {"prime-window", "prime-supply"},
                 "Both prime-route proofs are required")
        private, shared = 0, {}
        for row in selected:
            impact = row["impact"]
            validate_impact(impact)
            private += impact["private_nodes"]
            for name, weight in impact["shared"].items():
                _require(shared.setdefault(name, weight) == weight, "Shared prime-route cost disagrees")
        measured = baseline["composition_nodes"] + private + sum(shared.values())
    elif route == "archive-replacement":
        _require(selected and graph is not None and graph.baseline == baseline["archive_nodes"],
                 "An audited archive graph is required for combined edits")
        edits = {}
        if course:
            edits[graph.target(REFLECTION)] = replacement_for(graph, course)
        for row in selected:
            _require(row.get("verifier") != PORTFOLIO_VERIFIER and row["hole"] not in
                     ("window-logic", "prime-window", "prime-supply"), "Invalid component of an archive route")
            group = graph.target(target(row))
            _require(group not in edits, "Two edits select the same theorem")
            edits[group] = replacement_for(graph, row)
        measured, used = graph.measure(edits)
        _require(set(used) == set(edits), "A nominated route contributor is unreachable")
    else:
        _require(len(selected) == 1, "A standalone proof has one contributor")
        row = selected[0]
        _require(row.get("verifier") != PORTFOLIO_VERIFIER and row["hole"] not in
                 ("window-logic", "prime-window", "prime-supply"), "Incomplete standalone RH route")
        if route == "standalone-replacement" and _positive(row.get("standalone_rh_nodes")):
            measured = row["standalone_rh_nodes"]
        elif route in ("direct", "standalone-replacement") and target(row) == ROOT and not row.get("archive_deps"):
            validate_impact(row["impact"])
            measured = footprint_size(row["impact"])
        elif route in ("archive-reflection", "standalone-replacement") and target(row) == REFLECTION and not row.get("archive_deps"):
            validate_impact(row["impact"])
            measured = baseline["spine_nodes"] + footprint_size(row["impact"])
        else:
            raise ValueError("Unknown or unmeasured whole-proof route")
    _require(measured == nodes, "Route cost differs from the recorded measurement")
    return {"version": 1, "root": ROOT, "metric": baseline["metric"], "archive_sha256": baseline["compressed_sha256"],
            "mathlib_inventory_sha256": baseline["mathlib_inventory_sha256"],
            "route": route, "nodes": nodes, "entries": [binding(row) for row in selected],
            "course_reflection": binding(course) if course else None}


def subject_id(subject):
    encoded = json.dumps(subject, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_attestation(receipt, subject):
    """Validate a trusted audit job's evidence envelope. Never accept one from issue text."""
    _require(isinstance(receipt, dict) and type(receipt.get("schema")) is int and receipt["schema"] == 1
             and subject_id(receipt.get("subject")) == subject_id(subject), "Audit subject mismatch")
    solution = receipt.get("solution_sha256")
    _require(_hash(solution) and receipt.get("reproductions") == [solution, solution],
             "The two derivations must produce the same solution export")
    _require(receipt.get("measured_root") == subject["root"] == ROOT, "Recount targeted the wrong root")
    _require(_hash(subject.get("mathlib_inventory_sha256"))
             and receipt.get("mathlib_inventory_sha256") == subject["mathlib_inventory_sha256"],
             "Recount used a different Mathlib inventory")
    _require(_positive(receipt.get("measured_nodes")) and receipt["measured_nodes"] == subject["nodes"]
             and receipt.get("measured_export_sha256") == solution, "Independent export recount mismatch")
    _require(_positive(receipt.get("run")) and _positive(receipt.get("attempt"))
             and isinstance(receipt.get("commit"), str) and re.fullmatch("[a-f0-9]{40}", receipt["commit"]),
             "Missing audit CI run identity")
    policy_bytes = POLICY.read_bytes()
    policy = json.loads(policy_bytes)
    _require(set(policy["required_checks"]) == CHECKS and _hash(policy.get("challenge_sha256")),
             "Incomplete trusted checker policy")
    report = receipt.get("checker_receipt")
    _require(isinstance(report, dict) and type(report.get("schema")) is int and report["schema"] == 1
             and report.get("status") == "passed" and report.get("solution_sha256") == solution
             and set(policy["allowed_axioms"]) == AXIOMS and set(report.get("allowed_axioms", ())) == AXIOMS
             and report.get("challenge_sha256") == policy["challenge_sha256"]
             and report.get("policy_sha256") == hashlib.sha256(policy_bytes).hexdigest(),
             "Checker report does not match the pinned challenge, solution and policy")
    checks = report.get("checks")
    _require(isinstance(checks, dict) and CHECKS <= checks.keys(), "Missing independent check")
    for name in sorted(CHECKS):
        check = checks[name]
        version = policy["check_versions"][name]
        _require(isinstance(check, dict) and isinstance(version, str) and version
                 and check.get("status") == "passed" and type(check.get("exit_code")) is int
                 and check["exit_code"] == 0 and _hash(check.get("log_sha256"))
                 and check.get("tool_version") == version, f"Missing or unsuccessful check: {name}")
