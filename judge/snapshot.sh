#!/usr/bin/env bash
# The site always reads the newest ledger; receipt writes are atomic on a separate branch.
set -euo pipefail
mkdir -p .out/ledger
remote=$(git ls-remote --heads origin refs/heads/golf-scores)
if [[ -n "$remote" ]]; then
  git fetch --quiet --depth=1 origin refs/heads/golf-scores
  git archive FETCH_HEAD:ledger | tar -xf - -C .out/ledger
fi
python3 judge/board.py --ledger .out/ledger --site public
