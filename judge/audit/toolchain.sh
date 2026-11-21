#!/usr/bin/env bash
# Provision only trusted, pinned binaries and sources. Run before handling candidate data.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
dest=${1:?supply a directory for trusted audit tools}
mkdir -p "$dest"
dest=$(cd "$dest" && pwd)
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) platform=linux ;;
  Darwin-arm64) platform=darwin_aarch64 ;;
  *) echo 'Supported audit hosts are Linux x86_64 and macOS arm64.' >&2; exit 2 ;;
esac
read -r version digest revision < <(python3 - "$here/policy.json" "$platform" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
print(p["lean_version"], p["distributions"][sys.argv[2]], p["con_leche_commit"])
PY
)
archive="lean-$version-$platform"
if [[ ! -x "$dest/$archive/bin/leanchecker-paranoid" ]]; then
  stage=$(mktemp -d "$dest/install.XXXXXX")
  trap 'rm -rf "$stage"' EXIT
  curl --fail --location --retry 3 --silent --show-error \
    "https://github.com/leanprover/lean4/releases/download/v$version/$archive.tar.zst" -o "$stage/archive.zst"
  python3 - "$stage/archive.zst" "$digest" <<'PY'
import hashlib, sys
with open(sys.argv[1], 'rb') as f:
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(4 << 20), b""):
        h.update(chunk)
if h.hexdigest() != sys.argv[2]:
    raise SystemExit("Lean release checksum mismatch")
PY
  zstd -dc "$stage/archive.zst" | tar -xf - -C "$stage"
  mv "$stage/$archive" "$dest/$archive"
fi
export PATH="$dest/$archive/bin:$PATH"
lean --version | grep -F "version $version" >/dev/null
src="$dest/con-leche-$revision"
if [[ ! -d "$src/.git" ]]; then
  mkdir -p "$src"
  git -C "$src" init -q
fi
if [[ "$(git -C "$src" rev-parse --verify HEAD 2>/dev/null || true)" != "$revision" ]]; then
  git -C "$src" fetch -q --depth=1 https://github.com/leanprover/con-leche.git "$revision"
  git -C "$src" -c advice.detachedHead=false checkout -q --detach "$revision"
fi
git -C "$src" diff --quiet "$revision" --
(cd "$src" && lake build con-leche)
ln -sfn "$archive" "$dest/lean"
ln -sfn "con-leche-$revision/.lake/build/bin/con-leche" "$dest/con-leche"
