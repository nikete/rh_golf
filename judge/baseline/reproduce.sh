#!/usr/bin/env bash
# Run from the repository root. Input is the pinned compressed export on stdin.
set -euo pipefail
work=${1:?supply a work directory containing mathlib-names.jsonl.gz}
test -f "$work/mathlib-names.jsonl.gz"
mkdir -p "$work/archive-graph"
g++ -O3 -std=c++20 judge/baseline/index.cpp -o "$work/index"
g++ -O3 -std=c++20 judge/baseline/measure.cpp -o "$work/measure"
python3 -c '
import hashlib, json, sys
expected = json.load(open("judge/baseline.json"))["compressed_sha256"]
digest = hashlib.sha256()
while chunk := sys.stdin.buffer.read(1 << 20):
    digest.update(chunk)
    sys.stdout.buffer.write(chunk)
if digest.hexdigest() != expected:
    sys.exit("Wrong SHA-256 for the compressed export")
' | zstd --long=30 -dc | "$work/index" "$work"
python3 judge/baseline/catalog.py "$work"
python3 - "$work" <<'PY'
import json, subprocess, sys
from pathlib import Path
work = Path(sys.argv[1]).resolve()
targets = json.loads((work / "targets.json").read_text())
order = ("riemannHypothesis", "Formalism.VW.rh_of_right", "rhOfAll", "Formalism.VW.rh_of_every", "allChi")
result = subprocess.check_output([work / "measure", work, *[str(targets[n]) for n in order]], text=True)
actual = json.loads(result)
baseline = json.loads(Path("judge/baseline.json").read_text())
expected = {k: baseline[k] for k in ("archive_nodes", "spine_nodes", "reflection_nodes",
                                     "archive_groups", "spine_groups", "reflection_groups")}
if actual != expected:
    raise SystemExit(f"Footprint mismatch: {actual} vs {expected}")
(work / "result.json").write_text(result)
print(json.dumps(actual, indent=2))
PY
python3 judge/baseline/graph_assets.py "$work" judge/baseline.json
