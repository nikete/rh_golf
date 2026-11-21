from array import array
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
from archive_graph import ArchiveGraph, Replacement


class SubstitutionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        w = Path(temp.name)
        # Root 5 uses {3,4}, both use 2. Original 3 also uses 1.
        # Nodes 6 and 7 are outside ordinary RH.
        weights = [0, 5, 20, 25, 30, 10, 4, 40]
        deps = [[], [], [], [1, 2], [2], [3, 4], [5], []]
        counts = [0, 1, 2, 1, 1, 1, 0, 0]
        nodes, edges = array("I"), array("I")
        for i, ds in enumerate(deps):
            nodes.extend((weights[i], len(edges), len(ds), counts[i]))
            edges.extend(ds)
        (w / "groups.bin").write_bytes(nodes.tobytes())
        (w / "dependencies.bin").write_bytes(edges.tobytes())
        (w / "manifest.json").write_text(json.dumps(dict(version=1, root=5, baseline=90,
                                                    metric="rh-declaration-nodes-v1")))
        lines = [f'{i}\tthm\t["g",{i}]\n' for i in range(1, 8)]
        lines.append('7\tinductive\t["weird.name","10"]\n')
        (w / "names.tsv").write_text(''.join(lines))
        self.graph = ArchiveGraph(w)

    def test_overlap_credited_once(self):
        r = Replacement(2, {"Interface": 3})
        self.assertEqual(self.graph.measure({3: r}), (65, {3}))
        self.assertEqual(self.graph.measure({3: r, 4: r}), (17, {3, 4}))
        self.assertEqual(self.graph.measure({3:r, 4:r, 5:Replacement(6)}), (6, {5}))

    def test_raise_and_drop_archive_dependencies(self):
        self.assertEqual(self.graph.measure({3:Replacement(1, {}, (2, 2))}), (61, {3}))
        self.assertEqual(self.graph.measure({3:Replacement(1, {}, (7,)), 7:Replacement(2)}), (63, {3, 7}))
        self.assertEqual(self.graph.measure({7:Replacement(1)}), (90, set()))

    def test_cycles_rejected_even_off_root(self):
        for rows in ({2:Replacement(1, {}, (5,))}, {6:Replacement(1, {}, (6,))},
                     {6:Replacement(1, {}, (7,)), 7:Replacement(1, {}, (6,))}):
            with self.assertRaisesRegex(ValueError, "Cyclic"):
                self.graph.measure(rows)

    def test_name_identity(self):
        self.assertEqual(self.graph.target('g.3'), 3)
        self.assertEqual(self.graph.lookup('«weird.name».«10»'), 7)
        with self.assertRaises(ValueError):
            self.graph.lookup(['weird.name', 10])
        with self.assertRaises(ValueError):
            self.graph.lookup('g.unknown')

    def test_sparse_scores_match_direct_traversal(self):
        # Random DAGs include off-root groups, forward edges, dead branches,
        # and replacements that link to each other or create joint cycles.
        rng = random.Random(29426)
        for _ in range(100):
            graph = ArchiveGraph.__new__(ArchiveGraph)
            graph.count = 20
            graph.root = 17
            graph.replaceable = bytearray([1] * graph.count)
            deps = [rng.sample(range(1, i), min(max(0, i-1), rng.randrange(4)))
                    for i in range(graph.count)]
            refs = [0] * graph.count
            refs[graph.root] = 1
            for g in range(graph.count - 1, 0, -1):
                if refs[g]:
                    for d in deps[g]:
                        refs[d] += 1
            graph.nodes, graph.edges = array("I"), array("I")
            graph.baseline = 0
            for g, ds in enumerate(deps):
                weight = rng.randint(1, 50)
                graph.nodes.extend((weight, len(graph.edges), len(ds), refs[g]))
                graph.edges.extend(ds)
                if refs[g]:
                    graph.baseline += weight
            for _ in range(6):
                replacements = {}
                for g in rng.sample(range(1, graph.count), rng.randrange(1, 9)):
                    new_deps = tuple(rng.choices(range(1, graph.count), k=rng.randrange(4)))
                    share = {"shared": 3} if rng.randrange(2) else {}
                    replacements[g] = Replacement(rng.randint(1, 20), share, new_deps)
                try:
                    direct = graph._full_measure(replacements, {"shared": 3})
                except ValueError:
                    with self.assertRaisesRegex(ValueError, "Cyclic"):
                        graph.measure(replacements)
                else:
                    self.assertEqual(graph.measure(replacements), direct)

class PortfolioTests(unittest.TestCase):
    def board(self, count):
        from archive_portfolio import ArchiveRecord, REFLECTION
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        w = Path(temp.name)
        # The branches share an expensive ancestor. Every replacement costs
        # one extra node in isolation. Only replacing all branches helps.
        root = count + 3
        weights = [0, 100] + [5]*count + [8, 9]
        deps = [[], []] + [[1]]*count + [[], list(range(2, root))]
        references = [0, count] + [1]*count + [1, 1]
        nodes, edges = array("I"), array("I")
        for i, ds in enumerate(deps):
            nodes.extend((weights[i], len(edges), len(ds), references[i]))
            edges.extend(ds)
        (w / "groups.bin").write_bytes(nodes.tobytes())
        (w / "dependencies.bin").write_bytes(edges.tobytes())
        (w / "manifest.json").write_text(json.dumps(dict(version=1, root=root, baseline=sum(weights),
                                                       metric="rh-declaration-nodes-v1")))
        names = [(i, json.dumps([f"g{i}"])) for i in range(1, root+1)]
        names.append((root-1, json.dumps(REFLECTION.split("."), separators=(",",":"))))
        (w / "names.tsv").write_text("".join(f"{i}\tthm\t{n}\n" for i,n in names))
        reference = dict(version=1, private_nodes=7, shared={})
        return ArchiveRecord(ArchiveGraph(w), reference, dict(archive_nodes=sum(weights), spine_nodes=sum(weights)-8))

    def row(self, issue, cost=6, combine=None):
        return dict(issue=issue, impact=dict(version=1, private_nodes=cost, shared={}),
                    combine=combine or [])

    def test_nonwinning_siblings_combine_automatically(self):
        record = self.board(2)
        self.assertIsNone(record.consider(self.row(1), "g2"))
        self.assertEqual(record.consider(self.row(2), "g3"), (28, (1,2), (1,2)))

    def test_explicit_three_way_and_redundant_copy(self):
        record = self.board(3)
        self.assertIsNone(record.consider(self.row(1), "g2"))
        self.assertIsNone(record.consider(self.row(2), "g3"))
        self.assertEqual(record.consider(self.row(3, combine=[1,2]), "g4"), (34, (1,2,3), (1,2,3)))
        self.assertIsNone(record.consider(self.row(4, combine=[1,2]), "g4"))
        self.assertEqual(record.consider(self.row(5, cost=5), "g4"), (33, (1,2,5), (5,)))

    def test_explicit_neutral_addon_is_dropped(self):
        record = self.board(2)
        # A duplicate of the course proof is eligible but merits no credit when
        # explicitly included with the two useful sibling replacements.
        self.assertIsNone(record.consider(self.row(1, cost=7), "g4"))
        self.assertIsNone(record.consider(self.row(2), "g2"))
        self.assertEqual(record.consider(self.row(3, combine=[1,2]), "g3"), (28, (2,3), (2,3)))

    def test_invalid_nominations(self):
        record = self.board(3)
        self.assertIsNone(record.consider(self.row(1), "g2"))
        attempts = (([8],"g3"), ([1,1],"g3"), ([1],"g2"), ([True],"g3"))
        for issue, (combine, target) in enumerate(attempts, start=2):
            self.assertIsNone(record.consider(self.row(issue, combine=combine), target))
            self.assertRegex(record.last_bundle_warning, "Unknown|distinct")
            self.assertIn(issue, record.entries)
        result = record.consider(self.row(6, cost=3, combine=[200]), "g2")
        self.assertEqual(result[2], (6,))
        self.assertRegex(record.last_bundle_warning, "Unknown")
        record.consider(self.row(7), "g3")
        self.assertIsNone(record.last_bundle_warning)

    def test_cycle_skips_nominated_route_and_preserves_valid_proof(self):
        record = self.board(3)
        first = self.row(1) | {"archive_deps": ["g3"]}
        second = self.row(2, cost=3, combine=[1]) | {"archive_deps": ["g2"]}
        self.assertIsNone(record.consider(first, "g2"))
        result = record.consider(second, "g3")
        self.assertEqual(result[2], (2,))
        self.assertRegex(record.last_bundle_warning, "Cyclic")
        self.assertIn(2, record.entries)


class CompletePortfolioTests(unittest.TestCase):
    def bulk(self, issue, nodes):
        from archive_portfolio import PORTFOLIO_VERIFIER
        return dict(issue=issue, hole="portfolio", verifier=PORTFOLIO_VERIFIER,
                    standalone_rh_nodes=nodes, portfolio_sha256="c"*64,
                    portfolio_url="https://raw.githubusercontent.com/example/project/" + "a"*40 + "/proof.jsonl.gz",
                    portfolio_coverage=dict(submitted=1000, reachable=900, bypassed=100))

    def score(self, rows, graph=None):
        from impact import score_project
        refs = {"reflection": {"impact": dict(version=1, private_nodes=100, shared={})}}
        return score_project(rows, refs, dict(archive_nodes=1000, spine_nodes=800, composition_nodes=4), graph)

    def test_complete_receipt_needs_no_replay_or_graph(self):
        project, credits = self.score([self.bulk(6, 886), self.bulk(8, 886), self.bulk(9, 830)], graph=object())
        self.assertEqual(project["winning_route"], "archive-portfolio")
        self.assertEqual(project["winning_issues"], (9,))
        self.assertEqual(project["pending_issues"], [])
        self.assertEqual(credits, {6: 14, 9: 56})

    def test_complete_routes_only_win_the_increment(self):
        direct = dict(issue=7, hole="riemann", impact=dict(version=1, private_nodes=850, shared={}))
        rows = [self.bulk(10, 820), self.bulk(6, 880), direct, self.bulk(9, 860)]
        project, credits = self.score(rows)
        self.assertEqual(project["current_nodes"], 820)
        self.assertEqual(project["winning_issues"], (10,))
        self.assertEqual(credits, {6: 20, 7: 30, 10: 30})

    def test_inconsistent_bulk_receipt_rejected(self):
        from archive_portfolio import portfolio_nodes
        row = self.bulk(1, 700)
        for key, value in (("portfolio_coverage", {"submitted": 3, "reachable": 1, "bypassed": 1}),
                           ("portfolio_sha256", "bogus"), ("portfolio_url", None), ("standalone_rh_nodes", True),
                           ("portfolio_url", "https://raw.githubusercontent.com/example/project/main/proof.jsonl.gz")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                portfolio_nodes(row | {key: value})
