"""Exercise kernel replay against an isolated course and a separate trusted archive fixture."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    tc = ROOT / ".tools/lean-4.33.1-linux"
    env = {**os.environ, "PATH": f"{tc}/bin:{os.environ['PATH']}", "LEAN_NUM_THREADS": "2"}
    paths = subprocess.check_output(["lake", "env", "printenv", "LEAN_PATH"], cwd=ROOT, env=env, text=True).strip()
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        env["LEAN_PATH"] = temp + os.pathsep + paths
        def lean(*args, check=True):
            p = subprocess.run(["lean", *args], env=env, cwd=work, text=True, capture_output=True, timeout=240)
            if check and p.returncode:
                raise RuntimeError(p.stdout + p.stderr)
            return p

        # Use a minimal course for these kernel fixtures. The public issue tests
        # separately elaborate and replay real entries against League.Course.
        (work / "League").mkdir()
        for artifact in (ROOT / ".lake/build/lib/lean/League").iterdir():
            if not artifact.name.startswith("Course."):
                (work / "League" / artifact.name).symlink_to(artifact)
        (work / "League/Course.lean").write_text("import Init\n")
        lean("-o", "League/Course.olean", "League/Course.lean")
        module = "Lemmata.ArchiveReplayFixture"
        lib = work / "Lemmata"
        lib.mkdir()
        (lib / "ArchiveReplayFixture.lean").write_text("""
namespace Fixture
theorem source (p : Prop) (h : p) : p := h
theorem target (p : Prop) (h : p) : p := h
def natValue : Nat := 3
end Fixture
""")
        lean("-o", "Lemmata/ArchiveReplayFixture.olean", "Lemmata/ArchiveReplayFixture.lean")

        def certificate(source):
            (work / "Entry.lean").write_text(f"import League.Course\nimport {module}\n" + source + "\n")
            lean("-o", "Entry.olean", "Entry.lean")
            lean("--run", ROOT / "judge/Extract.lean", "proof.json", module)

        def replay(target, error=None):
            r = lean("--run", ROOT / "judge/Replay.lean", "archive", module, target, "proof.json", check=False)
            if error:
                assert r.returncode and error in r.stdout + r.stderr, r
                return None
            assert r.returncode == 0, r.stdout + r.stderr
            return json.loads(r.stdout)

        certificate("theorem Entry.answer : ∀ p : Prop, p → p := Fixture.source")
        score = replay('["Fixture","target"]')
        assert score["archive_deps"] == [["Fixture", "source"]], score
        replay("Fixture.source", "depends on its original")
        certificate("def Entry.answer : Nat := 1 + 2")
        replay("Fixture.natValue")
        certificate("def Entry.answer : Nat := 4")
        replay("Fixture.natValue", "changes computation")
        print("Named theorem, external dependency receipt and computational substitution checks passed.")


if __name__ == "__main__":
    main()
