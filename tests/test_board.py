import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
from board import record, render, standings
from run import Rejected, event_submission

class BoardTests(unittest.TestCase):
    def row(self, author, size, issue, hole="reflection", shared=None):
        return dict(author=author, nodes=size, issue=issue, hole=hole,
                    impact=dict(version=1, private_nodes=size, shared=shared or {}))

    def scoring(self, rows):
        refs = {"reflection": self.row("course", 100, 0)}
        baseline = dict(archive_nodes=1000, spine_nodes=800, composition_nodes=4)
        return standings(rows, refs, baseline)

    def test_only_new_global_records_earn_points(self):
        rows = [self.row("a", 70, 1), self.row("b", 70, 2), self.row("b", 50, 3),
                self.row("a", 1, 4, "window-logic"), self.row("c", 800, 5, "riemann")]
        pars, holes, board, project, credits = self.scoring(rows[::-1])
        self.assertEqual(credits, {1: 30, 3: 20, 5: 50})
        self.assertEqual(project["current_nodes"], 800)
        self.assertEqual(project["course_saved_nodes"], 100)
        self.assertEqual(project["saved_nodes"], 100 + sum(credits.values()))
        self.assertEqual(pars["reflection"], 50)
        self.assertEqual(len(holes["reflection"]), 2)
        self.assertEqual([p["points"] for p in board], [50, 30, 20])

    def test_pair_requires_both_halves_and_shares_common_definitions(self):
        first = self.row("criterion", 400, 1, "prime-window", {"Golf.Windows": 100})
        other = self.row("supply", 300, 2, "prime-supply", {"Golf.Windows": 100})
        self.assertFalse(self.scoring([first])[4])
        _, _, _, project, credits = self.scoring([first, other])
        self.assertEqual(project["current_nodes"], 804)
        self.assertEqual(credits, {1: 48, 2: 48})
        third = self.row("revision", 289, 3, "prime-supply", {"Golf.Windows": 100})
        _, _, _, project, credits = self.scoring([first, other, third])
        self.assertEqual(credits, {1: 48, 2: 48, 3: 11})
        self.assertEqual(project["community_saved_nodes"], sum(credits.values()))
        invalid = self.row("invalid", 100, 4, "prime-supply", {"Golf.Windows": 90})
        with self.assertRaises(ValueError):
            self.scoring([first, invalid])

    def test_pending_cannot_earn_and_cross_route_gains_do_not_stack(self):
        missing = self.row("pending", 1, 7)
        del missing["impact"]
        rows = [self.row("solo", 300, 2, "riemann"), missing,
                self.row("a", 140, 3, "prime-window"), self.row("b", 141, 4, "prime-supply")]
        _, _, _, project, credits = self.scoring(rows)
        self.assertEqual(project["pending_issues"], [7])
        self.assertEqual(credits, {2: 600, 3: 8, 4: 7})
        self.assertEqual(project["current_nodes"], 285)

    def test_event_only_takes_attribution_from_github(self):
        event = {"issue": {"title": "[entry] reflection", "body": "```lean\nx\n```", "user": {"login": "player"}}}
        self.assertEqual(event_submission(event), ("reflection", "x\n", "player"))
        event["issue"]["title"] = "[entry] imaginary"
        with self.assertRaises(Rejected):
            event_submission(event)
        event["issue"]["title"] = "[entry] reflection"
        event["issue"]["body"] += "\nBy: somebody else"
        with self.assertRaises(Rejected):
            event_submission(event)

    def test_ledger_replay_and_static_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            source = "theorem Entry.answer : True := True.intro\n"
            # Aggregation fixture only. Mathematical acceptance is covered by the CI kernel tests.
            event = {"issue": {"number": 19, "created_at": "2026-11-21", "title": "[entry] reflection",
                               "body": "```lean\n" + source + "```", "user": {"login": "player"}}}
            r = dict(status="accepted", hole="reflection", season="1", nodes=280, helpers=0,
                     axioms=[], source_sha256=hashlib.sha256(source.encode()).hexdigest(), certificate_sha256="a"*64)
            receipt = p / "receipt"; receipt.write_text(json.dumps(r))
            with patch.dict(os.environ, GITHUB_RUN_ID="11", GITHUB_RUN_ATTEMPT="1", GITHUB_SHA="a"*40):
                record(event, receipt, p/"ledger")
                record(event, receipt, p/"ledger")
                render(p/"ledger", p/"site")
                data = json.loads((p/"site/scores.json").read_text())
                self.assertEqual(len(data["accepted"]), 1)
                self.assertEqual(data["players"][0]["points"], 0)
                self.assertEqual(data["project"]["pending_issues"], [19])
                self.assertEqual((p/"site/proofs/19.lean").read_text(), source)
                self.assertIn("player", (p/"site/index.html").read_text())
                self.assertIn("CI receipt", (p/"site/reflection.html").read_text())
                r["source_sha256"] = "f"*64; receipt.write_text(json.dumps(r))
                with self.assertRaises(ValueError):
                    record(event, receipt, p/"ledger")

if __name__ == "__main__":
    unittest.main()
