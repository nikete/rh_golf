#!/usr/bin/env bash
set -euo pipefail
# Only the generated publishing branch may be replaced with site content.
source=$(gh api "repos/$GITHUB_REPOSITORY/pages" --jq '.source | .branch + ":" + .path')
[[ "$source" == 'gh-pages:/' ]] || { echo 'Branch publishing requires gh-pages at /'; exit 1; }
git fetch --quiet --depth=1 origin refs/heads/gh-pages
work=$(mktemp -d)
git worktree add --quiet --detach "$work" FETCH_HEAD
trap 'git worktree remove --force "$work"' EXIT
rsync -a --delete --exclude=/.git public/ "$work/"
git -C "$work" add --all
if ! git -C "$work" diff --cached --quiet; then
  git -C "$work" -c user.name='RH Golf' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
    commit --quiet -m "Publish RH Golf standings for run $GITHUB_RUN_ID"
  git -C "$work" push origin HEAD:refs/heads/gh-pages
fi
# A push made with GITHUB_TOKEN does not by itself trigger a branch Pages build.
gh api --method POST "repos/$GITHUB_REPOSITORY/pages/builds" --silent
