from array import array
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

JUDGE = Path(__file__).resolve().parents[1] / "judge"
sys.path.insert(0, str(JUDGE))
from baseline import delta_anchor
import delta_policy


class DeltaPolicyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.sig = self.work / "sig.gz"
        (self.work / "reuse").mkdir()
        row = [12, [3, 8], 4, [], [1], [["Lib"]]]
        header = {"format": 1, "export": "f" * 64, "axioms": ["Classical.choice", "Quot.sound", "propext"]}
        data = b"".join(json.dumps(item).encode() + b"\n" for item in [header, row])
        self.sig.write_bytes(gzip.compress(data))
        (self.work / "reuse/index.lock.json").write_text(json.dumps({
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "export_sha256": header["export"]}))
        (self.work / "baseline.json").write_text(json.dumps({"compressed_sha256": header["export"]}))
        self.rows = [
            {"in": 1, "str": {"pre": 0, "str": "Lib"}},
            {"in": 2, "str": {"pre": 0, "str": "Archive"}},
            {"thm": {"type": 12, "value": 13, "name": 1, "levelParams": [3, 8], "all": [1]}},
            {"thm": {"type": 12, "value": 24, "name": 2, "levelParams": [3, 8], "all": [2]}},
        ]
        (self.work / "owner.bin").write_bytes(array("I", [0, 0, 1]).tobytes())
        self.measure = self.work / "measure"
        self.run_measure(13, "")
        self.save()

    def run_measure(self, expr, deps):
        self.measure.write_text("#!/bin/sh\nwhile read root; do\n"
                                f'  if [ "$root" = {expr} ]; then echo "$root 4 {deps}"; '
                                'else echo "$root 4"; fi\ndone\n')
        self.measure.chmod(0o755)

    def save(self):
        (self.work / "declarations.ndjson").write_text("".join(json.dumps(row) + "\n" for row in self.rows))

    def scan(self):
        with patch.object(delta_anchor, "JUDGE", self.work):
            return delta_anchor.scan(self.work, self.sig)

    def test_library_boundary_and_ordered_signature(self):
        receipt = self.scan()
        self.assertEqual((receipt["archive_theorems"], receipt["library_theorems"],
                          receipt["library_expression_roots"], receipt["library_to_archive_edges"]), (1, 1, 2, 0))
        self.rows[-1]["thm"]["levelParams"].reverse()
        self.save()
        with self.assertRaisesRegex(ValueError, "ordered universe"):
            self.scan()

    def test_hidden_library_edges_rejected(self):
        self.run_measure(13, "1")
        with self.assertRaisesRegex(ValueError, "archive dependencies"):
            self.scan()
        self.rows[2]["thm"]["all"].append(2)
        self.save()
        with self.assertRaisesRegex(ValueError, "metadata field"):
            self.scan()

    def test_source_drift_invalidates_publishing_identity(self):
        judge = self.work / "judge"
        judge.mkdir()
        checker = judge / "delta_checker.py"
        original = b"original checker"
        checker.write_bytes(original + b" changed")
        policy = judge / "delta_policy.json"
        policy.write_text(json.dumps({"schema": 1, "root": "riemannHypothesis", "source_files": {
            "judge/delta_checker.py": hashlib.sha256(original).hexdigest()}}))
        with patch.object(delta_policy, "JUDGE", judge), patch.object(delta_policy, "POLICY", policy):
            with self.assertRaisesRegex(ValueError, "delta_checker.py"):
                delta_policy.policy_identity()

    def test_raw_and_expanded_bytes_pinned(self):
        data = b"raw"
        expected = hashlib.sha256(data).hexdigest()
        result = io.BytesIO()
        delta_anchor.copy_verified(io.BytesIO(data), result, expected)
        self.assertEqual(result.getvalue(), data)
        with self.assertRaisesRegex(ValueError, "Wrong SHA"):
            delta_anchor.copy_verified(io.BytesIO(data + b"x"), io.BytesIO(), expected)
        self.sig.write_bytes(gzip.compress(data))
        delta_policy._verify_file(self.sig, 3, expected, compressed=True)
        with self.assertRaisesRegex(ValueError, "size"):
            delta_policy._verify_file(self.sig, 2, expected, compressed=True)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            delta_policy._verify_file(self.sig, 3, "0" * 64, compressed=True)


if __name__ == "__main__":
    unittest.main()
