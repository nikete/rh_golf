"""Publish an immutable score with an optimistic, fast-forward-only ledger update."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
from board import record

BRANCH = "golf-scores"

def git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", str(cwd), *args], check=check, text=True, capture_output=True)

def publish(event, receipt):
    for attempt in range(12):
        with tempfile.TemporaryDirectory() as dirname:
            work = Path(dirname)
            # Use the main checkout's credential via git worktree, never expose it to entries.
            home = Path.cwd()
            result = git(home, "ls-remote", "--exit-code", "origin", "refs/heads/" + BRANCH, check=False)
            if result.returncode not in (0, 2):
                raise RuntimeError("Could not read score ledger: " + result.stderr)
            if result.returncode == 0:
                git(home, "fetch", "--depth=1", "origin", "refs/heads/" + BRANCH)
                git(home, "worktree", "add", "--detach", str(work), "FETCH_HEAD")
            else:
                git(home, "worktree", "add", "--detach", str(work), "HEAD")
            try:
                if result.returncode == 2:
                    git(work, "switch", "--orphan", "scores-init-" + os.environ["GITHUB_RUN_ID"])
                record(event, receipt, work / "ledger")
                git(work, "add", "ledger")
                if git(work, "diff", "--cached", "--quiet", check=False).returncode == 0:
                    return
                git(work, "-c", "user.name=RH Golf", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                    "commit", "-m", f"Record issue #{event['issue']['number']}")
                pushed = git(work, "push", "origin", "HEAD:refs/heads/" + BRANCH, check=False)
                if not pushed.returncode:
                    return
                if "rejected" not in pushed.stderr and "cannot lock ref" not in pushed.stderr:
                    raise RuntimeError(pushed.stderr)
            finally:
                git(home, "worktree", "remove", "--force", str(work))
                if result.returncode == 2:
                    git(home, "branch", "-D", "scores-init-" + os.environ["GITHUB_RUN_ID"], check=False)
        time.sleep(min(12, attempt + 1))
    raise RuntimeError("Ledger was busy; rerun this workflow to record the verified entry.")

if __name__ == "__main__":
    publish(json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()), Path(sys.argv[1]))
