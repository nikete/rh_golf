"""Render named archive substitutions and their standalone and combined scores."""
from array import array
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
from archive_graph import ArchiveGraph
from board import ROOT, render


class NamedSiteTests(unittest.TestCase):
    def test_root_portfolio_and_direct_proof_share_complete_size_ranking(self):
        url = "https://raw.githubusercontent.com/demo/proofs/" + "b"*40 + "/round.jsonl.gz"
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            for issue, author, local, total in [(91, "a", 3, 200), (92, "a", 10, 180), (93, "b", 2, 190)]:
                row = dict(status="accepted", hole="riemann", season="1", author=author, issue=issue,
                           run=42, attempt=1, nodes=local, helpers=0, axioms=[], source_sha256="a"*64,
                           certificate_sha256="b"*64)
                if issue == 92:
                    row.update(hole="riemannHypothesis", verifier="pinned-export-exact-reuse-portfolio-v1",
                               standalone_rh_nodes=total, portfolio_url=url, portfolio_sha256="c"*64,
                               portfolio_coverage=dict(submitted=5, reachable=3, bypassed=2))
                else:
                    row["impact"] = dict(version=1, private_nodes=local, shared={f"dep{issue}": total-local})
                folder = work / "ledger" / "1" / str(issue)
                folder.mkdir(parents=True)
                (folder / "score.json").write_text(json.dumps(row))
                (folder / "Entry.lean").write_text("-- rendering fixture")
            render(work / "ledger", work / "site")
            index = (work / "site/index.html").read_text()
            self.assertIn("3 of 5 substitutions reachable", index)
            self.assertIn(f"href='{url}'", index)
            self.assertIn("<td>—</td>", index)
            root = (work / "site/riemann.html").read_text()
            self.assertIn("Complete RH nodes", root)
            self.assertIn("pinned-export-exact-reuse-portfolio-v1", root)
            scores = json.loads((work / "site/scores.json").read_text())
            best = scores["provisional_personal_bests"]["riemann"]
            self.assertEqual([(r["issue"], r["nodes"], r["complete_rh_nodes"]) for r in best],
                             [(92, 10, 180), (93, 2, 190)])
            self.assertEqual(scores["provisional_records"]["riemann"], 180)
            self.assertEqual(scores["records"]["riemann"], scores["project"]["archive_nodes"])

    def test_named_entries_render_without_legacy_headroom(self):
        baseline = json.loads((ROOT / "judge/baseline.json").read_text())
        original = baseline["archive_nodes"]
        reflection = baseline["reflection_nodes"]
        # The root refers to reflection and one replaceable theorem. A fourth
        # theorem is absent from the ordinary RH proof.
        target = "Research.«A<i>term</i>»"
        with tempfile.TemporaryDirectory() as t:
            work = Path(t)
            (work / "manifest.json").write_text(json.dumps(dict(
                version=1, metric="rh-declaration-nodes-v1", root=3, baseline=original)))
            (work / "groups.bin").write_bytes(array("I", [
                0, 0, 0, 0, reflection, 0, 0, 1, 2000, 0, 0, 1,
                original-reflection-2000, 0, 2, 1, 100, 2, 0, 0]).tobytes())
            (work / "dependencies.bin").write_bytes(array("I", [1, 2]).tobytes())
            (work / "names.tsv").write_text(
                '1\tthm\t["Formalism","VW","rh_of_right"]\n2\tthm\t["Research","A<i>term</i>"]\n'
                '3\tthm\t["riemannHypothesis"]\n4\tthm\t["Unused"]\n')
            for issue, name, solo in [(91, target, original-1990), (92, "Unused", original)]:
                folder = work / "ledger" / "1" / str(issue)
                folder.mkdir(parents=True)
                row = dict(status="accepted", hole=name, season="1", nodes=10, helpers=0,
                           author="some-player", issue=issue, run=42, attempt=1, axioms=[],
                           source_sha256="a"*64, certificate_sha256="b"*64,
                           impact=dict(private_nodes=10, shared={}, version=1),
                           archive_deps=[], standalone_rh_nodes=solo)
                if name == "Unused":
                    row.update(verifier="pinned-export-exact-reuse-v1", reuse_donor=target,
                               axioms_scope="pinned-export-upper-bound", archive_deps=[["Research", "A<i>term</i>"]])
                (folder / "score.json").write_text(json.dumps(row))
                (folder / "Entry.lean").write_text("-- rendering fixture")
            with patch("board.open_graph", return_value=ArchiveGraph(work)):
                render(work / "ledger", work / "site")
            page = (work / "site/index.html").read_text()
            prompt = (work / "site/agent-prompt.txt").read_text().rstrip("\n")
            self.assertIn("python3 examples/agent_round.py", prompt)
            self.assertIn(prompt, (Path(__file__).resolve().parents[1] / "README.md").read_text())
            self.assertIn("id='copy-prompt'", page)
            self.assertIn("href='agent-prompt.txt'", page)
            self.assertTrue((work / "site/copy-prompt.js").is_file())
            self.assertIn("Research.«A&lt;i&gt;term&lt;/i&gt;»", page)
            self.assertNotIn(target, page)
            self.assertIn("Reuses Research.«A&lt;i&gt;term&lt;/i&gt;»", page)
            self.assertIn("Export receipt", page)
            self.assertIn("rules.html#reuse", page)
            scores = json.loads((work / "site/scores.json").read_text())
            results = {r["hole"]: (r["standalone_saved_nodes"], r["points"]) for r in scores["accepted"]}
            self.assertEqual(results, {target: (1990, 0), "Unused": (0, 0)})
            self.assertEqual(scores["accepted"][0]["provisional_points"], 1990)
            self.assertIsNone(scores["provisional_project"]["reflection_headroom_nodes"])
