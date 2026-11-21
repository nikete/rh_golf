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
    def row(self, author, nodes, issue, hole="reflection"):
        return dict(author=author, nodes=nodes, issue=issue, hole=hole)

    def test_ties_rescores_and_personal_bests(self):
        rows = [self.row("a", 40, 1), self.row("a", 30, 2), self.row("b", 30, 3), self.row("a", 10, 4, "prime-window")]
        pars, holes, board = standings(rows, {"reflection": {"nodes": 15}})
        self.assertEqual(pars, {"reflection": 15, "prime-window": 10})
        self.assertEqual([(p["author"], p["points"]) for p in board], [("a", 1500), ("b", 500)])
        self.assertEqual(len(holes["reflection"]), 2)
        _, _, board = standings(rows + [self.row("c", 6, 7)], {})
        self.assertEqual([p["points"] for p in board], [1200, 1000, 200])

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
                self.assertEqual(data["players"][0]["points"], 1000)
                self.assertEqual((p/"site/proofs/19.lean").read_text(), source)
                self.assertIn("player", (p/"site/index.html").read_text())
                self.assertIn("CI receipt", (p/"site/reflection.html").read_text())
                r["source_sha256"] = "f"*64; receipt.write_text(json.dumps(r))
                with self.assertRaises(ValueError):
                    record(event, receipt, p/"ledger")

if __name__ == "__main__":
    unittest.main()
