"""Historical attribution of verified reductions in a complete proof of ordinary RH."""
from collections import defaultdict
from dataclasses import dataclass
from archive_portfolio import ArchiveRecord, PORTFOLIO_VERIFIER, portfolio_nodes


def validate_impact(value):
    def positive(n):
        return type(n) is int and n > 0
    if (not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1
            or not positive(value.get("private_nodes")) or not isinstance(value.get("shared"), dict)
            or any(not isinstance(k, str) or not k or not positive(v) for k, v in value["shared"].items())):
        raise ValueError("Malformed whole-proof measurement")


def footprint_size(impact):
    return impact["private_nodes"] + sum(impact["shared"].values())


@dataclass(frozen=True)
class Route:
    kind: str
    nodes: int
    entries: tuple = ()


def provisional_project(rows, refs, baseline, graph=None):
    archive = baseline["archive_nodes"]
    spine = baseline["spine_nodes"]
    if not 0 < spine < archive:
        raise ValueError("Invalid RH baseline")
    start = Route("archive", archive)
    shared_costs = {}

    def check(measure):
        validate_impact(measure)
        for name, weight in measure["shared"].items():
            if shared_costs.setdefault(name, weight) != weight:
                raise ValueError(f"Inconsistent pinned declaration weight for {name}")

    reference = refs["reflection"]["impact"]
    check(reference)
    reference_size = spine + footprint_size(reference)
    if reference_size < start.nodes:
        start = Route("course-reflection", reference_size)

    archive_record = None
    winner = start
    history = []
    credit = defaultdict(int)
    pending = []
    bundle_warnings = {}
    halves = {"prime-window": {}, "prime-supply": {}}
    for row in sorted(rows, key=lambda r: r["issue"]):
        issue, hole = row["issue"], row["hole"]
        kind = {"Formalism.VW.rh_of_right": "reflection", "riemannHypothesis": "riemann"}.get(hole, hole)
        bulk = row.get("verifier") == PORTFOLIO_VERIFIER
        if not bulk:
            if kind == "window-logic":
                continue
            measurement = row.get("impact")
            if measurement is None:
                pending.append(issue)
                continue
            check(measurement)
            size = footprint_size(measurement)
        if bulk:
            candidate = Route("archive-portfolio", portfolio_nodes(row), (issue,))
        elif graph is not None and ("archive_deps" in row or kind in ("reflection", "riemann")):
            if archive_record is None:
                archive_record = ArchiveRecord(graph, reference, baseline)
            target = {"reflection": "Formalism.VW.rh_of_right", "riemann": "riemannHypothesis"}.get(hole, hole)
            record = archive_record.consider(row, target)
            if archive_record.last_bundle_warning:
                bundle_warnings[issue] = archive_record.last_bundle_warning
            if record is None:
                continue
            size, entries, _ = record
            candidate = Route("archive-replacement", size, entries)
        elif kind == "reflection":
            candidate = Route("archive-reflection", spine + size, (issue,))
        elif kind == "riemann":
            candidate = Route("direct", size, (issue,))
        elif hole in halves:
            # For the same set of shared course declarations, the cheapest private
            # implementation dominates in every possible pairing.
            signature = tuple(sorted(measurement["shared"]))
            existing = halves[hole].get(signature)
            if existing and existing["impact"]["private_nodes"] <= measurement["private_nodes"]:
                continue
            halves[hole][signature] = row
            opposite = "prime-window" if hole == "prime-supply" else "prime-supply"
            pairs = []
            for partner in halves[opposite].values():
                other = partner["impact"]
                union = measurement["shared"] | other["shared"]
                total = (baseline["composition_nodes"] + measurement["private_nodes"]
                         + other["private_nodes"] + sum(union.values()))
                entries = tuple(sorted((issue, partner["issue"])))
                pairs.append(Route("prime-pair", total, entries))
            if not pairs:
                continue
            candidate = min(pairs, key=lambda route: (route.nodes, route.entries))
        else:
            raise ValueError(f"Unknown score target {hole}")
        if candidate.nodes >= winner.nodes:
            continue
        gain = winner.nodes - candidate.nodes
        # On an initial two-part shortcut the contributors split the gain. When
        # a winning pair keeps its partner only the newly used entry earns credit.
        beneficiaries = ([i for i in candidate.entries if i not in winner.entries]
                         if candidate.kind in ("prime-pair", "archive-replacement") else [issue])
        if not beneficiaries:
            beneficiaries = list(candidate.entries) or [issue]
        quotient, remainder = divmod(gain, len(beneficiaries))
        awards = {i: quotient + int(k < remainder) for k, i in enumerate(beneficiaries)}
        for i, award in awards.items():
            credit[i] += award
        history.append({"issue": issue, "route": candidate.kind, "entries": candidate.entries,
                        "before_nodes": winner.nodes, "after_nodes": candidate.nodes,
                        "saved_nodes": gain, "credits": awards})
        winner = candidate
    community = start.nodes - winner.nodes
    if sum(credit.values()) != community:
        raise AssertionError("Whole-proof credits must equal the community reduction")
    return {
        "metric": "rh-declaration-nodes-v1", "root": "riemannHypothesis",
        "archive_nodes": archive, "starting_nodes": start.nodes, "current_nodes": winner.nodes,
        "saved_nodes": archive - winner.nodes, "course_saved_nodes": archive - start.nodes,
        "community_saved_nodes": community,
        "reflection_headroom_nodes": max(0, winner.nodes - spine) if archive_record is None else None,
        "winning_route": winner.kind, "bundle_warnings": bundle_warnings,
        "winning_issues": winner.entries, "history": history, "pending_issues": pending,
    }, dict(credit)


def score_project(rows, refs, baseline, graph=None, *, audit_dir=None):
    """Replay only independently checked complete routes in entry-number order."""
    import hashlib
    import json
    from route_audit import make_subject, subject_id, validate_attestation
    audits, errors = [], {}
    for path in sorted(audit_dir.glob("*.json")) if audit_dir else ():
        try:
            evidence = json.loads(path.read_text())
            declared = evidence["subject"]
            issues = [r["issue"] for r in declared["entries"]]
            actual = make_subject(rows, declared["route"], issues, declared["nodes"], baseline, refs=refs,
                                  course_reflection=declared["course_reflection"] is not None, graph=graph)
            for entry in actual["entries"]:
                source = audit_dir.parent / str(entry["issue"]) / "Entry.lean"
                if hashlib.sha256(source.read_bytes()).hexdigest() != entry["source_sha256"]:
                    raise ValueError("Submitted ledger source differs from its audited digest")
            key = subject_id(actual)
            if path.name != key + ".json":
                raise ValueError("Wrong subject filename")
            validate_attestation(evidence, actual)
            audits.append({"subject_id": key, "route": actual["route"], "nodes": actual["nodes"],
                           "entries": tuple(sorted(issues)), "course_reflection": actual["course_reflection"] is not None,
                           "run": evidence["run"], "attempt": evidence["attempt"],
                           "solution_sha256": evidence["solution_sha256"]})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            # A broken or stale sidecar cannot award points or hide good receipts.
            errors[path.name] = str(exc)

    archive = start = current = baseline["archive_nodes"]
    winner = Route("archive", archive)
    history, credits = [], defaultdict(int)
    # Audit arrival order cannot change attribution. At each issue use the
    # smallest certified complete route which its participants made available.
    audits.sort(key=lambda a: (max(a["entries"], default=0), a["nodes"], a["entries"], a["subject_id"]))
    for audit in audits:
        entries = audit["entries"]
        cost = audit["nodes"]
        if cost >= current:
            continue
        if not entries:
            start = current = cost
            winner = Route("course-reflection", cost)
            continue
        beneficiaries = [i for i in entries if i not in winner.entries] or list(entries)
        gain = current - cost
        quotient, remainder = divmod(gain, len(beneficiaries))
        awards = {i: quotient + int(k < remainder) for k, i in enumerate(beneficiaries)}
        for i, award in awards.items():
            credits[i] += award
        history.append({"issue": max(entries), "route": audit["route"], "entries": entries,
                        "before_nodes": current, "after_nodes": cost, "saved_nodes": gain,
                        "credits": awards, "audit_subject": audit["subject_id"]})
        winner, current = Route(audit["route"], cost, entries), cost
    covered = {i for audit in audits for i in audit["entries"]}
    return {"metric": baseline.get("metric", "rh-declaration-nodes-v1"), "root": "riemannHypothesis",
            "archive_nodes": archive, "starting_nodes": start, "current_nodes": current,
            "saved_nodes": archive - current, "course_saved_nodes": archive - start,
            "community_saved_nodes": start - current, "winning_route": winner.kind,
            "winning_issues": winner.entries, "history": history, "audits": audits, "invalid_audits": errors,
            "pending_issues": sorted(r["issue"] for r in rows if r["issue"] not in covered)}, dict(credits)


def attach_measurements(rows, backfills):
    result = []
    for row in rows:
        saved = backfills.get(str(row["issue"]))
        if saved:
            if any(saved[k] != row[k] for k in ("source_sha256", "certificate_sha256", "hole")):
                raise ValueError("Historic footprint and immutable receipt differ")
            if "impact" in row and row["impact"] != saved["impact"]:
                raise ValueError("Historic and new whole-proof measurements differ")
            row = {**row, "impact": saved["impact"]}
        result.append(row)
    return result
