import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
import reuse
from archive_graph import ArchiveGraph


class ReuseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name) / "reuse"
        self.folder.mkdir()
        scope = patch.object(reuse, "HERE", self.folder)
        scope.start()
        self.addCleanup(scope.stop)
        graph = self.graph = ArchiveGraph.__new__(ArchiveGraph)
        graph.root, graph.count, graph.baseline = 4, 5, 41
        graph.nodes = [0, 0, 0, 0, 4, 0, 0, 1, 6, 0, 0, 1, 30, 0, 1, 1, 1, 1, 2, 1]
        graph.edges = [1, 2, 3]
        graph.replaceable = [False, True, True, True, True]
        graph.names = {json.dumps([name]).encode(): i for i, name in enumerate(["", "Ty", "Donor", "Target", "Root"])}
        header = {"format": 1, "export": "archive-digest", "axioms": reuse.AXIOMS}
        rows = [header, [17, [85], 2, [1], [2, 3, 4], [["Mathlib", "a.b"]]]]
        payload = b"".join((json.dumps(r) + "\n").encode() for r in rows)
        self.asset = self.folder / "signatures.jsonl.gz"
        self.asset.write_bytes(gzip.compress(payload))
        pin = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "export_sha256": "archive-digest"}
        (self.folder / "index.lock.json").write_text(json.dumps(pin))
        (self.folder.parent / "baseline.json").write_text(json.dumps({"compressed_sha256": "archive-digest"}))

    def verify(self, target, donor):
        return reuse.verify_reuse(target, donor, self.graph, "reuse " + donor + "\n")

    def test_archive_and_library_donors(self):
        archive = self.verify("Target", "Donor")
        self.assertEqual(archive["nodes"], 3)
        self.assertEqual(archive["standalone_rh_nodes"], 14)
        self.assertEqual(archive["archive_deps"], [["Ty"], ["Donor"]])
        self.assertEqual(archive["axioms_scope"], "pinned-export-upper-bound")
        library = self.verify("Target", "Mathlib.«a.b»")
        self.assertEqual(library["archive_deps"], [["Ty"]])
        self.assertNotEqual(library["certificate_sha256"], archive["certificate_sha256"])

    def test_unlisted_and_cyclic_reuse(self):
        for target, donor in [("Donor", "Donor"), ("Target", "Root"), ("Target", "Mathlib.a.b"), ("Ty", "Target")]:
            with self.subTest(target=target, donor=donor), self.assertRaises(ValueError):
                self.verify(target, donor)

    def test_tampering(self):
        self.asset.write_bytes(gzip.compress(b"changed"))
        with self.assertRaisesRegex(RuntimeError, "pinned digest"):
            self.verify("Target", "Donor")

    def test_portfolio_certificate_is_independent_of_manifest_order(self):
        from reuse.portfolio import verify_portfolio
        pairs = [("Target", "Donor"), ("Donor", "Mathlib.«a.b»")]
        results = verify_portfolio(pairs, self.graph)
        other = verify_portfolio([(["Donor"], ["Mathlib", "a.b"]), (["Target"], ["Donor"])], self.graph)
        self.assertEqual(results, other)
        self.assertEqual(results["standalone_rh_nodes"], 11)
        self.assertEqual(results["coverage"], {"submitted": 2, "reachable": 2, "bypassed": 0})
        solo = verify_portfolio([("Target", "Donor")], self.graph)
        self.assertEqual(solo["standalone_rh_nodes"], self.verify("Target", "Donor")["standalone_rh_nodes"])
        self.assertNotEqual(solo["certificate_sha256"], results["certificate_sha256"])

    def test_portfolio_checks_bypassed_entries(self):
        from reuse.portfolio import verify_portfolio
        score = verify_portfolio([("Root", "Mathlib.«a.b»"), ("Target", "Donor")], self.graph)
        self.assertEqual(score["live_groups"], frozenset({4}))
        self.assertEqual(score["coverage"], {"submitted": 2, "reachable": 1, "bypassed": 1})
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            verify_portfolio([("Root", "Mathlib.«a.b»"), ("Target", "Donor"), ("Donor", "Target")], self.graph)
        # One forward reference would be cyclic on its own. The simultaneous
        # replacement of Root makes both declarations well-founded.
        joint = verify_portfolio([("Target", "Root"), ("Root", "Mathlib.«a.b»")], self.graph)
        self.assertEqual(joint["standalone_rh_nodes"], 7)

    def test_portfolio_rejects_duplicate_invalid_and_empty_edits(self):
        from reuse.portfolio import verify_portfolio
        bad = [[], [["Donor"]], [("Donor", "Donor")], [("Target", "Ty")],
               [("Target", "Donor"), (["Target"], ["Mathlib", "a.b"])]]
        for pairs in bad:
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                verify_portfolio(pairs, self.graph)
