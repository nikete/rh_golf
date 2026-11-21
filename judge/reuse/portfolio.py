"""Verify a simultaneous set of exact theorem aliases against the pinned RH export."""
import hashlib
import json

from archive_graph import Replacement
from . import signature_index

METHOD = "pinned-export-exact-reuse-portfolio-v1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def verify_portfolio(pairs, graph):
    """Validate named target/donor pairs and score their joint whole-proof closure.

    Archive donors resolve to positive group IDs. Library donors retain their exact
    name components. The witness order comes from the pinned theorem index, so
    reordering or re-encoding a submission produces the same proof certificate.
    """
    requested = {}
    for number, pair in enumerate(pairs, 1):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(f"Expected a target/donor pair on manifest line {number}")
        target, donor = pair
        target_id = graph.target(target)
        if target_id in requested:
            raise ValueError(f"Duplicate target on manifest line {number}")
        key = canonical(graph.name_parts(donor))
        donor_id = graph.names.get(key)
        if donor_id == target_id:
            raise ValueError(f"A theorem cannot reuse itself on manifest line {number}")
        requested[target_id] = key if donor_id is None else donor_id
    if not requested:
        raise ValueError("A portfolio requires at least one theorem pair")

    pin, header, signatures = signature_index()
    digest = hashlib.sha256()
    digest.update(canonical([METHOD, header["export"], pin["sha256"]]) + b"\n")
    patches = {}
    for _, _, nodes, deps, theorems, library in signatures:
        targets = [group for group in theorems if group in requested]
        if not targets:
            continue
        members = set(theorems)
        library_names = {canonical(name) for name in library}
        for group in targets:
            donor = requested.pop(group)
            if isinstance(donor, int) and donor in members:
                # A dependency group may contain multiple declarations. Charge
                # the group once even if it also occurs in the statement.
                boundary = tuple(sorted({*deps, donor}))
                witness_donor = donor
            elif isinstance(donor, bytes) and donor in library_names:
                boundary = tuple(deps)
                witness_donor = json.loads(donor)
            else:
                raise ValueError(f"Donor does not share target group {group}'s exact exported signature")
            patches[group] = Replacement(nodes + 1, {}, boundary)
            digest.update(canonical([group, witness_donor]) + b"\n")
        if not requested:
            break
    if requested:
        raise ValueError(f"Target group {next(iter(requested))} has no matching exported theorem signature")

    # Visit the RH closure once, then check unvisited edited components for
    # cycles. An unreachable cyclic proof is still an invalid submission.
    cost, live = graph._full_measure(patches, {})
    count = len(patches)
    return {"replacements": patches, "live_groups": live, "standalone_rh_nodes": cost,
            "verifier": METHOD, "certificate_sha256": digest.hexdigest(),
            "coverage": {"submitted": count, "reachable": len(live), "bypassed": count - len(live)}}
