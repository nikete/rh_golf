"""Exercise the public issue path with entry 17's locally generated, inline proof."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "judge"))

import board
import post
import run

EXPECTED_SIZE = 2_382_593_136
PLAYER = "roundtrip-player"


def judge(event, folder):
    folder.mkdir()
    event_path = folder / "event.json"
    event_path.write_text(json.dumps(event))
    command = [sys.executable, str(ROOT / "judge/run.py"), "--event", str(event_path)]
    assert subprocess.check_output(command + ["--preflight"], text=True).strip() == "needs_lean=false"
    receipt = folder / "receipt.json"
    subprocess.run(command + ["--output", str(receipt)], check=True)
    return receipt, json.loads(receipt.read_text())


def main(body):
    issue = dict(number=17, title="[entry] riemannHypothesis", body=body,
                 user={"login": PLAYER}, created_at="2026-11-21T00:00:00Z")
    event = {"action": "opened", "issue": issue}
    lean_fence, raw_proof = run.issue_blocks(event)
    package = json.loads(raw_proof)
    assert package["claimed_nodes"] == EXPECTED_SIZE
    witness = base64.b64decode(package["witness_base64"], validate=True)
    mac_package = (ROOT / "docs/examples/17/entrant-proof.json").read_text(encoding="utf-8")
    golden = json.loads(mac_package)
    mac_witness = base64.b64decode(golden["witness_base64"], validate=True)
    for data, proof in ((witness, package), (mac_witness, golden)):
        assert hashlib.sha256(data).hexdigest() == proof["witness_sha256"]
    assert gzip.decompress(witness) == gzip.decompress(mac_witness)

    def with_proof(raw):
        body = f"{lean_fence}\n\n```rh-proof\n{raw.rstrip()}\n```\n"
        return dict(event, issue=dict(issue, body=body))

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        receipt, score = judge(event, work / "valid")
        assert score["status"] == "accepted" and score["standalone_rh_nodes"] == EXPECTED_SIZE, score
        ledger = work / "ledger"
        for name, fallback in {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40}.items():
            os.environ.setdefault(name, fallback)
        with patch.object(post, "update_ledger", lambda write, message: write(ledger)):
            post.publish(event, receipt)
        saved = ledger / run.SEASON / "17"
        assert json.loads((saved / "entrant-proof.json").read_bytes()) == package
        assert (saved / "entrant.rhproof.gz").read_bytes() == witness

        site = work / "site"
        board.render(ledger, site)
        result = json.loads((site / "scores.json").read_text())
        accepted, = result["accepted"]
        assert result["project"]["current_nodes"] == EXPECTED_SIZE
        assert accepted["author"] == PLAYER and accepted["points"] == 119_634_132, accepted
        verification, = accepted["verification"]
        assert verification["verification_kind"] == "exact-reuse-delta"
        assert (site / verification["evidence_url"]).is_file()

        _, mac_score = judge(with_proof(mac_package), work / "mac-example")
        assert mac_score == score, mac_score
        altered = dict(package, claimed_nodes=EXPECTED_SIZE - 1)
        _, rejected = judge(with_proof(json.dumps(altered)), work / "invalid")
        assert rejected["status"] == "rejected" and "supplied node count differs" in rejected["reason"], rejected
        print(f"Verified {EXPECTED_SIZE:,} nodes, awarded {accepted['points']:,} test points, and rejected an altered claim.")


if __name__ == "__main__":
    main(Path(sys.argv[1]).read_text(encoding="utf-8"))
