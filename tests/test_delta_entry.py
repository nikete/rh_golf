import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
import delta_entry as driver
from reuse import AXIOMS


class DeltaEntryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.ledger = self.work / "ledger"
        self.output = self.work / "proofs"
        self.graph = self.work / "graph"
        self.graph.mkdir()
        (self.graph / "manifest.json").write_text("{}")
        self.inputs = driver.policy_identity()
        self.source = "reuse Other.donor\n"
        self.row = {"hole": "Archive.target", "nodes": 2, "helpers": 0, "verifier": driver.SINGLE_REUSE,
                    "axioms": AXIOMS, "axioms_scope": "pinned-export-upper-bound", "archive_deps": [],
                    "impact": {"version": 1, "private_nodes": 2, "shared": {}}, "reuse_donor": "Other.donor",
                    "reuse_statement_id": 99, "reuse_universe_parameters": [], "status": "accepted",
                    "season": driver.SEASON, "issue": 52, "run": 128, "attempt": 1, "commit": "d" * 40,
                    "source_sha256": hashlib.sha256(self.source.encode()).hexdigest(), "certificate_sha256": "b" * 64,
                    "standalone_rh_nodes": driver.BASELINE["archive_nodes"] - 71, "author": "player",
                    "submitted": "2026-11-21T00:00:00Z"}
        pin = json.loads((driver.ROOT / "judge/archive_graph.lock.json").read_text())
        self.report = {"schema": 1, "verifier": "rh-exact-theorem-delta-v1", "root": "riemannHypothesis",
                       "local_nodes": 2, "reuse_statement_id": 99, "reuse_universe_parameters": [], "archive_deps": [],
                       "changed_live_nodes": 2, "nodes": self.row["standalone_rh_nodes"],
                       "standalone_rh_nodes": self.row["standalone_rh_nodes"], "baseline_nodes": driver.BASELINE["archive_nodes"],
                       "saved_nodes": 71, "archive_groups": pin["files"]["groups.bin"]["bytes"] // 16 - 1,
                       "reachable_groups": 201, "coverage": {"submitted": 1, "reachable": 1, "bypassed": 0},
                       "certificate_sha256": "b" * 64, "portfolio_certificate_sha256": "a" * 64,
                       "normalized_changes_sha256": "c" * 64, "signature_index_sha256": self.inputs["signatures_sha256"],
                       "graph_pin_sha256": self.inputs["graph_sha256"], "base_export_sha256": driver.BASELINE["compressed_sha256"],
                       "axioms": AXIOMS, "axioms_scope": "pinned-export-upper-bound"}
        self.origin = {"run": 733, "attempt": 2, "commit": "e" * 40}
        self.folder = self.ledger / driver.SEASON / "52"
        self.folder.mkdir(parents=True)
        self.freeze()

    def freeze(self):
        (self.folder / "score.json").write_text(json.dumps(self.row))
        (self.folder / "Entry.lean").write_text(self.source)

    def produce(self):
        with patch.object(driver, "authenticate_inputs", return_value=self.inputs), \
                patch.object(driver, "check_delta", return_value=self.report) as check, \
                patch.object(driver, "_origin", return_value=self.origin):
            self.assertEqual(driver.check(self.ledger, self.graph, self.output, run=128), 1)
            self.assertEqual(list(check.call_args.args[1]), [("Archive.target", "Other.donor")])
            self.assertTrue(check.call_args.kwargs["single"])
        return json.loads((self.output / driver.BATCH).read_text())

    def test_separate_writer_and_zero_work_after_backfill(self):
        batch = self.produce()
        self.assertFalse((self.ledger / driver.SEASON / "deltas").exists())
        driver.apply_batch(self.ledger, batch, self.origin)
        sidecar = next((self.ledger / driver.SEASON / "deltas").glob("*.json"))
        self.assertEqual(json.loads(sidecar.read_text())["run"], 733)
        before = sidecar.read_bytes()
        driver.apply_batch(self.ledger, batch, self.origin)
        self.assertEqual(sidecar.read_bytes(), before)
        with patch.object(driver, "authenticate_inputs", side_effect=AssertionError), \
                patch.object(driver.subprocess, "run", side_effect=AssertionError), \
                patch.object(driver, "_origin", return_value=self.origin):
            self.assertEqual(driver.check(self.ledger, self.work / "absent", self.output), 0)
        self.assertEqual(json.loads((self.output / driver.BATCH).read_text())["entries"], [])

    def test_recheck_fresh_source_and_entire_batch_before_install(self):
        batch = self.produce()
        for key in ("run", "attempt", "commit"):
            changed = dict(self.origin, **{key: 123})
            with self.subTest(key=key), self.assertRaises(ValueError):
                driver.apply_batch(self.ledger, batch, changed)
        bad = copy.deepcopy(batch)
        bad["entries"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicated"):
            driver.apply_batch(self.ledger, bad, self.origin)
        self.assertFalse((self.ledger / driver.SEASON / "deltas").exists())
        (self.folder / "Entry.lean").write_text("reuse Different.donor\n")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            driver.apply_batch(self.ledger, batch, self.origin)
        self.assertFalse((self.ledger / driver.SEASON / "deltas").exists())

    def test_frozen_fast_receipt_disagreement_and_stale_output(self):
        batch = self.produce()
        for field in ("nodes", "local_nodes", "archive_deps", "certificate_sha256", "coverage"):
            bad = copy.deepcopy(batch)
            bad["entries"][0]["report"][field] = False
            with self.subTest(field=field), self.assertRaises(ValueError):
                driver.apply_batch(self.ledger, bad, self.origin)
        self.row["reuse_donor"] = "Some.other"
        self.freeze()
        with self.assertRaises(ValueError):
            driver.check(self.ledger, self.graph, self.output, issue=52)
        self.assertFalse((self.output / driver.BATCH).exists())

    def test_ineligible_entry_and_run_without_receipt(self):
        self.row.pop("verifier")
        self.freeze()
        with patch.object(driver, "authenticate_inputs", side_effect=AssertionError):
            self.assertEqual(driver.check(self.ledger, self.graph, self.output, issue=52), 0)
            self.assertEqual(driver.check(self.ledger, self.graph, self.output, run=999), 0)

    def test_local_witness_regenerates_the_primary_score(self):
        origin_fields = {"issue", "run", "attempt", "commit", "author", "submitted"}
        score = driver.score_from_report(self.row["hole"], self.source, self.report)
        self.assertEqual(score, {k: v for k, v in self.row.items() if k not in origin_fields})
        witness = b"test witness"
        proof = {"format": "rh-golf-local-witness-v1", "target": self.row["hole"],
                 "source_sha256": self.row["source_sha256"], "policy_sha256": self.inputs["policy_sha256"],
                 "claimed_nodes": self.row["standalone_rh_nodes"], "witness_sha256": hashlib.sha256(witness).hexdigest(),
                 "witness_base64": base64.b64encode(witness).decode()}
        canonical = (json.dumps(proof, sort_keys=True, separators=(",", ":")) + "\n").encode()
        receipt = {"kind": "local-witness-v1", "receipt_sha256": hashlib.sha256(canonical).hexdigest()}
        evidence = driver.envelope(self.row, self.inputs, self.report, **self.origin, entrant_proof=receipt)
        driver._write_json(driver._sidecar(self.ledger, evidence["subject"]), evidence)
        self.assertFalse(driver._verified(self.ledger, self.row, evidence["subject"]))
        driver._write_json(self.folder / "entrant-proof.json", proof)
        self.assertFalse(driver._verified(self.ledger, self.row, evidence["subject"]))
        binary = self.folder / "entrant.rhproof.gz"
        binary.write_bytes(witness)
        self.assertTrue(driver._verified(self.ledger, self.row, evidence["subject"]))
        binary.write_bytes(b"corrupt")
        self.assertFalse(driver._verified(self.ledger, self.row, evidence["subject"]))
        driver._write_json(self.folder / "entrant-proof.json", {"claim": "stale"})
        self.assertFalse(driver._verified(self.ledger, self.row, evidence["subject"]))

    def test_backfill_preserves_damaged_local_evidence_and_advances_other_issues(self):
        second = dict(self.row, issue=53)
        other = self.folder.with_name("53")
        other.mkdir()
        driver._write_json(other / "score.json", second)
        (other / "Entry.lean").write_text(self.source)
        with patch.object(driver, "authenticate_inputs", return_value=self.inputs), \
                patch.object(driver, "check_delta", return_value=self.report), \
                patch.object(driver, "_origin", return_value=self.origin):
            self.assertEqual(driver.check(self.ledger, self.graph, self.output), 2)
            before_local_witness = json.loads((self.output / driver.BATCH).read_text())
            local = driver.envelope(self.row, self.inputs, self.report, **self.origin,
                                    entrant_proof={"kind": "local-witness-v1", "receipt_sha256": "f" * 64})
            path = driver._sidecar(self.ledger, local["subject"])
            driver._write_json(path, local)
            original = path.read_bytes()
            self.assertEqual(driver.check(self.ledger, self.graph, self.output), 1)
            self.assertEqual(json.loads((self.output / driver.BATCH).read_text())["entries"][0]["issue"], 53)
            driver.apply_batch(self.ledger, before_local_witness, self.origin)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(driver._verified(self.ledger, second, driver.subject_for(second)))
            # If only the original binary survives, a historical retry must still preserve it.
            path.unlink()
            (self.folder / "entrant.rhproof.gz").write_bytes(b"incomplete archive")
            driver.apply_batch(self.ledger, before_local_witness, self.origin)
            self.assertFalse(path.exists())

    def test_nominations_and_manifest_bound_to_frozen_fields(self):
        original = "-- combine: #5\n" + self.source
        row = dict(self.row, source_sha256=hashlib.sha256(original.encode()).hexdigest(), combine=[5])
        self.assertEqual(driver._instruction(row, original), ("Archive.target", "Other.donor"))
        with self.assertRaises(ValueError):
            driver._instruction(dict(row, combine=[6]), original)
        url = "https://raw.githubusercontent.com/owner/repo/" + "a" * 40 + "/proofs.jsonl.gz"
        source = f"reuse-file {url} {'b' * 64}\n"
        bulk = dict(self.row, verifier=driver.PORTFOLIO_VERIFIER, hole="riemannHypothesis",
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(), portfolio_url=url, portfolio_sha256="b" * 64,
                    portfolio_coverage=self.report["coverage"])
        self.assertEqual(driver._instruction(bulk, source), (url, "b" * 64))
        with self.assertRaises(ValueError):
            driver._instruction(dict(bulk, portfolio_sha256="f" * 64), source)
        with patch.object(driver, "fetch_pairs", return_value=iter([("A", "B")])) as fetch, \
                patch.object(driver, "check_delta", return_value=dict(self.report, portfolio_certificate_sha256="b" * 64)) as checker:
            driver.derive(bulk, source, self.graph, self.inputs)
            fetch.assert_called_once_with(url, "b" * 64)
            self.assertEqual(list(checker.call_args.args[1]), [("A", "B")])
            self.assertFalse(checker.call_args.kwargs["single"])
        report = dict(self.report, portfolio_certificate_sha256="b" * 64)
        score = driver.score_from_report("riemannHypothesis", source, report)
        self.assertEqual(score["nodes"], report["changed_live_nodes"])
        self.assertEqual(score["portfolio_sha256"], bulk["portfolio_sha256"])
        self.assertEqual(score["portfolio_coverage"], report["coverage"])
        self.assertNotIn("archive_deps", score)
        for target, instruction in [(self.row["hole"], source), ("riemannHypothesis", "-- combine: #7\n" + source)]:
            with self.assertRaises(ValueError):
                driver.score_from_report(target, instruction, report)
