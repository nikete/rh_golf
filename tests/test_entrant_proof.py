"""Exercise the public issue format for optional, locally generated proof witnesses."""
import base64
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
import entrant_proof
import run


class EntrantProofTests(unittest.TestCase):
    def setUp(self):
        self.target = "Research.cut"
        self.source = run.validate_source("reuse Research.earlier")
        self.policy = "a" * 64
        self.payload = gzip.compress(b"test witness transport", mtime=0)
        self.url = ("https://raw.githubusercontent.com/golf-player/rh-proofs/"
                    + "b" * 40 + "/witness.rhproof.gz")
        self.package = {"format": "rh-golf-local-witness-v1", "target": self.target,
                        "source_sha256": hashlib.sha256(self.source.encode()).hexdigest(),
                        "policy_sha256": self.policy, "claimed_nodes": 2382593136,
                        "witness_sha256": hashlib.sha256(self.payload).hexdigest(),
                        "witness_base64": base64.b64encode(self.payload).decode("ascii")}
        self.lean_block = "```lean\n" + self.source + "```"

    def parse(self, package, *, target=None, source=None, policy=None):
        return entrant_proof.parse_package(json.dumps(package), target or self.target,
                                           source or self.source, policy or self.policy)

    def event(self, body):
        return {"issue": {"title": "[entry] " + self.target, "body": body, "user": {"login": "golf-player"}}}

    def test_accept_inline_and_pinned_url_without_rejudging(self):
        external = dict(self.package, witness_url=self.url)
        del external["witness_base64"]
        with patch.object(run, "judge", side_effect=AssertionError("unexpected primary judge")), \
                patch.object(run, "open_graph", side_effect=AssertionError("unexpected graph load")):
            self.assertEqual(self.parse(self.package), self.package)
            self.assertEqual(self.parse(external), external)

    def test_package_bytes_are_deterministic_ascii(self):
        entry = dict(reversed(list(self.package.items())))
        entry["target"] = "Research.«α»"
        expected = (json.dumps(entry, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
        self.assertEqual(entrant_proof.package_bytes(entry), expected)
        self.assertEqual(entrant_proof.package_bytes(dict(reversed(list(entry.items())))), expected)

    def test_package_is_bound_to_normalized_source_target_and_policy(self):
        for mismatch in ({"source": self.source.replace("earlier", "other")}, {"target": "Research.other"},
                         {"policy": "c" * 64}):
            with self.subTest(mismatch=mismatch), self.assertRaises(ValueError):
                self.parse(self.package, **mismatch)

    def test_transport_requires_one_witness_and_a_pinned_github_url(self):
        missing = self.package.copy()
        del missing["witness_base64"]
        invalid = [missing, dict(self.package, witness_url=self.url)]
        for url in (self.url.replace("b" * 40, "main"), self.url.replace("raw.githubusercontent.com", "example.org"),
                    self.url.replace(".rhproof.gz", ".txt")):
            invalid.append(dict(missing, witness_url=url))
        for package in invalid:
            with self.subTest(fields=package.keys(), url=package.get("witness_url")), self.assertRaises(ValueError):
                self.parse(package)

    def test_reject_invalid_identity_claims_and_unrecognized_formats(self):
        for fields in ({"claimed_nodes": True}, {"claimed_nodes": 0}, {"claimed_nodes": 12.5},
                       {"witness_sha256": "bad"}, {"source_sha256": "0" * 64}, {"format": "earlier-format"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.parse(self.package | fields)
        for field in ("target", "policy_sha256", "claimed_nodes", "witness_sha256"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.parse({key: value for key, value in self.package.items() if key != field})

    def test_inline_bytes_and_json_fields_are_checked(self):
        for changed in ({"witness_base64": "$$$"}, {"witness_base64": ""}, {"witness_sha256": "e" * 64},
                        {"extra": 1}, {"claimed_nodes": 2**63}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.parse(self.package | changed)
        duplicate = '{"target":' + json.dumps(self.target) + "," + json.dumps(self.package)[1:]
        with self.assertRaises(ValueError):
            entrant_proof.parse_package(duplicate, self.target, self.source, self.policy)

    def test_claim_must_match_verified_substitution_size(self):
        report = {"standalone_rh_nodes": self.package["claimed_nodes"] - 1}
        with patch.object(entrant_proof, "policy_identity", return_value={"policy_sha256": self.policy}), \
                patch.object(entrant_proof, "_graph"), \
                patch.object(entrant_proof.delta_witness, "verify_witness", return_value=report) as verify, \
                patch.object(run, "judge", side_effect=AssertionError("unexpected primary judge")), \
                self.assertRaises(ValueError):
            entrant_proof.verify(json.dumps(self.package), self.target, self.source)
        verify.assert_called_once()

    def test_optional_issue_fence_preserves_source_and_github_attribution(self):
        plain = self.event(self.lean_block)
        self.assertEqual(run.issue_blocks(plain), (self.lean_block, None))
        self.assertEqual(run.event_submission(plain), (self.target, self.source, "golf-player"))
        body = self.lean_block + "\n\n```rh-proof\n" + entrant_proof.package_bytes(self.package).decode() + "```\n"
        with_proof = self.event(body.replace("\n", "\r\n"))
        self.assertEqual(run.event_submission(with_proof), run.event_submission(plain))
        source_block, proof = run.issue_blocks(with_proof)
        self.assertEqual(source_block, self.lean_block)
        self.assertEqual(entrant_proof.parse_package(proof, self.target, self.source, self.policy), self.package)
        copied = copy.deepcopy(with_proof)
        copied["issue"]["user"]["login"] = "second-player"
        self.assertEqual(run.event_submission(copied)[2], "second-player")

    def test_marker_in_a_lean_comment_is_normal_source(self):
        source = "/- Example Markdown:\n```rh-proof\n-/\ntheorem Entry.answer : True := True.intro\n"
        event = self.event("```lean\n" + source + "```")
        self.assertEqual(run.event_submission(event), (self.target, source, "golf-player"))
        self.assertIsNone(run.issue_blocks(event)[1])

    def test_reject_ambiguous_or_truncated_issue_fences(self):
        proof = "\n\n```rh-proof\n{}\n```"
        for body in (self.lean_block + proof + proof, self.lean_block + proof[:-3],
                     self.lean_block + proof + "\ntrailing text", "```rh-proof\n{}\n```"):
            with self.subTest(body=body), self.assertRaises(run.Rejected):
                run.event_submission(self.event(body))


if __name__ == "__main__":
    unittest.main()
