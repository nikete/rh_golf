"""Exercise the deployed check chain on three compact real Lean exports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from checks import HERE, POLICY, check, digest, environment

# These primitives are checked by Lean's comparator on every input, including a small fixture.
PRIMITIVES = """propext Classical.choice Quot.sound Quot Quot.mk Quot.lift Quot.ind
Nat.add Nat.sub Nat.mul Nat.pow Nat.gcd Nat.div Nat.mod Nat.beq Nat.ble Nat.land Nat.lor Nat.xor
Nat.shiftLeft Nat.shiftRight String.ofList Char.ofNat List eagerReduce Nat String String.mk Char
optParam autoParam semiOutParam outParam""".split()
THEOREM = "auditIdentity"


def fixtures(work, tools):
    tool_bin = tools / "lean/bin"
    env = {**environment(tools), "LEAN_PATH": str(work)}
    statements = {"Challenge": "(p : Prop) : p → p := by sorry",
                  "Valid": "(p : Prop) : p → p := fun hp => hp",
                  "Wrong": "(p q : Prop) : p → p := fun hp => hp"}
    for name, statement in statements.items():
        (work / (name + ".lean")).write_text(f"theorem {THEOREM} {statement}\n")
        subprocess.run([tool_bin / "lean", "-o", name + ".olean", name + ".lean"], cwd=work, env=env, check=True)
        with (work / (name + ".ndjson")).open("wb") as out:
            subprocess.run([tool_bin / "leanexport", name, "--", THEOREM, *PRIMITIVES],
                           cwd=work, env=env, stdout=out, check=True)
    found = None
    corrupted = False
    with (work / "Valid.ndjson").open("rb") as src, (work / "Broken.ndjson").open("wb") as dst:
        for line in src:
            row = json.loads(line)
            if row.get("str") == {"pre": 0, "str": THEOREM}:
                found = row["in"]
            if "thm" in row and found is not None and row["thm"]["name"] == found:
                row["thm"]["value"] = row["thm"]["type"]
                line = json.dumps(row, separators=(",", ":")).encode() + b"\n"
                corrupted = True
            dst.write(line)
    if not corrupted:
        raise RuntimeError("Failed to construct the deliberately ill-typed fixture")


def smoke(output, tools):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        fixtures(work, tools)
        challenge = work / "Challenge.ndjson"
        policy = json.loads(POLICY.read_bytes())
        policy.update(scope="fixture-only", target=THEOREM, challenge_sha256=digest(challenge))
        raw = json.dumps(policy, sort_keys=True).encode()
        for folder, name, valid in (("valid", "Valid", True), ("wrong-statement", "Wrong", False),
                                    ("invalid-proof", "Broken", False)):
            path = output / folder
            result = check(challenge, work / (name + ".ndjson"), path, tools, smoke_policy=raw)
            checks = json.loads((path / "checks.json").read_text())["checks"]
            if result != valid:
                raise RuntimeError("Unexpected fixture verdict for " + folder)
            if name == "Wrong" and (checks["con_leche"]["status"] != "passed"
                                    or any(checks[k]["status"] == "passed" for k in ("comparator", "con_leche_compare"))):
                raise RuntimeError("Both independent statement comparators must reject the well-typed wrong target")
            if name == "Broken" and any(checks[k]["status"] == "passed" for k in ("con_leche", "comparator")):
                raise RuntimeError("An invalid theorem body passed a kernel")
    print("Valid proof accepted, wrong statement and ill-typed proof rejected.")


if __name__ == "__main__":
    tools = Path(os.environ.get("AUDIT_TOOLS", HERE.parents[1] / ".tools/community-audit")).resolve()
    if len(sys.argv) != 2:
        raise SystemExit("Usage: smoke.py LOG_DIR")
    smoke(Path(sys.argv[1]).resolve(), tools)
