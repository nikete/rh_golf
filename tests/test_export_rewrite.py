"""Small, well-typed Lean export with a polymorphic identity theorem and forward donor."""
import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

JUDGE = Path(__file__).resolve().parents[1] / "judge"
sys.path.insert(0, str(JUDGE / "audit"))
import rewrite
from measure_export import measure_export
import reuse
from archive_graph import ArchiveGraph


class ExportRewriteTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        fixture = self.work / "reuse"
        fixture.mkdir()
        names = ["u", "α", "p", "h", "LibraryProof", "A", "B", "riemannHypothesis"]
        seq = [{"meta": {"exporter": {"name": "lean4export", "version": "3.1.0"},
                         "format": {"version": "3.1.0"}, "lean": {"githash": "fixture", "version": "4.33.1"}}}]
        seq.extend({"in": i, "str": {"pre": 0, "str": n}} for i, n in enumerate(names, 1))
        seq.append({"il": 1, "param": 1})
        def bind(kind, index, name, typ, body):
            return {kind: {"binderInfo": "default", "body": body, "name": name, "type": typ}, "ie": index}
        seq.extend([{"ie": 0, "sort": 0}, {"bvar": 0, "ie": 1}, {"bvar": 1, "ie": 2},
                    bind("forallE", 3, 4, 1, 2), bind("forallE", 4, 3, 0, 3),
                    bind("lam", 5, 4, 1, 1), bind("lam", 6, 3, 0, 5), {"ie": 7, "sort": 1},
                    bind("forallE", 8, 2, 7, 4), bind("lam", 9, 2, 7, 6)])
        def theorem(name, value):
            return {"thm": {"all": [name], "levelParams": [1], "name": name, "type": 8, "value": value}}
        seq.extend([theorem(5, 9), {"const": {"name": 5, "us": [1]}, "ie": 10},
                    theorem(6, 9), {"const": {"name": 6, "us": [1]}, "ie": 11},
                    theorem(7, 9), theorem(8, 11)])
        self.original = self.work / "original.ndjson"
        # lean4export uses lexicographically sorted JSON object keys.
        self.original.write_bytes(b"".join((json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))+"\n").encode() for row in seq))
        self.pin = {"compressed_sha256": "fixture", "unpacked_sha256": rewrite.hash_file(self.original)}
        (self.work / "baseline.json").write_text(json.dumps(self.pin))
        payload = b"".join(rewrite.canonical(row) + b"\n" for row in [
            {"format": 1, "export": "fixture", "axioms": reuse.AXIOMS}, [8, [1], 7, [], [1, 2, 3], [["LibraryProof"]]]])
        (fixture / "signatures.jsonl.gz").write_bytes(gzip.compress(payload))
        (fixture / "index.lock.json").write_text(json.dumps({"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "export_sha256": "fixture"}))
        scope = patch.object(reuse, "HERE", fixture)
        scope.start()
        self.addCleanup(scope.stop)
        g = self.graph = ArchiveGraph.__new__(ArchiveGraph)
        g.root, g.count, g.baseline = 3, 4, 18
        g.replaceable = [False, True, True, True]
        g.nodes = [0, 0, 0, 0, 10, 0, 0, 1, 10, 0, 0, 0, 8, 0, 1, 1]
        g.edges = [1]
        g.names = {rewrite.canonical([n]): i for i, n in enumerate(names[-3:], 1)}
        self.library = self.work / "mathlib-names.jsonl.gz"
        self.library.write_bytes(gzip.compress(b'["LibraryProof"]\n'))

    def write(self, pairs):
        aliases, receipt = rewrite.verify_inputs(self.graph, pairs)
        output = self.work / "changed.ndjson"
        summary = rewrite.materialize(self.original, output, self.graph, aliases, receipt, self.pin)
        self.assertEqual(summary["candidate_sha256"], rewrite.hash_file(output))
        return output, summary

    def test_forward_donor_is_ordered_and_polymorphic_constant_checked(self):
        output, summary = self.write([("A", "B")])
        rows = list(map(json.loads, output.read_bytes().splitlines()))
        decls = [r["thm"] for r in rows if "thm" in r]
        self.assertEqual([d["name"] for d in decls], [5, 7, 6, 8])
        self.assertIn({"const": {"name": 7, "us": [1]}, "ie": 12}, rows)
        self.assertEqual(decls[2], {"name": 6, "levelParams": [1], "type": 8, "all": [6], "value": 12})
        self.assertEqual(summary["expected_nodes"], 26)
        count = measure_export(output, self.library, self.work / "recount", 26)
        self.assertEqual(count["nodes"], summary["expected_nodes"])
        self.assertEqual(count["export_sha256"], summary["candidate_sha256"])

    def test_existing_library_expression_is_reused_and_portfolio_applied(self):
        output, _ = self.write([("A", "B"), ("B", "LibraryProof")])
        rows = list(map(json.loads, output.read_bytes().splitlines()))
        b = next(row["thm"] for row in rows if row.get("thm", {}).get("name") == 7)
        self.assertEqual(b["value"], 10)
        self.assertEqual(sum(row.get("const", {}).get("name") == 5 for row in rows), 1)

    def test_rejects_cycles_and_wrong_original_bytes(self):
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            rewrite.verify_inputs(self.graph, [("A", "B"), ("B", "A")])
        self.pin["unpacked_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.write([("A", "B")])
        self.assertFalse((self.work / "changed.ndjson").exists())


    @unittest.skipUnless(shutil.which("leanchecker") or shutil.which("leanchecker-paranoid"),
                         "add the pinned Lean audit toolchain bin directory to PATH for kernel regression")
    def test_kernels_check_real_inductive_and_quotient_prefix_and_forward_reuse(self):
        # The first 121 lines of the checksum-pinned MIT export contain Eq and
        # the four quotient declarations, including generated recursor info.
        prefix = (Path(__file__).parent / "fixtures/rewrite-eq-quotient.ndjson").read_bytes()
        rows = []
        for i, name in enumerate(("A", "B", "riemannHypothesis"), 26):
            rows.append({"in": i, "str": {"pre": 0, "str": name}})
        def eq_refl_theorem(name, value):
            return {"thm": {"all": [name], "levelParams": [2], "name": name, "type": 12, "value": value}}
        rows += [eq_refl_theorem(26, 21), eq_refl_theorem(27, 21),
                 {"const": {"name": 26, "us": [1]}, "ie": 87}, eq_refl_theorem(28, 87)]
        self.original.write_bytes(prefix + b"".join(rewrite.canonical(r)+b"\n" for r in rows))
        self.pin["unpacked_sha256"] = rewrite.hash_file(self.original)
        # Raw signatures are checked a second time while rewriting; the fake
        # index below is scoped to this fixture and has no effect on production.
        header = {"format": 1, "export": "fixture", "axioms": reuse.AXIOMS}
        payload = b"".join(rewrite.canonical(r)+b"\n" for r in [header, [12, [2], 9, [], [1, 2, 3], []]])
        (reuse.HERE / "signatures.jsonl.gz").write_bytes(gzip.compress(payload))
        (reuse.HERE / "index.lock.json").write_text(json.dumps({
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "export_sha256": "fixture"}))
        self.graph.nodes[12] = 10
        self.graph.baseline = 20
        output, _ = self.write([("A", "B")])
        changed = output.read_bytes()
        for original in prefix.splitlines(keepends=True):
            if original.startswith((b'{"inductive":', b'{"quot":')):
                self.assertIn(original, changed)
        # Dropping the donor's universe argument leaves an ill-typed proof.
        broken = self.work / "broken.ndjson"
        self.assertIn(b'{"const":{"name":27,"us":[1]}', changed)
        broken.write_bytes(changed.replace(b'{"const":{"name":27,"us":[1]}', b'{"const":{"name":27,"us":[]}'))
        for tool in ("leanchecker", "leanchecker-paranoid"):
            path = shutil.which(tool)
            if not path:
                continue
            with self.subTest(kernel=tool):
                for valid in (self.original, output):
                    subprocess.run([path, "--silent", "--from-export", valid], check=True, capture_output=True, timeout=60)
                rejected = subprocess.run([path, "--silent", "--from-export", broken], capture_output=True, timeout=60)
                self.assertNotEqual(rejected.returncode, 0)
