#!/usr/bin/env bash
# Produce the one-hole ordinary-RH reference without running candidate code.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out=${1:?supply an output .ndjson path}
mkdir -p "$(dirname "$out")"
stage=$(mktemp -d "$(dirname "$out")/reference.XXXXXX")
trap 'rm -rf "$stage"' EXIT
url=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["upstream_challenge_url"])' "$here/policy.json")
curl --fail --silent --show-error --location --retry 3 "$url" -o "$stage/challenge.zst"
python3 - "$here/policy.json" "$stage/challenge.zst" <<'PY'
import hashlib, json, pathlib, sys
expected = json.load(open(sys.argv[1]))["upstream_challenge_compressed_sha256"]
if hashlib.sha256(pathlib.Path(sys.argv[2]).read_bytes()).hexdigest() != expected:
    raise SystemExit("Unexpected compressed MIT challenge")
PY
zstd --long=27 -dc "$stage/challenge.zst" > "$stage/original.ndjson"
python3 "$here/reference.py" "$stage/original.ndjson" "$stage/ordinary.ndjson"
python3 - "$here/policy.json" "$stage/ordinary.ndjson" <<'PY'
import hashlib, json, sys
with open(sys.argv[2], "rb") as f:
    h = hashlib.sha256()
    for b in iter(lambda: f.read(4 << 20), b""):
        h.update(b)
if h.hexdigest() != json.load(open(sys.argv[1]))["challenge_sha256"]:
    raise SystemExit("The projected RH challenge differs from the accepted pin")
PY
mv "$stage/ordinary.ndjson" "$out"
