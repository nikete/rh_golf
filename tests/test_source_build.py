"""Exercise the real downstream export with a tiny, Mathlib-free model archive."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "judge/audit"))
from source_build import make_exporter

LEAN = os.environ.get("RH_TEST_LEAN") or str(ROOT / ".tools/lean-4.33.1-linux/bin/lean")
EXPORTER = Path(os.environ.get("RH_TEST_EXPORTER", ROOT / ".lake/rh-golf-exporter/Export.lean"))


class SourceBuildTest(unittest.TestCase):
    @unittest.skipUnless(Path(LEAN).is_file() and EXPORTER.is_file(), "requires pinned Lean and lean4export")
    def test_substitution_reaches_the_root(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            env = {**os.environ, "PATH": str(Path(LEAN).parent) + os.pathsep + os.environ["PATH"],
                   "LEAN_PATH": str(work), "LEAN_ABORT_ON_PANIC": "1"}
            def lean(*args, **opts):
                return subprocess.run([LEAN, *map(str, args)], cwd=work, env=env, timeout=180, **opts)

            league = work / "League"
            league.mkdir()
            for module in ("Certificate", "CertReplay"):
                shutil.copyfile(ROOT / f"League/{module}.lean", league / f"{module}.lean")
                lean("-o", league / f"{module}.olean", f"League/{module}.lean", check=True)
            (league / "Course.lean").write_text("import Init\n")
            lean("-o", "League/Course.olean", "League/Course.lean", check=True)
            make_exporter(EXPORTER, work / "SourceOverlayExport.lean")
            lean("-o", "SourceOverlayExport.olean", "SourceOverlayExport.lean", check=True)
            (work / "Main.lean").write_text("""import Init
theorem Fixture.oldDonor : True := True.intro
theorem Fixture.newDonor : True := True.intro
theorem Fixture.target : True := Fixture.oldDonor
theorem riemannHypothesis : True := Fixture.target
theorem riemannZeta_eq_zero_re : True := True.intro
theorem LFunction_ne_zero_of_half_lt_re : True := True.intro
theorem LFunction_eq_zero_re : True := True.intro
theorem LFunction_eq_zero_re_of_isPrimitive : True := True.intro
""")
            lean("-o", "Main.olean", "Main.lean", check=True)
            # Create the inert certificate using the same Lean JSON codec as extraction.
            (work / "MakeCert.lean").write_text("""import League.Certificate
open Lean Golf.Cert
def main : IO Unit := do
  let c : Certificate := ⟨#[.const (.pack `True) [], .const (.pack `Fixture.newDonor) []],
    #[⟨.pack `Entry.answer, [], "theorem", 0, 1⟩]⟩
  IO.FS.writeFile "cert.json" (toJson c).compress
""")
            lean("--run", "MakeCert.lean", check=True)
            driver = ROOT / "judge/audit/SourceBuild.lean"
            lean("--run", driver, "", '["Fixture","target"]', "cert.json", "result.ndjson", check=True)
            names, constants, values = {0: ()}, {}, {}
            for line in (work / "result.ndjson").read_bytes().splitlines():
                row = json.loads(line)
                if "str" in row:
                    n = row["str"]
                    names[row["in"]] = (*names[n["pre"]], n["str"])
                elif "num" in row:
                    n = row["num"]
                    names[row["in"]] = (*names[n["pre"]], n["i"])
                elif "const" in row:
                    constants[row["ie"]] = names[row["const"]["name"]]
                elif "thm" in row:
                    v = row["thm"]
                    values[names[v["name"]]] = constants.get(v["value"])
            self.assertEqual(values[("riemannHypothesis",)], ("Fixture", "target"))
            self.assertEqual(values[("Fixture", "target")], ("Fixture", "newDonor"))
            self.assertNotIn(("Fixture", "oldDonor"), values)
            self.assertNotIn(("Entry", "answer"), values)


if __name__ == "__main__":
    unittest.main()
