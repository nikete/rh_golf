#!/usr/bin/env bash
# Compile the community's exact lean4export against the same Lean ABI as Replay.
set -euo pipefail
root=$(pwd)
lib="$root/.lake/build/lib/lean"
source_dir="$root/.lake/rh-golf-exporter"
revision=15f6055e299ad5b89345e533cc2192f4cc00f659
digest=1c60d571dc24bfb99e7cbb218d8d489919bbc871238f6db9c76248521fbea998
mkdir -p "$lib" "$source_dir"
if [[ ! -f "$source_dir/$digest.built" || ! -f "$lib/Export.olean" ]]; then
  curl --fail --silent --show-error --location --retry 3 --output "$source_dir/Export.lean" \
    "https://raw.githubusercontent.com/leanprover/lean4export/$revision/Export.lean"
  python3 - "$source_dir/Export.lean" "$digest" <<'PY'
import hashlib, pathlib, sys
if hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() != sys.argv[2]:
    raise SystemExit("Pinned lean4export source digest mismatch")
PY
  (cd "$source_dir"; lean -o "$lib/Export.olean" Export.lean)
  touch "$source_dir/$digest.built"
fi
