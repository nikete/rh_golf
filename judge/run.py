"""Run one RH Golf entry. CI places only the elaboration side in the candidate sandbox."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "judge/holes.json").read_text())
TARGETS = {h["id"]: h["target"] for h in CONFIG}
ALLOWED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
MAX_SOURCE = 48 * 1024
MAX_CERT = 8 * 1024 * 1024
MAX_NODES = 100_000
SANDBOX_IMAGE = (ROOT / "judge/image.txt").read_text().strip()
ISSUE_TITLE = re.compile(r"^\[entry\]\s+([a-z-]+)(?:\s+.*)?$", re.I)
SOURCE_BLOCK = re.compile(r"\A(?:### Lean source\s+)?```(?:lean4?|Lean)?[ \t]*\n(.*?)\n```\s*\Z", re.S)
LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}\Z")
SEASON = "1"

class Rejected(Exception):
    """A deterministic format, compilation, checker or resource rejection."""


def validate_source(text):
    if not text.strip() or len(text.encode()) > MAX_SOURCE or "\x00" in text:
        raise Rejected("Supply 1 to 49,152 bytes of UTF-8 Lean source.")
    return text.rstrip() + "\n"


def event_submission(event):
    issue = event["issue"]
    # Issue author is the GitHub-authenticated entrant. The event snapshot is immutable.
    match = ISSUE_TITLE.fullmatch(issue["title"].strip())
    if not match or match[1] not in TARGETS:
        raise Rejected("Use an entry template and a course hole ID.")
    block = SOURCE_BLOCK.fullmatch((issue.get("body") or "").replace("\r\n", "\n").strip())
    if not block:
        raise Rejected("Put the declarations inside one fenced lean code block.")
    account = issue["user"]["login"]
    if not LOGIN.fullmatch(account):
        raise Rejected("Unsupported GitHub account name.")
    return match[1], validate_source(block[1]), account


def clean_env():
    toolchain = ROOT / ".tools/lean-4.33.1-linux"
    if not (toolchain / "bin/lean").exists():
        raise RuntimeError("Install the pinned toolchain with judge/prepare.sh")
    env = {"PATH": f"{toolchain}/bin:/usr/bin:/bin", "HOME": "/tmp",
           "LANG": "C.UTF-8", "LEAN_ABORT_ON_PANIC": "1", "LEAN_NUM_THREADS": "2"}
    paths = subprocess.check_output(["lake", "env", "printenv", "LEAN_PATH"],
                                    cwd=ROOT, env=env, text=True, timeout=60).strip()
    env["LEAN_PATH"] = paths
    return env, toolchain


def limited():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 << 20, 64 << 20))


def process(argv, env, cwd, stdout, stderr, timeout):
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                              stdout=stdout, stderr=stderr, timeout=timeout, preexec_fn=limited)
    except subprocess.TimeoutExpired as exc:
        raise Rejected("Entry exceeded its time allowance.") from exc
    if proc.returncode:
        raise Rejected(f"Checker process exited with status {proc.returncode}.")


def elaborate(src, env, toolchain, work, trusted_example):
    (work / "Entry.lean").write_text("import League.Course\n" + src)
    # The only bytes crossing the public-submission boundary are bounded JSON on stdout.
    if trusted_example:
        subprocess.run(["lean", "-o", "Entry.olean", "Entry.lean"], cwd=work, env=env,
                       check=True, timeout=240, stdout=sys.stderr, stderr=sys.stderr)
        inside = {**env, "LEAN_PATH": str(work) + ":" + env["LEAN_PATH"]}
        subprocess.run(["lean", "--run", str(ROOT / "judge/Extract.lean"), str(work / "proof.json")],
                       cwd=work, env=inside, check=True, timeout=180, stdout=sys.stderr)
    else:
        # No token, network, host workspace, docker socket, runner commands or shared writable mounts.
        # Lake can resolve symlinks in its search path. Map each path to a mounted directory.
        search_dirs = []
        for raw in env["LEAN_PATH"].split(os.pathsep):
            path = Path(raw).resolve()
            if path.is_relative_to(toolchain.resolve()):
                search_dirs.append(str(Path("/opt/lean") / path.relative_to(toolchain.resolve())))
            else:
                search_dirs.append(str(Path("/course/.lake") / path.relative_to(ROOT / ".lake")))
        search = ":".join(search_dirs)
        argv = ["docker", "run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL",
                "--security-opt=no-new-privileges", "--pids-limit=128", "--memory=6g",
                "--memory-swap=6g", "--cpus=2", "--user=65534:65534", "--ulimit",
                "fsize=16777216:16777216", "--tmpfs", "/tmp:rw,nosuid,nodev,size=160m,mode=1777",
                "-v", f"{toolchain}:/opt/lean:ro", "-v", f"{ROOT}/.lake:/course/.lake:ro",
                "-v", f"{ROOT}/judge/Extract.lean:/Extract.lean:ro",
                "-v", f"{work}/Entry.lean:/input/Entry.lean:ro",
                "-e", "HOME=/tmp", "-e", "LEAN_ABORT_ON_PANIC=1", "-e", "LEAN_NUM_THREADS=2",
                "-e", f"LEAN_PATH=/tmp:{search}", "-w", "/tmp", SANDBOX_IMAGE, "sh", "-ec",
                "cp /input/Entry.lean Entry.lean; "
                "/opt/lean/bin/lean -o Entry.olean Entry.lean >&2; "
                "/opt/lean/bin/lean --run /Extract.lean /tmp/proof.json >&2; cat /tmp/proof.json"]
        # Download the standard userspace before the networkless container is started.
        subprocess.run(["docker", "image", "inspect", SANDBOX_IMAGE], check=True,
                       stdout=subprocess.DEVNULL, timeout=20)
        with (work / "proof.json").open("wb") as cert, (work / "compile.log").open("wb") as log:
            try:
                process(argv, env, ROOT, cert, log, 360)
            except Rejected as exc:
                with (work / "compile.log").open("rb") as reader:
                    reader.seek(max(0, (work / "compile.log").stat().st_size - 900))
                    detail = reader.read().decode(errors="replace")
                raise Rejected(str(exc) + " " + detail) from exc
    cert = work / "proof.json"
    if not stat.S_ISREG(cert.lstat().st_mode) or not (0 < cert.stat().st_size <= MAX_CERT):
        raise Rejected("Missing certificate or certificate exceeds 8 MiB.")
    return cert


def judge(hole, text, trusted_example=False):
    src = validate_source(text)
    env, tc = clean_env()
    with tempfile.TemporaryDirectory() as dirname:
        work = Path(dirname)
        # The kernel only reads the certificate and the course; no candidate .olean is on its path.
        cert = elaborate(src, env, tc, work, trusted_example)
        with (work / "result").open("wb") as out, (work / "err").open("wb") as err:
            try:
                process(["lean", "--run", str(ROOT / "judge/Replay.lean"), TARGETS[hole], str(cert)],
                        env, ROOT, out, err, 240)
            except Rejected as exc:
                raise Rejected(str(exc) + " " + (work / "err").read_bytes()[:500].decode(errors="replace")) from exc
        score = json.loads((work / "result").read_text())
        validate_score(score)
        return {**score, "source_sha256": hashlib.sha256(src.encode()).hexdigest(),
                "certificate_sha256": hashlib.sha256(cert.read_bytes()).hexdigest()}


def validate_score(score):
    if (type(score["nodes"]) is not int or not 1 <= score["nodes"] <= MAX_NODES
            or type(score["helpers"]) is not int or not 0 <= score["helpers"] <= 1000
            or not isinstance(score["axioms"], list) or not set(score["axioms"]) <= ALLOWED_AXIOMS):
        raise ValueError("Malformed replay result")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path)
    parser.add_argument("--hole", choices=TARGETS)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", action="store_true", help="Only for checked-in maintainer examples")
    args = parser.parse_args()
    result = None
    try:
        if args.event:
            if args.reference:
                parser.error("Public entries always use the sandbox.")
            hole, src, author = event_submission(json.loads(args.event.read_text()))
        else:
            if not args.source or not args.hole:
                parser.error("--hole and --source are required for a local entry")
            hole, src, author = args.hole, args.source.read_text(), "Course reference"
            if args.reference:
                path = next((h.get("example") for h in CONFIG if h["id"] == hole), None)
                if not path or args.source.resolve() != (ROOT / path).resolve():
                    parser.error("--reference only accepts the checked-in example for this hole")
        result = {"status": "accepted", "hole": hole, "season": SEASON, **judge(hole, src, args.reference)}
    except Rejected as exc:
        result = {"status": "rejected", "reason": " ".join(str(exc).split())[-1000:]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if result["status"] == "accepted":
        print(f"accepted {result['nodes']} nodes")
    else:
        # Keep diagnostics on one JSON-escaped line, including arbitrary compiler text.
        print("rejected " + json.dumps(result["reason"], ensure_ascii=True))
    if result["status"] != "accepted" and not args.event:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
