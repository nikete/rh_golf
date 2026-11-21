"""Place the original reflection proof body under the same exact target as the course entry."""
import hashlib
from pathlib import Path
import sys

DIGEST = "7e2c0b519ee420192cad8fb281c2d2bfebae2ba553342fd579c81c2aa0bd3dc5"
raw = Path(sys.argv[1]).read_bytes()
if hashlib.sha256(raw).hexdigest() != DIGEST:
    raise SystemExit("The reflection source differs from the published archive.")
prefix, proof = raw.decode().split(": RiemannHypothesis := by\n")
if not prefix.startswith("import Mathlib\n\nopen Complex\n\ntheorem Formalism.VW.rh_of_right "):
    raise SystemExit("Unexpected original theorem header")
Path(sys.argv[2]).write_text("open Complex\n\ntheorem Entry.answer : Golf.Reflection := by\n  intro hz\n" + proof)
