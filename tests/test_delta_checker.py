from array import array
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
import delta_checker as delta
from archive_graph import ArchiveGraph
import reuse
from reuse.portfolio import verify_portfolio


class DeltaCheckerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.graph = root / "graph"
        self.graph.mkdir()
        signatures = root / "reuse"
        signatures.mkdir()
        for ctx in [patch.object(delta, "JUDGE", root), patch.object(reuse, "HERE", signatures)]:
            ctx.start()
            self.addCleanup(ctx.stop)
        self.origin = "7" * 64
        (root / "baseline.json").write_bytes(delta.encode({"metric": delta.METRIC, "root": delta.ROOT,
                                                          "archive_nodes": 41, "compressed_sha256": self.origin}))
        meta = {"metric": delta.METRIC, "version": 1, "root": 8, "baseline": 41, "export_sha256": self.origin}
        (self.graph / "manifest.json").write_bytes(delta.encode(meta))
        names = ["", "Ty", "A", "B", "Hidden", "Spare", "ReorderedUniverses", "ReadsA", delta.ROOT]
        weights = [0, 4, 6, 30, 10, 11, 9, 12, 1]
        deps = [[], [], [1], [1], [1], [1], [1], [1, 2], [2, 3]]
        refs = [0, 2, 1, 1, 0, 0, 0, 0, 1]
        nodes, edges, table = array("I"), array("I"), bytearray()
        for g in range(len(names)):
            nodes.extend([weights[g], len(edges), len(deps[g]), refs[g]])
            edges.extend(deps[g])
            if g:
                table.extend(f"{g}\t{'def' if g == 1 else 'thm'}\t".encode() + delta.encode([names[g]]) + b"\n")
        for path, words in [(self.graph / "groups.bin", nodes), (self.graph / "dependencies.bin", edges)]:
            if sys.byteorder != "little":
                words.byteswap()
            path.write_bytes(words.tobytes())
        (self.graph / "names.tsv").write_bytes(table)
        specs = {}
        for path in self.graph.iterdir():
            specs[path.name] = {"sha256": delta.digest(path.read_bytes()), "bytes": path.stat().st_size}
        (root / "archive_graph.lock.json").write_bytes(delta.encode({"export_sha256": self.origin, "files": specs}))
        self.header = {"format": 1, "export": self.origin, "axioms": delta.AXIOMS}
        self.classes = [[17, [11, 22], 2, [1], [2, 3, 4, 5, 7, 8], [["Lib", "a.b", 4]]],
                        [17, [22, 11], 2, [1], [6], [["DifferentUniverses"]]]]
        self.put_signatures()

    def put_signatures(self):
        data = b"".join(delta.encode(row) + b"\n" for row in [self.header, *self.classes])
        (delta.JUDGE / "reuse/signatures.jsonl.gz").write_bytes(gzip.compress(data))
        (delta.JUDGE / "reuse/index.lock.json").write_bytes(delta.encode({
            "export_sha256": self.origin, "bytes": len(data), "sha256": delta.digest(data)}))

    def test_aliases_bound_to_exact_original_witness(self):
        pairs = [("B", "A"), ("A", "Lib.«a.b».4")]
        result = delta.check_delta(self.graph, pairs)
        original = verify_portfolio(pairs, ArchiveGraph(self.graph))
        self.assertEqual(result["certificate_sha256"], original["certificate_sha256"])
        self.assertEqual(result["nodes"], original["standalone_rh_nodes"])
        self.assertEqual((result["nodes"], result["changed_live_nodes"]), (11, 6))
        self.assertEqual(result, delta.check_delta(self.graph, [(["A"], ["Lib","a.b",4]), (["B"], ["A"])]))
        single = delta.check_delta(self.graph, [("B","A")], single=True)
        fast = reuse.verify_reuse("B", "A", ArchiveGraph(self.graph), "")
        for field in ("archive_deps", "reuse_statement_id", "reuse_universe_parameters", "certificate_sha256"):
            self.assertEqual(single[field], fast[field])
        self.assertEqual((single["local_nodes"], single["changed_live_nodes"], single["nodes"]), (3, 3, 14))
        self.assertEqual(single["normalized_changes_sha256"], delta.check_delta(self.graph, [("B","A")])["normalized_changes_sha256"])

    def test_changed_closure_includes_new_groups_and_off_root_cycle_checks(self):
        adding = delta.check_delta(self.graph, [("B", "Hidden")])
        self.assertEqual((adding["nodes"], adding["reachable_groups"]), (24, 5))
        off = delta.check_delta(self.graph, [("Hidden", "Spare")], single=True)
        self.assertEqual((off["nodes"], off["local_nodes"], off["changed_live_nodes"]), (41, 3, 0))
        self.assertEqual(off["coverage"], {"submitted": 1, "reachable": 0, "bypassed": 1})
        with self.assertRaisesRegex(ValueError, "Cycle"):
            delta.check_delta(self.graph, [("B","A"), ("Hidden","Spare"), ("Spare","Hidden")])
        with self.assertRaisesRegex(ValueError, "Cycle"):
            delta.check_delta(self.graph, [("A","ReadsA")])
        joint = delta.check_delta(self.graph, [("A","ReadsA"), ("ReadsA", "Lib.«a.b».4")])
        self.assertEqual(joint["coverage"]["reachable"], 2)

    def test_wrong_ordered_universes_names_and_kinds(self):
        for pairs in ([("A","ReorderedUniverses")], [("Ty","A")], [("A","Ty")], [("A","Unknown")],
                      [("A","B"), (["A"],["Hidden"])], [("A","A")], [("A",'Lib.«a.b».«4»')],
                      [("A", "Lib.a.b.4")], []):
            with self.subTest(pairs=pairs), self.assertRaises(ValueError):
                delta.check_delta(self.graph,pairs)
        with self.assertRaises(ValueError):
            delta.check_delta(self.graph,[("A","B"), ("B","Hidden")], single=True)

    def test_pins_and_axioms_fail_closed(self):
        self.header["axioms"] = [*delta.AXIOMS,"sorryAx"]
        self.put_signatures()
        with self.assertRaisesRegex(ValueError, "axiom"):
            delta.check_delta(self.graph,[("A","B")])
        self.header["axioms"] = delta.AXIOMS
        self.put_signatures()
        f = self.graph / "groups.bin"
        original = f.read_bytes()
        f.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, "Checksum"):
            delta.check_delta(self.graph,[("A","B")])
        f.write_bytes(original)
        f = delta.JUDGE / "reuse/signatures.jsonl.gz"
        f.write_bytes(gzip.compress(b"[]\n"))
        with self.assertRaisesRegex(ValueError, "Checksum"):
            delta.check_delta(self.graph,[("A","B")])
