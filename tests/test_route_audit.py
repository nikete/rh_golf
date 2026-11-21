"""Synthetic receipts exercise the certification gate; they do not certify real entries."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
from impact import score_project
import route_audit as audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        work = Path(temp.name)
        self.audits = work / "audits"
        self.audits.mkdir()
        self.baseline = dict(metric="rh-declaration-nodes-v1", compressed_sha256="a"*64, mathlib_inventory_sha256="8"*64,
                             archive_nodes=1000, spine_nodes=800, composition_nodes=4)
        self.policy = dict(challenge_sha256="c"*64, required_checks=sorted(audit.CHECKS),
                           allowed_axioms=sorted(audit.AXIOMS), check_versions={k:k+"-test" for k in audit.CHECKS})
        p = work / "policy.json"
        p.write_text(json.dumps(self.policy))
        self.policy_hash = hashlib.sha256(p.read_bytes()).hexdigest()
        self.addCleanup(patch.stopall)
        patch.object(audit, "POLICY", p).start()
        self.rows = [self.entry(1, "riemann", 400), self.entry(2, "prime-window", 110),
                     self.entry(3, "prime-supply", 120), self.entry(4, "riemann", 30)]
        for row in self.rows:
            folder = work / str(row["issue"])
            folder.mkdir()
            source = ("-- fixture " + str(row["issue"])).encode()
            (folder / "Entry.lean").write_bytes(source)
            row["source_sha256"] = hashlib.sha256(source).hexdigest()

    @staticmethod
    def entry(issue, hole, nodes):
        return dict(issue=issue, hole=hole, source_sha256=f"{issue:064x}",
                    certificate_sha256=f"{issue+20:064x}", impact=dict(version=1, private_nodes=nodes, shared={}))

    def evidence(self, route, entries, nodes):
        subject = audit.make_subject(self.rows, route, entries, nodes, self.baseline)
        sha = "d"*64
        checks = {name: {"exit_code": 0, "status": "passed", "log_sha256": "e"*64,
                         "tool_version": self.policy["check_versions"][name]} for name in audit.CHECKS}
        return dict(schema=1, subject=subject, solution_sha256=sha, reproductions=[sha, sha],
                    measured_root=subject["root"], mathlib_inventory_sha256=subject["mathlib_inventory_sha256"],
                    measured_nodes=nodes, measured_export_sha256=sha, run=1, attempt=1, commit="f"*40,
                    checker_receipt=dict(schema=1, solution_sha256=sha, challenge_sha256=self.policy["challenge_sha256"],
                                         policy_sha256=self.policy_hash, status="passed",
                                         allowed_axioms=self.policy["allowed_axioms"], checks=checks))

    def save(self, evidence):
        key = audit.subject_id(evidence["subject"])
        (self.audits / (key + ".json")).write_text(json.dumps(evidence))

    def score(self):
        return score_project(self.rows, {}, self.baseline, audit_dir=self.audits)

    def test_no_proposal_promotes_itself(self):
        self.rows[0]["audit"] = self.evidence("direct", [1], 400)
        project, credit = self.score()
        self.assertEqual(project["current_nodes"], 1000)
        self.assertFalse(credit)
        self.assertEqual(project["pending_issues"], [1, 2, 3, 4])

    def test_audit_history_and_exact_joint_contributors(self):
        self.save(self.evidence("prime-pair", [2, 3], 234))
        self.save(self.evidence("direct", [1], 400))
        project, credit = self.score()
        self.assertEqual(credit, {1:600, 2:83, 3:83})
        self.assertEqual(project["current_nodes"], 234)
        self.assertEqual(project["pending_issues"], [4])
        self.rows[1]["certificate_sha256"] = "e"*64
        project, credit = self.score()
        self.assertEqual(credit, {1:600})
        self.assertEqual(len(project["invalid_audits"]), 1)
        self.assertEqual(project["pending_issues"], [2, 3, 4])

    def test_fail_closed_for_evidence_mismatch(self):
        evidence = self.evidence("direct", [1], 400)
        failures = [
            ("measured_root", "allChi"), ("mathlib_inventory_sha256", "0"*64), ("measured_nodes", 399), ("measured_export_sha256", "b"*64),
            ("reproductions", ["d"*64, "a"*64]), ("run", 0),
            ("solution_sha256", "a"*64),
        ]
        for field, value in failures:
            with self.subTest(field):
                bad = dict(evidence, **{field:value})
                self.save(bad)
                self.assertFalse(self.score()[1])
        for mutation in ("challenge", "policy", "axioms", "missing", "version", "exit", "log"):
            with self.subTest(mutation):
                bad = copy.deepcopy(evidence)
                report = bad["checker_receipt"]
                check = report["checks"]["nanoda"]
                if mutation == "challenge":
                    report["challenge_sha256"] = "a"*64
                elif mutation == "policy":
                    report["policy_sha256"] = "a"*64
                elif mutation == "axioms":
                    report["allowed_axioms"].append("sorryAx")
                elif mutation == "missing":
                    del report["checks"]["comparator"]
                elif mutation == "version":
                    check["tool_version"] = "unpinned"
                elif mutation == "exit":
                    check["exit_code"] = False
                else:
                    check["log_sha256"] = ""
                self.save(bad)
                self.assertFalse(self.score()[1])

    def test_published_source_cannot_drift_after_the_audit(self):
        self.save(self.evidence("direct", [1], 400))
        (self.audits.parent / "1/Entry.lean").write_bytes(b"-- changed")
        project, credit = self.score()
        self.assertFalse(credit)
        self.assertIn("audited digest", next(iter(project["invalid_audits"].values())))

    def test_publication_links_only_the_audited_candidate_to_a_record(self):
        import shutil
        from board import render, ROOT
        self.baseline = json.loads((ROOT / "judge/baseline.json").read_text())
        self.save(self.evidence("direct", [1], 400))
        work = self.audits.parent
        ledger = work / "ledger"
        season = ledger / "1"
        season.mkdir(parents=True)
        shutil.copytree(self.audits, season / "audits")
        for row in (self.rows[0], self.rows[3]):
            folder = season / str(row["issue"])
            shutil.copytree(work / str(row["issue"]), folder)
            content = dict(row, status="accepted", season="1", author="fixture", run=123,
                           attempt=1, nodes=row["impact"]["private_nodes"], helpers=0, axioms=[])
            (folder / "score.json").write_text(json.dumps(content))
        output = work / "site"
        with patch("board.REPO", "test/fixture"):
            render(ledger, output)
        scores = json.loads((output / "scores.json").read_text())
        self.assertEqual(scores["project"]["current_nodes"], 400)
        self.assertEqual(scores["provisional_project"]["current_nodes"], 30)
        self.assertEqual(scores["pending"], [4])
        self.assertEqual(scores["personal_bests"]["riemann"][0]["issue"], 1)
        evidence_path, = (output / "audits").glob("*.json")
        page = (output / "index.html").read_text()
        self.assertIn("audits/" + evidence_path.name, page)
        self.assertIn("/actions/runs/1/attempts/1", page)

    def test_policy_rotation_renews_only_the_same_materialized_proof(self):
        from audit.record import evidence, store_attestation
        ledger = self.audits.parent / "ledger"
        first = self.evidence("direct", [1], 400)
        subject = first["subject"]
        build = {"subject": subject, "solution_sha256": first["solution_sha256"]}
        count = {"root": subject["root"], "nodes": 400, "export_sha256": build["solution_sha256"],
                 "mathlib_inventory_sha256": subject["mathlib_inventory_sha256"]}
        receipt = evidence(build, build, count, first["checker_receipt"], subject, 1, 1, "a"*40)
        with self.assertRaisesRegex(ValueError, "wrong root"):
            evidence(build, build, dict(count, root="allChi"), first["checker_receipt"], subject, 1, 1, "a"*40)
        with self.assertRaisesRegex(ValueError, "Mathlib inventory"):
            evidence(build, build, dict(count, mathlib_inventory_sha256="0"*64), first["checker_receipt"],
                     subject, 1, 1, "a"*40)
        store_attestation(ledger, subject, receipt)
        path = ledger / "1/audits" / (audit.subject_id(subject) + ".json")
        original = path.read_bytes()
        store_attestation(ledger, subject, dict(receipt, run=2))
        self.assertEqual(path.read_bytes(), original)

        self.policy["check_versions"]["nanoda"] += "-next"
        audit.POLICY.write_text(json.dumps(self.policy))
        self.policy_hash = hashlib.sha256(audit.POLICY.read_bytes()).hexdigest()
        latest = self.evidence("direct", [1], 400)
        renewed = evidence(build, build, count, latest["checker_receipt"], subject, 3, 1, "a"*40)
        with self.assertRaises(ValueError):
            evidence(build, dict(build, solution_sha256="f"*64), count, latest["checker_receipt"],
                     subject, 3, 1, "a"*40)
        with self.assertRaisesRegex(ValueError, "frozen"):
            evidence(dict(build, subject=dict(subject, version=True)), build, count,
                     latest["checker_receipt"], subject, 3, 1, "a"*40)
        other = dict(build, solution_sha256="f"*64)
        other_count = dict(count, export_sha256="f"*64)
        other_check = dict(latest["checker_receipt"], solution_sha256="f"*64)
        wrong_proof = evidence(other, other, other_count, other_check, subject, 4, 1, "a"*40)
        with self.assertRaisesRegex(ValueError, "Changed subject or solution"):
            store_attestation(ledger, subject, wrong_proof)
        self.assertEqual(path.read_bytes(), original)
        store_attestation(ledger, subject, renewed)
        self.assertEqual(json.loads(path.read_text()), renewed)

    def test_candidate_selection_uses_ledger_and_historical_measurements(self):
        from audit import candidate
        ledger = self.audits.parent / "ledger"
        rows = [dict(self.rows[0], hole="reflection"), dict(self.rows[1], hole="window-logic"),
                dict(self.rows[2], hole="riemannHypothesis")]
        backfills = {}
        for row in rows:
            issue = row["issue"]
            folder = ledger / "1" / str(issue)
            folder.mkdir(parents=True)
            (folder / "Entry.lean").write_bytes((self.audits.parent / str(issue) / "Entry.lean").read_bytes())
            stamp = dict(row, status="accepted", season="1", author="fixture", run=42+issue,
                         attempt=1, nodes=row["impact"]["private_nodes"], helpers=0, axioms=[])
            impact = stamp.pop("impact")
            (folder / "score.json").write_text(json.dumps(stamp))
            supplement = {k: row[k] for k in ("source_sha256", "certificate_sha256", "hole")}
            supplement["impact"] = impact
            if issue == 3:
                (folder / "impact.json").write_text(json.dumps(supplement))
            else:
                backfills[str(issue)] = supplement
        with patch.object(candidate, "historic_measurements", return_value=backfills):
            entry = candidate.select(ledger, 1, None)
            self.assertEqual(entry["method"], "named-lean")
            self.assertEqual(entry["subject"]["nodes"], candidate.BASELINE["spine_nodes"] + 400)
            self.assertEqual(candidate.select(ledger, None, 44)["state"], "pending")
            self.assertEqual(candidate.select(ledger, 3, None)["subject"]["nodes"], 120)
            mismatch = dict(backfills["1"], certificate_sha256="e"*64)
            (ledger / "1/1/impact.json").write_text(json.dumps(mismatch))
            with self.assertRaisesRegex(ValueError, "immutable receipt differ"):
                candidate.select(ledger, 1, None)

    def test_reuse_audit_reconstructs_the_printed_instruction(self):
        from audit import candidate
        work = self.audits.parent
        source = work / "instruction"
        row = dict(hole="Research.X", verifier=candidate.SINGLE_REUSE, reuse_donor="Research.Y", combine=[1])
        source.write_text("-- combine: #1\nreuse Research.Y\n")
        self.assertEqual(candidate.reuse_arguments(row, source, work),
                         ["--target", "Research.X", "--donor", "Research.Y"])
        with self.assertRaisesRegex(ValueError, "recorded donor"):
            candidate.reuse_arguments(dict(row, reuse_donor="Research.Z"), source, work)
        with self.assertRaisesRegex(ValueError, "nomination"):
            candidate.reuse_arguments(dict(row, combine=[]), source, work)
        url = "https://raw.githubusercontent.com/demo/proofs/" + "b"*40 + "/round.jsonl.gz"
        row = dict(hole="riemannHypothesis", verifier=candidate.PORTFOLIO_VERIFIER, portfolio_url=url,
                   portfolio_sha256="c"*64, portfolio_coverage={"submitted":1, "reachable":1,"bypassed":0},
                   standalone_rh_nodes=127, certificate_sha256="d"*64)
        source.write_text(f"reuse-file {url} " + "c"*64 + "\n")
        with patch.object(candidate, "fetch_pairs", return_value=[["X", "Y"]]) as fetch:
            args = candidate.reuse_arguments(row, source, work)
            self.assertEqual(args[0], "--manifest")
            fetch.assert_called_once_with(url, "c"*64)
            with candidate.gzip.open(args[1], "rt") as f:
                self.assertEqual(json.loads(f.read()), ["X", "Y"])
            with self.assertRaisesRegex(ValueError, "recorded portfolio"):
                candidate.reuse_arguments(dict(row, portfolio_sha256="e"*64), source, work)
            self.assertEqual(fetch.call_count, 1)
        report = dict(certificate_sha256="d"*64, expected_nodes=127, candidate_sha256="f"*64,
                      original_sha256=candidate.BASELINE["unpacked_sha256"], coverage=row["portfolio_coverage"])
        candidate.check_rewrite(row, report, "f"*64)
        for field, value in (("certificate_sha256","0"*64), ("expected_nodes",126), ("candidate_sha256","e"*64),
                             ("original_sha256","c"*64), ("coverage",{"submitted":2, "reachable":2, "bypassed":0})):
            with self.subTest(field), self.assertRaisesRegex(ValueError, "regenerated"):
                candidate.check_rewrite(row, dict(report, **{field:value}), "f"*64)

    def test_standalone_alias_does_not_promote_a_larger_bundle(self):
        self.rows[0].update(hole="Research.A", standalone_rh_nodes=550)
        self.save(self.evidence("standalone-replacement", [1], 550))
        project, credits = self.score()
        self.assertEqual(project["current_nodes"], 550)
        self.assertEqual(credits, {1:450})
        with self.assertRaises(ValueError):
            self.evidence("standalone-replacement", [1, 2], 100)
