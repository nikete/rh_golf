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
        # A synthetic goal tests public root naming without making a real RH claim.
        (work / "League/Course.lean").write_text("import Init\ndef RiemannHypothesis : Prop := True\n")
        lean("-o", "League/Course.olean", "League/Course.lean")
        module = "Lemmata.ArchiveReplayFixture"
        lib = work / "Lemmata"
        lib.mkdir()
        (lib / "ArchiveReplayFixture.lean").write_text("""
import League.Course
theorem riemannHypothesis : RiemannHypothesis := True.intro
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


        def declarations(filename):
            names = {0: []}
            result = {}
            for line in (work / filename).read_text().splitlines():
                row = json.loads(line)
                if "in" in row:
                    item = row.get("str", row.get("num"))
                    pre = item["pre"]
                    names[row["in"]] = [*names[pre], item.get("str", item.get("i"))]
                for kind in ("thm", "axiom", "def", "opaque"):
                    if kind in row:
                        result[tuple(names[row[kind]["name"]])] = kind
            return result

        def replay(target, error=None, export=False):
            options = ["--export", "solution.ndjson", "challenge.ndjson"] if export else []
            r = lean("--run", ROOT / "judge/Replay.lean", *options, "archive", module, target, "proof.json", check=False)
            if error:
                assert r.returncode and error in r.stdout + r.stderr, r
                return None
            assert r.returncode == 0, r.stdout + r.stderr
            return json.loads(r.stdout)

        certificate("theorem Entry.answer : ∀ p : Prop, p → p := Fixture.source")
        score = replay('["Fixture","target"]', export=True)
        subject = tuple(score["export_subject"])
        assert declarations("challenge.ndjson")[subject] == "thm"
        assert declarations("solution.ndjson")[subject] == "thm"
        assert ("Fixture", "source") in declarations("solution.ndjson")
        assert ("Fixture", "source") not in declarations("challenge.ndjson")
        assert score["archive_deps"] == [["Fixture", "source"]], score
        replay("Fixture.source", "depends on its original")
        certificate("def Entry.answer : Nat := 1 + 2")
        score = replay("Fixture.natValue", export=True)
        subject = tuple(score["export_subject"])
        assert declarations("solution.ndjson")[subject + ("conversion",)] == "thm"
        certificate("def Entry.answer : Nat := 4")
        replay("Fixture.natValue", "changes computation")
        certificate("theorem Entry.answer : RiemannHypothesis := True.intro")
        score = replay("riemannHypothesis", export=True)
        subject = ("riemannHypothesis",)
        assert tuple(score["export_subject"]) == subject
        assert declarations("solution.ndjson")[subject] == "thm"
        assert declarations("challenge.ndjson")[subject] == "thm"
        assert ("RHGolfImpact", "riemannHypothesis", "answer") not in declarations("solution.ndjson")
        print("Named theorem, external dependency receipt and computational substitution checks passed.")


if __name__ == "__main__":
    main()
