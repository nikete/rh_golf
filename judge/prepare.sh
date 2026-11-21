#!/usr/bin/env bash
set -euo pipefail
root=$(pwd)
tools_dir="$root/.tools"
toolchain="$tools_dir/lean-4.33.1-linux"
mkdir -p "$tools_dir"
if [[ ! -x "$toolchain/bin/lean" ]]; then
  archive=$(mktemp)
  trap 'rm -f "$archive"' EXIT
  curl --fail --location --retry 3 --output "$archive" \
    https://github.com/leanprover/lean4/releases/download/v4.33.1/lean-4.33.1-linux.tar.zst
  echo "890afd185370f85666025b883914ab4f4b339136f8c96167b69cfb62aecaf235  $archive" | sha256sum --check
  tar --zstd -xf "$archive" -C "$tools_dir"
  rm "$archive"
  trap - EXIT
fi
export PATH="$toolchain/bin:$PATH"
# Shallow, commit-pinned dependencies keep a cold build within a hosted runner's disk.
python3 - <<'PY'
import json, pathlib, subprocess
for pkg in json.loads(pathlib.Path("lake-manifest.json").read_text())["packages"]:
    folder = pathlib.Path(".lake/packages") / pkg["name"]
    def git(*args):
        return subprocess.check_output(["git", "-C", str(folder), *args], text=True).strip()
    if not (folder / ".git").is_dir():
        folder.mkdir(parents=True, exist_ok=True)
        git("init", "-q")
        git("remote", "add", "origin", pkg["url"])
        git("fetch", "-q", "--depth=1", "origin", pkg["rev"])
        git("checkout", "-q", "--detach", "FETCH_HEAD")
    if git("rev-parse", "HEAD") != pkg["rev"]:
        raise SystemExit("Wrong dependency revision: " + pkg["name"])
PY
cache_stamp=".lake/rh-golf-course-v1"
if [[ ! -f "$cache_stamp" ]]; then
  export MATHLIB_CACHE_GET_URL=https://cache.mathlib.org/mathlib4
  lake exe cache get Mathlib.NumberTheory.LSeries.RiemannZeta \
    Mathlib.NumberTheory.ArithmeticFunction.VonMangoldt Mathlib.NumberTheory.Harmonic.EulerMascheroni \
    Mathlib.Tactic.Linarith Mathlib.Tactic.LinearCombination Mathlib.Tactic.Ring
  lake build League
  touch "$cache_stamp"
else
  lake build League
fi
lake env lean judge/Extract.lean
lake env lean judge/Replay.lean
