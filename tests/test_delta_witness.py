import gzip
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
import delta_checker as delta
import delta_witness as witness
import test_delta_checker as fixtures


class WitnessTests(unittest.TestCase):
    setUp = fixtures.DeltaCheckerTests.setUp
    put_signatures = fixtures.DeltaCheckerTests.put_signatures

    def round_trip(self, pairs, single=False):
        artifact = witness.make_witness(self.graph, pairs, single=single)
        expected = delta.check_delta(self.graph, pairs, single=single)
        # Supplied evidence can be checked with both producer/all-purpose graph solvers absent.
        with patch.object(witness, "_produced_ranks_and_live", side_effect=AssertionError), \
             patch.object(delta, "measure", side_effect=AssertionError):
            self.assertEqual(witness.verify_witness(self.graph, pairs, artifact, single=single), expected)
        return artifact, expected

    def replace_payload(self, pairs, groups, bits):
        instance = witness._load(self.graph, pairs, False)
        hdr = witness.HEADER.pack(witness.MAGIC, bytes.fromhex(instance.report["graph_pin_sha256"]),
                                  bytes.fromhex(instance.report["normalized_changes_sha256"]), 0,
                                  instance.count, len(groups))
        overrides = b"".join(witness.OVERRIDE.pack(group, rank) for group, rank in groups)
        return gzip.compress(hdr + overrides + bytes(bits))

    def test_single_and_portfolio_reproduce_all_fields(self):
        for pairs, single in [([("B", "A")], True), ([("B", "A")], False),
                              ([("Hidden", delta.ROOT), (delta.ROOT, "Lib.«a.b».4")], False),
                              ([("B", "Hidden"), ("A", "ReadsA"), ("ReadsA", "Lib.«a.b».4")], False)]:
            with self.subTest(pairs=pairs, single=single):
                artifact, report = self.round_trip(pairs, single)
                self.assertEqual(artifact, witness.make_witness(self.graph, reversed(pairs), single=single))
                if pairs[0][0] == "Hidden":
                    self.assertEqual((report["coverage"]["reachable"], report["reachable_groups"]), (1, 2))
        a = witness.make_witness(self.graph, [("B", "A")], single=True)
        for other_pairs, single in [([("B", "A")], False), ([("A", "B")], True)]:
            with self.assertRaisesRegex(ValueError, "does not match"):
                witness.verify_witness(self.graph, other_pairs, a, single=single)

    def test_rank_and_exact_closure_obligations(self):
        pairs = [("B", "A")]
        packed, expected = self.round_trip(pairs)
        fields = witness.HEADER.unpack_from(gzip.decompress(packed))
        self.assertEqual(fields[-1], 0)
        bits = gzip.decompress(packed)[witness.HEADER.size:]
        self.assertEqual(bits, bytes([0b1110, 0b1]))
        # Unrelated A and Hidden may share rank 2.
        allowed = self.replace_payload(pairs, [(4, 2)], bits)
        self.assertEqual(witness.verify_witness(self.graph, pairs, allowed), expected)
        for overrides, bad_bits in [
            ([(8, 2)], bits),           # Decreases or ties on original outgoing edges are invalid.
            ([], [0b1100, 1]),          # Omitted dependency.
            ([], [0b11110, 1]),         # Closed superset containing an unjustified off-root group.
            ([], [0b1110, 0]),          # Missing root.
            ([], [0b1111, 1]),          # Claimed reserved group zero.
            ([], [0b1110, 3]),          # Claimed group beyond the last real bit.
            ([(4, 2), (4, 2)], bits),
            ([(0, 2)], bits), ([(9, 2)], bits), ([(4, 4)], bits), ([(4, 17)], bits),
        ]:
            with self.subTest(overrides=overrides, bits=bad_bits), self.assertRaises(ValueError):
                witness.verify_witness(self.graph, pairs, self.replace_payload(pairs, overrides, bad_bits))

    def test_hidden_cycle_and_malformed_frames(self):
        cyclic = [("Hidden", "Spare"), ("Spare", "Hidden")]
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            witness.make_witness(self.graph, cyclic)
        forged = self.replace_payload(cyclic, [], [0b1110, 0b1])
        with self.assertRaisesRegex(ValueError, "strictly decrease"):
            witness.verify_witness(self.graph, cyclic, forged)
        pairs = [("B", "A")]
        valid = witness.make_witness(self.graph, pairs)
        raw = gzip.decompress(valid)
        for bad in [valid[:-3], valid + gzip.compress(b""), valid + b"trailing", gzip.compress(raw[:-1]),
                    gzip.compress(raw[:8] + bytes(32) + raw[40:]), gzip.compress(raw + b"X" * 1000)]:
            with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                witness.verify_witness(self.graph, pairs, bad)


if __name__ == "__main__":
    unittest.main()
