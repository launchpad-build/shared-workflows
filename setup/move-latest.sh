#!/usr/bin/env bash
# Point the moving latest tag at a release, so consumers pinned at @latest track it.
#
# Run this at release time, after the version tag is pushed. latest points at a
# commit that contains .github/workflows, so moving it is a workflow-file change.
# GitHub refuses those from a CI token, but a user push over SSH carries them, so
# this is a manual step run from a checkout with push rights.
#
# Usage:
#   ./setup/move-latest.sh [TAG]
#     TAG  release tag to point latest at. Defaults to the newest semver tag.
set -euo pipefail

git fetch --tags --quiet

if [ $# -ge 1 ]; then
  target="$1"
else
  target=$(git tag --list '[0-9]*.[0-9]*.[0-9]*' | sort -V | tail -1)
fi

if [ -z "$target" ]; then
  echo "No release tag found to point latest at." >&2
  exit 1
fi

echo "Pointing latest at ${target}."
git tag -f latest "${target}"
git push --force origin latest
echo "latest now points at ${target}."
