"""Exact, composable replacements in the pinned ordinary RH dependency graph."""
from array import array
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys


@dataclass(frozen=True)
class Replacement:
    private_nodes: int
    shared: dict = field(default_factory=dict)
    dependencies: tuple = ()


class IncompatibleReplacements(ValueError):
    """Standalone substitutions cannot be installed together."""


def _words(path):
    data = array("I")
    with path.open("rb") as f:
        size = path.stat().st_size
        if data.itemsize != 4 or size % 4:
            raise ValueError("Malformed archive graph array")
        data.fromfile(f, size // 4)
    if sys.byteorder != "little":
        data.byteswap()
    return data


def _components(name):
    if isinstance(name, (list, tuple)):
        if not name or any(not (type(p) is str or type(p) is int and p >= 0) for p in name):
            raise ValueError("Invalid Lean name components")
        return name
    if not isinstance(name, str) or not name:
        raise ValueError("Missing Lean name")
    # Quoted components can contain periods, and distinguish «10» from the
    # numeric component 10. Certificates can pass exact component arrays.
    parts = []
    pos = 0
    while True:
        if pos >= len(name):
            raise ValueError("Empty unquoted Lean name component")
        quoted = name[pos] == "«"
        if quoted:
            end = name.find("»", pos + 1)
            if end < 0:
                raise ValueError("Unclosed Lean name escape")
            piece = name[pos+1:end]
            pos = end+1
        else:
            end = name.find(".", pos)
            if end < 0:
                end = len(name)
            piece = name[pos:end]
            if not piece:
                raise ValueError("Empty unquoted Lean name component")
            pos = end
        parts.append(int(piece) if not quoted and piece.isascii() and piece.isdecimal() else piece)
        if pos == len(name):
            return parts
        if name[pos] != ".":
            raise ValueError("Expected a Lean namespace separator")
        pos += 1


class ArchiveGraph:
    def __init__(self, folder):
        folder = Path(folder)
        manifest = json.loads((folder / "manifest.json").read_text())
        if manifest.get("version") != 1 or manifest.get("metric") != "rh-declaration-nodes-v1":
            raise ValueError("Unknown RH graph format")
        self.nodes = _words(folder / "groups.bin")
        self.edges = _words(folder / "dependencies.bin")
        self.root = manifest["root"]
        self.baseline = manifest["baseline"]
        self.count = len(self.nodes) // 4
        if len(self.nodes) % 4 or not 0 < self.root < self.count:
            raise ValueError("Invalid RH graph header")
        self.names = {}
        self.replaceable = bytearray(self.count)
        with (folder / "names.tsv").open("rb") as f:
            for line in f:
                group, kind, name = line.rstrip(b"\n").split(b"\t", 2)
                group = int(group)
                self.names[name] = group
                if kind in (b"thm", b"def", b"opaque"):
                    self.replaceable[group] = 1

    @staticmethod
    def name_parts(name):
        """Exact components of the Lean target for the replay checker."""
        return _components(name)

    def lookup(self, name):
        key = json.dumps(_components(name), ensure_ascii=False, separators=(",", ":")).encode()
        if key not in self.names:
            raise ValueError(f"Unknown non-Mathlib archive declaration {name!r}")
        return self.names[key]

    def target(self, name):
        group = self.lookup(name)
        if not self.replaceable[group]:
            raise ValueError("The archive declaration is not individually replaceable")
        return group

    def _original(self, group):
        offset = self.nodes[group*4+1]
        count = self.nodes[group*4+2]
        return self.edges[offset:offset+count]

    def measure(self, replacements):
        """Return (complete cost, reachable replacement IDs). Cyclic entries are invalid."""
        if not replacements:
            return self.baseline, frozenset()
        first_forward = self.count
        shared = {}
        for group, proof in replacements.items():
            if type(group) is not int or not 0 < group < self.count or not self.replaceable[group]:
                raise ValueError("Unsupported archive substitution group")
            if type(proof.private_nodes) is not int or proof.private_nodes <= 0:
                raise ValueError("Invalid replacement footprint")
            for name, weight in proof.shared.items():
                if type(weight) is not int or weight <= 0:
                    raise ValueError("Invalid shared declaration cost")
                if shared.setdefault(name, weight) != weight:
                    raise IncompatibleReplacements("Inconsistent shared declaration cost")
            for dep in proof.dependencies:
                if type(dep) is not int or not 0 < dep < self.count:
                    raise ValueError("Unknown archive dependency")
                if dep >= group:
                    first_forward = min(group, first_forward)
        if first_forward < self.count:
            self._check_cycles(replacements, first_forward)
        if self.root in replacements:
            # The full archive can drop away through a small standalone root.
            return self._full_measure(replacements, shared, only_root=True)

        # Install the new edges of initially live substitutions, then remove
        # their superseded edges. Reachability can only grow during the first
        # pass and only shrink in the second. On a DAG every unreachable node
        # eventually loses its last reference, including shared descendants.
        used = {g for g in replacements if self.nodes[g*4+3]}
        cost = self.baseline
        added, removed = [], []
        for group in used:
            proof = replacements[group]
            cost += proof.private_nodes - self.nodes[group*4]
            original = set(self._original(group))
            new = set(proof.dependencies)
            added.extend(new - original)
            removed.extend(original - new)

        references = {}
        for pending, sign in ((added, 1), (removed, -1)):
            while pending:
                group = pending.pop()
                old = references.get(group, self.nodes[group*4+3])
                count = old + sign
                references[group] = count
                if count < 0:
                    raise ValueError("Negative archive reference count")
                if old and count:
                    continue
                proof = replacements.get(group)
                if proof is None:
                    cost += sign * self.nodes[group*4]
                    pending.extend(self._original(group))
                else:
                    cost += sign * proof.private_nodes
                    if count:
                        used.add(group)
                    else:
                        used.remove(group)
                    pending.extend(set(proof.dependencies))
        shared_names = {name for g in used for name in replacements[g].shared}
        return cost + sum(shared[n] for n in shared_names), frozenset(used)

    def _check_cycles(self, replacements, first_forward):
        # Every cycle includes a forward arc from a replacement. Below the
        # earliest such replacement all edges point backwards, so an original
        # subtree below that cutoff cannot lead back to an active ancestor.
        state = bytearray(self.count)
        starts = (g for g, p in replacements.items() if any(d >= g for d in p.dependencies))
        for start in starts:
            stack = [start]
            while stack:
                group = stack.pop()
                if group < 0:
                    state[-group] = 2
                    continue
                if state[group] == 2:
                    continue
                if state[group] == 1:
                    raise IncompatibleReplacements("Cyclic archive replacement")
                state[group] = 1
                stack.append(-group)
                proof = replacements.get(group)
                deps = self._original(group) if proof is None else proof.dependencies
                stack.extend(d for d in deps if d >= first_forward)

    def _full_measure(self, replacements, shared, only_root=False):
        # Direct traversal is cheap when the replacement for the root is small.
        state = bytearray(self.count)
        cost = 0
        used, shared_names = set(), set()
        for start in ((self.root,) if only_root else (self.root, *replacements)):
            bill = start == self.root
            stack = [start]
            while stack:
                group = stack.pop()
                if group < 0:
                    state[-group] = 2
                    continue
                if state[group] == 2:
                    continue
                if state[group] == 1:
                    raise IncompatibleReplacements("Cyclic archive replacement")
                state[group] = 1
                stack.append(-group)
                proof = replacements.get(group)
                if proof is None:
                    stack.extend(self._original(group))
                    if bill:
                        cost += self.nodes[group*4]
                else:
                    stack.extend(set(proof.dependencies))
                    if bill:
                        cost += proof.private_nodes
                        used.add(group)
                        shared_names.update(proof.shared)
        return cost + sum(shared[n] for n in shared_names), frozenset(used)
