"""Synthetic CI sidecars exercise the public standings; they certify no real submissions."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
from archive_portfolio import PORTFOLIO_VERIFIER
from board import render
from delta_policy import policy_identity
from impact import score_project
from reuse import AXIOMS, METHOD as SINGLE
from route_audit import JUDGE, ROOT, make_subject, subject_id


class DeltaStandingsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.ledger = self.work / "ledger"
        self.season = self.ledger / "1"
        (self.season / "deltas").mkdir(parents=True)
        self.baseline = json.loads((JUDGE / "baseline.json").read_text())
        self.inputs = policy_identity()
        self.rows = []

    def entry(self, issue, saved, *, single=False):
        cost = self.baseline["archive_nodes"] - saved
        row = dict(author="player" + str(issue), issue=issue, status="accepted", season="1",
                   nodes=4, helpers=0, axioms=AXIOMS, axioms_scope="pinned-export-upper-bound",
                   certificate_sha256=f"{issue:064x}", standalone_rh_nodes=cost, run=issue, attempt=1)
        if single:
            row.update(hole="Research.A", reuse_donor="Research.B", verifier=SINGLE, reuse_statement_id=34,
                       reuse_universe_parameters=[], archive_deps=[["Research", "B"]], combine=[7],
                       impact={"version":1, "private_nodes":4, "shared":{}})
            source = "-- combine: #7\nreuse Research.B\n"
            coverage = {"submitted":1, "reachable":1, "bypassed":0}
        else:
            coverage = {"submitted":3, "reachable":2, "bypassed":1}
            url = "https://raw.githubusercontent.com/player/proofs/" + "a"*40 + "/pairs.jsonl.gz"
            row.update(hole=ROOT, verifier=PORTFOLIO_VERIFIER, portfolio_url=url, portfolio_sha256="c"*64,
                       portfolio_coverage=coverage)
            source = f"reuse-file {url} {row['portfolio_sha256']}\n"
        row["source_sha256"] = hashlib.sha256(source.encode()).hexdigest()
        folder = self.season / str(issue)
        folder.mkdir()
        (folder / "Entry.lean").write_text(source)
        (folder / "score.json").write_text(json.dumps(row))
        self.rows.append(row)
        graph = json.loads((JUDGE / "archive_graph.lock.json").read_text())
        report = dict(schema=1, verifier="rh-exact-theorem-delta-v1", root=ROOT, nodes=cost,
                      standalone_rh_nodes=cost, baseline_nodes=self.baseline["archive_nodes"], saved_nodes=saved,
                      coverage=coverage, changed_live_nodes=4, reachable_groups=123,
                      archive_groups=graph["files"]["groups.bin"]["bytes"] // 16 - 1,
                      certificate_sha256=row["certificate_sha256"], normalized_changes_sha256="6"*64,
                      portfolio_certificate_sha256="d"*64 if single else row["certificate_sha256"],
                      base_export_sha256=self.baseline["compressed_sha256"],
                      signature_index_sha256=self.inputs["signatures_sha256"], graph_pin_sha256=self.inputs["graph_sha256"],
                      axioms=AXIOMS, axioms_scope="pinned-export-upper-bound")
        if single:
            report.update(local_nodes=4, reuse_statement_id=34, reuse_universe_parameters=[], archive_deps=row["archive_deps"])
        subject = make_subject([row], "standalone-replacement" if single else "archive-portfolio",
                               [issue], cost, self.baseline)
        return dict(schema=1, verification_kind="exact-reuse-delta", subject=subject, inputs=self.inputs,
                    report=report, run=31, attempt=2, commit="f"*40)

    def save(self, evidence):
        path = self.season / "deltas" / (subject_id(evidence["subject"]) + ".json")
        path.write_text(json.dumps(evidence))
        return path

    def score(self):
        return score_project(self.rows[::-1], {}, self.baseline, audit_dir=self.season / "audits")

    def test_earlier_entry_receives_credit_even_if_certified_later(self):
        first = self.entry(71, 150, single=True)
        second = self.entry(72, 340)
        self.save(second)
        self.assertEqual(self.score()[1], {72:340})
        self.save(first)
        project, points = self.score()
        self.assertEqual(points, {71:150, 72:190})
        self.assertFalse(project["pending_issues"])
        self.assertEqual(project["verification_kind"], "exact-reuse-delta")
        self.assertEqual(project["history"][0]["entries"], (71,))
        self.assertTrue(all(h["evidence_url"].startswith("deltas/") for h in project["history"]))

    def test_two_methods_for_one_subject_cannot_double_credit(self):
        delta = self.entry(71, 150)
        self.save(delta)
        subject = delta["subject"]
        policy_file = JUDGE / "audit/policy.json"
        policy = json.loads(policy_file.read_bytes())
        digest = "9"*64
        checks = {k: dict(exit_code=0, status="passed", log_sha256="4"*64, tool_version=policy["check_versions"][k])
                  for k in policy["required_checks"]}
        full = dict(schema=1, subject=subject, solution_sha256=digest, reproductions=[digest, digest],
                    measured_root=ROOT, mathlib_inventory_sha256=self.baseline["mathlib_inventory_sha256"],
                    measured_nodes=subject["nodes"], measured_export_sha256=digest, run=90, attempt=1, commit="e"*40,
                    checker_receipt=dict(schema=1, solution_sha256=digest, challenge_sha256=policy["challenge_sha256"],
                                         policy_sha256=hashlib.sha256(policy_file.read_bytes()).hexdigest(), status="passed",
                                         allowed_axioms=policy["allowed_axioms"], checks=checks))
        folder = self.season / "audits"
        folder.mkdir()
        (folder / (subject_id(subject) + ".json")).write_text(json.dumps(full))
        project, points = self.score()
        self.assertEqual(points, {71:150})
        self.assertEqual(len(project["history"]), 1)
        self.assertEqual({a["verification_kind"] for a in project["audits"]}, {"full-export", "exact-reuse-delta"})
        self.assertEqual(project["verification_kind"], "full-export")

    def test_reject_partial_or_changed_sidecars_and_sources(self):
        alias = self.entry(71, 100, single=True)
        for key, value in (("nodes", 1), ("standalone_rh_nodes", 1), ("root", "allChi"),
                           ("certificate_sha256", "1"*64), ("graph_pin_sha256","0"*64), ("base_export_sha256","0"*64),
                           ("signature_index_sha256","f"*64), ("changed_live_nodes",False), ("axioms", []),
                           ("normalized_changes_sha256","wrong"), ("local_nodes",3), ("archive_deps",[]),
                           ("reachable_groups",0), ("coverage",{"submitted":2,"reachable":1,"bypassed":1})):
            with self.subTest(key):
                bad = copy.deepcopy(alias)
                bad["report"][key] = value
                self.save(bad)
                self.assertFalse(self.score()[1])
        bad = dict(alias, inputs={}, run=True)
        self.save(bad)
        self.assertFalse(self.score()[1])
        self.save(alias)
        self.rows[0]["reuse_donor"] = "Research.C"
        self.assertFalse(self.score()[1])
        self.rows[0]["reuse_donor"] = "Research.B"
        self.rows[0].pop("verifier")
        self.assertFalse(self.score()[1])

    def test_singleton_attestation_cannot_certify_nominated_partners(self):
        alias = self.entry(71, 100, single=True)
        self.entry(72, 340, single=True)
        bad = copy.deepcopy(alias)
        bad["subject"]["entries"].append(dict(bad["subject"]["entries"][0], issue=72))
        bad["subject"]["route"] = "archive-replacement"
        self.save(bad)
        self.assertFalse(self.score()[1])
        self.save(alias)
        self.assertEqual(self.score()[1], {71:100})
        self.assertEqual(self.score()[0]["pending_issues"], [72])

    def test_site_exposes_only_verified_receipts_and_matching_entrant_artifact(self):
        ev = self.entry(71, 130)
        import base64
        artifact = b"fixture compressed witness"
        witness = dict(format="rh-golf-local-witness-v1", target=ROOT, source_sha256=self.rows[0]["source_sha256"],
                       policy_sha256=self.inputs["policy_sha256"], claimed_nodes=ev["report"]["nodes"],
                       witness_sha256=hashlib.sha256(artifact).hexdigest(), witness_base64=base64.b64encode(artifact).decode())
        encoded = json.dumps(witness, sort_keys=True, separators=(",", ":")) + "\n"
        ev["entrant_proof"] = dict(kind="local-witness-v1", receipt_sha256=hashlib.sha256(encoded.encode()).hexdigest())
        file = self.save(ev)
        self.assertFalse(self.score()[1])
        proof = self.season / "71/entrant-proof.json"
        proof.write_text(json.dumps(witness))
        binary = self.season / "71/entrant.rhproof.gz"
        self.assertFalse(self.score()[1])
        binary.write_bytes(artifact)
        output = self.work / "site"
        with patch("board.open_graph", side_effect=AssertionError("unexpected graph load")), \
                patch("reuse.manifest._download", side_effect=AssertionError("unexpected network request")):
            render(self.ledger, output)
        scores = json.loads((output / "scores.json").read_text())
        link = "deltas/" + file.name
        self.assertEqual(scores["project"]["evidence_url"], link)
        self.assertEqual(scores["accepted"][0]["points_evidence"][0]["points"], 130)
        self.assertEqual(scores["players"][0]["points_evidence"][0]["evidence_url"], link)
        self.assertEqual(scores["personal_bests"]["riemann"][0]["verification"][0]["evidence_url"], link)
        self.assertEqual(json.loads((output / link).read_text()), ev)
        page = (output / "index.html").read_text()
        self.assertIn(link, page)
        self.assertIn("/71/entrant-proof.json", page)
        self.assertIn("/71/entrant.rhproof.gz", page)
        self.assertIn("Exact-reuse transformation", page)
        binary.write_bytes(b"other")
        self.assertFalse(self.score()[1])
        binary.write_bytes(artifact)
        witness["claimed_nodes"] -= 1
        proof.write_text(json.dumps(witness))
        render(self.ledger, output)
        self.assertFalse((output / link).exists())
        self.assertEqual(self.score()[0]["pending_issues"], [71])
