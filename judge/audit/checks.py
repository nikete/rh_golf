"""Run the fixed external checkers on inert exports. The caller owns publication."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
POLICY = HERE / "policy.json"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def environment(tools):
    # Strip Lean, Lake, and comparator environment overrides from the calling shell.
    return {"PATH": str(tools / "lean/bin") + os.pathsep + os.defpath,
            "HOME": os.environ["HOME"], "LEAN_ABORT_ON_PANIC": "1", "LANG": "C"}


def run(command, cwd, env, log):
    with log.open("wb") as output:
        print("Running", command[0], flush=True)
        try:
            return subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                  stdout=output, stderr=subprocess.STDOUT).returncode
        except OSError as e:
            output.write(str(e).encode())
            return None


def outcome(code, observed, log, version, *, status=None):
    if status is None:
        if code == 0 and observed:
            status = "passed"
        elif code == 1:
            status = "failed"
        elif code == 2:
            status = "unsupported"
        else:
            status = "error"
    return {"status": status,
            "exit_code": code, "log_sha256": digest(log), "tool_version": version}


def check(challenge, solution, log_dir, tools, *, smoke_policy=None):
    challenge, solution, log_dir, tools = (p.resolve(strict=False) for p in (challenge, solution, log_dir, tools))
    log_dir.mkdir(parents=True, exist_ok=True)
    receipt_file = log_dir / "checks.json"
    # Published acceptance must always correspond to the current attempt.
    if receipt_file.exists():
        receipt_file.unlink()
    raw_policy = POLICY.read_bytes() if smoke_policy is None else smoke_policy
    policy = json.loads(raw_policy)
    expected = policy["challenge_sha256"]
    if digest(challenge) != expected:
        raise ValueError("The challenge does not match the trusted reference SHA-256")
    receipt = {"schema": 1, "policy_sha256": hashlib.sha256(raw_policy).hexdigest(),
               "challenge_sha256": expected, "solution_sha256": digest(solution),
               "allowed_axioms": policy["allowed_axioms"], "checks": {}}
    versions = policy["check_versions"]
    checks = receipt["checks"]
    env = environment(tools)
    tool_bin = tools / "lean/bin"
    con_leche = tools / "con-leche"
    # Comparator always runs the official kernel; configure the additional independent
    # kernel and the paranoid official build in the same invocation to avoid duplicate
    # multi-hour replays. In export-only mode Lake never builds a candidate project.
    with tempfile.TemporaryDirectory() as cwd:
        scratch = Path(cwd)
        config = {"challenge_module": "Challenge", "solution_module": "Solution",
                  "theorem_names": [policy["target"]], "permitted_axioms": policy["allowed_axioms"],
                  "external_kernels": {"nanoda": [str(tool_bin / "nanoda_bin")],
                                       "Lean paranoid": [str(tool_bin / "leanchecker-paranoid"),
                                                         "--silent", "--from-export"]}}
        (scratch / "comparator.json").write_text(json.dumps(config))
        for label, args in (("con_leche", [con_leche, "--verified", solution]),
                            ("con_leche_compare", [con_leche, "--verified", "--compare", challenge, solution])):
            log = log_dir / (label + ".log")
            code = run(args, scratch, env, log)
            lines = log.read_bytes().splitlines()
            accepted = any(line.startswith(b"con-leche: accepted ") and b"(--verified)" in line for line in lines)
            if label == "con_leche_compare":
                ending = (" " + policy["target"] + " justified by the solution").encode()
                accepted = accepted and any(line.startswith(b"con-leche: ") and line.endswith(ending) for line in lines)
            checks[label] = outcome(code, accepted, log, versions[label])
        comparator_log = log_dir / "comparator.log"
        cmd = [tool_bin / "lake", "comparator", "--config", scratch / "comparator.json",
               "--challenge-from-export", challenge, "--solution-from-export", solution]
        if sys.platform != "linux" and smoke_policy is not None:
            # macOS can exercise trusted fixtures locally. Official evidence always uses
            # Linux namespaces and the exact deployed policy digest.
            cmd.append("--inadvisably-no-sandbox")
        code = run(cmd, scratch, env, comparator_log)
        lines = comparator_log.read_bytes().splitlines()
        checks["comparator"] = outcome(code, b"Your solution is okay!" in lines, comparator_log, versions["comparator"])
        for label, titles in (("lean_kernel", ["Lean paranoid", "Lean default"]), ("nanoda", ["nanoda"])):
            success = all((title + " kernel accepts the solution").encode() in lines for title in titles)
            # These messages are printed by pinned Lake only after a child returned zero.
            # Keep the whole transcript since one failed child can stop subsequent checks.
            log = log_dir / (label + ".log")
            log.write_bytes(comparator_log.read_bytes())
            if success:
                checks[label] = outcome(0, True, log, versions[label])
            else:
                rejected = any((title + " kernel rejected the solution").encode() in lines for title in titles)
                checks[label] = outcome(None, False, log, versions[label], status="failed" if rejected else "not_run")
    passed = (all(checks[name]["status"] == "passed" for name in policy["required_checks"])
              and digest(solution) == receipt["solution_sha256"] and digest(challenge) == expected)
    receipt["status"] = "passed" if passed else "failed"
    tmp = receipt_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    tmp.replace(receipt_file)
    return passed


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: checks.py CHALLENGE.ndjson SOLUTION.ndjson LOG_DIR")
    tools = Path(os.environ.get("AUDIT_TOOLS", HERE.parents[1] / ".tools/community-audit"))
    sys.exit(0 if check(*(Path(p) for p in sys.argv[1:]), tools) else 1)
