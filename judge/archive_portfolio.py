"""Evaluate named, kernel-checked substitutions together in the ordinary RH proof."""
import re

from archive_graph import IncompatibleReplacements, Replacement

REFLECTION = "Formalism.VW.rh_of_right"
ROOT = "riemannHypothesis"
PORTFOLIO_VERIFIER = "pinned-export-exact-reuse-portfolio-v1"


def portfolio_nodes(row):
    """Read the full RH cost from a bulk verifier receipt for offline ledger replay."""
    from reuse.manifest import validate_url
    nodes = row.get("standalone_rh_nodes")
    coverage = row.get("portfolio_coverage")
    digest = row.get("portfolio_sha256")
    if (row.get("verifier") != PORTFOLIO_VERIFIER or type(nodes) is not int or nodes <= 0
            or not isinstance(digest, str) or not re.fullmatch("[a-f0-9]{64}", digest)
            or not isinstance(coverage, dict)
            or any(type(coverage.get(k)) is not int or coverage[k] < 0
                   for k in ("submitted", "reachable", "bypassed"))
            or coverage["submitted"] == 0
            or coverage["reachable"] + coverage["bypassed"] != coverage["submitted"]):
        raise ValueError("Malformed verified RH portfolio receipt")
    validate_url(row.get("portfolio_url"))
    return nodes


def replacement_for(graph, row):
    impact = row["impact"]
    deps = tuple(sorted({graph.lookup(name) for name in row.get("archive_deps", ())}))
    return Replacement(impact["private_nodes"], impact["shared"], deps)


class ArchiveRecord:
    def __init__(self, graph, reference, baseline):
        self.graph = graph
        self.entries = {}  # All earlier accepted archive substitutions, including zero-credit entries.
        self.last_bundle_warning = None
        if graph.baseline != baseline["archive_nodes"]:
            raise ValueError("Graph disagrees with the archived ordinary RH baseline")
        reflection = graph.target(REFLECTION)
        self.opening = {reflection: (0, replacement_for(graph, {"impact": reference}))}
        self.nodes, _ = graph.measure({reflection: self.opening[reflection][1]})
        expected = baseline["spine_nodes"] + reference["private_nodes"] + sum(reference["shared"].values())
        if self.nodes != expected:
            raise ValueError("Graph disagrees with the opening reflection measurement")
        self.edits = self.opening if self.nodes < graph.baseline else {}
        self.nodes = min(graph.baseline, self.nodes)

    def _nominated(self, row, target):
        requested = row.get("combine", [])
        if not isinstance(requested, list):
            raise ValueError("combine must be a list of earlier issue numbers")
        result = {}
        for issue in requested:
            if type(issue) is not int or issue <= 0 or issue >= row["issue"] or issue not in self.entries:
                raise ValueError(f"Unknown, unaccepted or later archive replacement #{issue}")
            group, proof = self.entries[issue]
            if group == target or group in result:
                raise ValueError("Nominated replacements must have distinct archive targets")
            result[group] = (issue, proof)
        return result

    def consider(self, row, target):
        """Return (complete cost, used issues, newly contributing issues) for a record."""
        self.last_bundle_warning = None
        gid = self.graph.target(target)
        issue = row["issue"]
        patch = replacement_for(self.graph, row)
        if type(issue) is not int or issue <= 0 or issue in self.entries:
            raise ValueError("Invalid or duplicate archive issue number")
        new = {gid: (issue, patch)}
        cache = {}

        def measure(edits):
            # Several search paths can describe the same portfolio. Do not rerun
            # a large archive traversal for each equivalent candidate.
            signature = tuple(sorted((g, i) for g, (i, _) in edits.items()))
            if signature not in cache:
                cost, used = self.graph.measure({g: p for g, (_, p) in edits.items()})
                cache[signature] = cost, {g: edits[g] for g in used}
            return cache[signature]

        # A broken nomination does not invalidate the standalone proof.
        measure(new)
        try:
            nominated = self._nominated(row, gid)
        except ValueError as error:
            self.last_bundle_warning = str(error)
            nominated = {}
        if nominated:
            try:
                measure(nominated | new)
            except IncompatibleReplacements as error:
                self.last_bundle_warning = str(error)
                nominated = {}
        best = None

        def maybe_measure(edits):
            try:
                return measure(edits)
            except IncompatibleReplacements:
                return None

        def remove_redundant(cost, live):
            # Prefer the incumbent to an interchangeable new copy. Removing a
            # replacement can make more substitutions unreachable; always use
            # the exact graph result of the trial.
            while True:
                before = live
                for group in sorted(before, key=lambda g: before[g][0], reverse=True):
                    if group not in live:
                        continue
                    stripped = {g: item for g, item in live.items() if g != group}
                    trial = maybe_measure(stripped)
                    if trial is not None and trial[0] <= cost:
                        cost, live = trial
                        continue
                    old = self.edits.get(group)
                    if old is not None and old != live[group]:
                        trial = maybe_measure(stripped | {group: old})
                        if trial is not None and trial[0] <= cost:
                            cost, live = trial
                if live == before:
                    return cost, live

        comparison_bases = (self.edits, self.opening, {})
        additions = [nominated] if nominated else [{}]
        # Earlier individually unprofitable edits can remove shared dependencies
        # together. Automatically try each one; larger sets can be named explicitly.
        additions.extend({g: (i, proof)} for i, (g, proof) in self.entries.items()
                         if g != gid)
        if nominated:
            additions.append({})
        for extras in additions:
            for base in comparison_bases:
                trial = maybe_measure(base | extras | new)
                if trial is None or trial[0] >= self.nodes:
                    continue
                cost, live = remove_redundant(*trial)
                issues = tuple(sorted(i for i, _ in live.values() if i))
                # Ties prefer a smaller witness, then the oldest contributors.
                key = (cost, len(issues), issues)
                if best is None or key < best[0]:
                    best = key, live
        self.entries[issue] = gid, patch
        if best is None:
            return None
        (cost, _, issues), live = best
        incumbent = {i for i, _ in self.edits.values() if i}
        newcomers = tuple(i for i in issues if i not in incumbent)
        self.nodes, self.edits = cost, live
        return cost, issues, (newcomers or issues)
