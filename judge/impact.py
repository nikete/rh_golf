"""Historical attribution of verified reductions in a complete proof of ordinary RH."""
from collections import defaultdict
from dataclasses import dataclass


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


def score_project(rows, refs, baseline):
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

    winner = start
    history = []
    credit = defaultdict(int)
    pending = []
    halves = {"prime-window": {}, "prime-supply": {}}
    for row in sorted(rows, key=lambda r: r["issue"]):
        issue, hole = row["issue"], row["hole"]
        measurement = row.get("impact")
        if hole == "window-logic":
            continue
        if measurement is None:
            pending.append(issue)
            continue
        check(measurement)
        size = footprint_size(measurement)
        if hole == "reflection":
            candidate = Route("archive-reflection", spine + size, (issue,))
        elif hole == "riemann":
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
        beneficiaries = [i for i in candidate.entries if i not in winner.entries]
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
        "reflection_headroom_nodes": max(0, winner.nodes - spine),
        "winning_route": winner.kind,
        "winning_issues": winner.entries, "history": history, "pending_issues": pending,
    }, dict(credit)


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
