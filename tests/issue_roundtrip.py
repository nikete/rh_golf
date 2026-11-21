"""Exercise an issue-open snapshot through the public judge, Git ledger and static site."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "judge"))
from board import render
from post import git, publish


def main():
    source = (ROOT / "examples/window-logic.lean").read_text()
    issue = {"issue": {"number": 7, "user": {"login": "fixture-player"},
                       "title": "[entry] window-logic", "created_at": "2026-11-21T00:00:00Z",
                       "body": "```lean\n" + source.rstrip() + "\n```"}}
    receipt = ROOT / ".out/window-logic.json"
    with tempfile.TemporaryDirectory() as dirname:
        folder = Path(dirname)
        event_file = folder / "event.json"
        event_file.write_text(json.dumps(issue))
        subprocess.run([sys.executable, str(ROOT / "judge/run.py"), "--event", str(event_file),
                        "--output", str(receipt)], check=True)
        result = json.loads(receipt.read_text())
        assert result["status"] == "accepted", result

        remote = folder / "origin.git"
        source_repo = folder / "checkout"
        source_repo.mkdir()
        git(folder, "init", "--bare", str(remote))
        git(source_repo, "init", "-b", "main")
        git(source_repo, "-c", "user.name=test", "-c", "user.email=test@example.org",
            "commit", "--allow-empty", "-m", "Fixture")
        git(source_repo, "remote", "add", "origin", str(remote))
        git(source_repo, "push", "-u", "origin", "main")
        commit = git(source_repo, "rev-parse", "HEAD").stdout.strip()
        previous = Path.cwd()
        try:
            os.chdir(source_repo)
            with patch.dict(os.environ, GITHUB_RUN_ID="11", GITHUB_RUN_ATTEMPT="1", GITHUB_SHA=commit):
                publish(issue, receipt)
                first = git(remote, "rev-parse", "golf-scores").stdout
                publish(issue, receipt)
                assert git(remote, "rev-parse", "golf-scores").stdout == first
        finally:
            os.chdir(previous)
        ledger = folder / "scores"
        git(folder, "clone", "--branch", "golf-scores", "--single-branch", str(remote), str(ledger))
        site = folder / "site"
        render(ledger / "ledger", site)
        scores = json.loads((site / "scores.json").read_text())
        assert scores["players"] == [{"author": "fixture-player", "points": 1000, "holes": 1}]
        assert scores["accepted"][0]["nodes"] == result["nodes"]
        assert (site / "proofs/7.lean").read_text() == source
        assert "fixture-player" in (site / "window-logic.html").read_text()
        print("Issue accepted, recorded once across two deliveries, and ranked on a static board.")


if __name__ == "__main__":
    main()
