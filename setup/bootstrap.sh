#!/usr/bin/env bash
# Bootstrap a repository for the shared news-fragment versioning workflow.
#
# Usage:
#   curl -sL https://raw.githubusercontent.com/launchpad-build/shared-workflows/main/setup/bootstrap.sh | bash
#
# Or clone and run locally:
#   ./bootstrap.sh [--version-source package-xml|package-json|pyproject-toml]
set -euo pipefail

SHARED_REPO="launchpad-build/shared-workflows"
VERSION_SOURCE="package-xml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version-source) VERSION_SOURCE="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "Setting up news-fragment versioning (version-source: $VERSION_SOURCE)"

# ── newsfragments directory ────────────────────────────────────────
mkdir -p newsfragments
touch newsfragments/.gitkeep
echo "  Created newsfragments/"

# ── towncrier.toml ────────────────────────────────────────────────
if [ ! -f towncrier.toml ]; then
  cat > towncrier.toml <<'EOF'
[tool.towncrier]
directory = "newsfragments"
filename = "CHANGELOG.md"
title_format = "## {version} ({project_date})"
underlines = ["", "", ""]

[[tool.towncrier.type]]
directory = "breaking"
name = "Breaking changes"
showcontent = true

[[tool.towncrier.type]]
directory = "feature"
name = "Features"
showcontent = true

[[tool.towncrier.type]]
directory = "fix"
name = "Fixes"
showcontent = true
EOF
  echo "  Created towncrier.toml"
else
  echo "  towncrier.toml already exists, skipping"
fi

# ── CHANGELOG.md seed ─────────────────────────────────────────────
if [ ! -f CHANGELOG.md ]; then
  cat > CHANGELOG.md <<'EOF'
# Changelog

<!-- towncrier release notes start -->
EOF
  echo "  Created CHANGELOG.md"
else
  echo "  CHANGELOG.md already exists, skipping"
fi

# ── Caller workflows ──────────────────────────────────────────────
mkdir -p .github/workflows

cat > .github/workflows/require-news-fragment-on-pr.yml <<EOF
name: Require news fragment on pull request

on:
  pull_request:
    branches: [main]

jobs:
  check:
    uses: ${SHARED_REPO}/.github/workflows/require-news-fragment.yml@main
EOF
echo "  Created .github/workflows/require-news-fragment-on-pr.yml"

cat > .github/workflows/release-on-merge.yml <<EOF
name: Release version on merge to main

on:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  release:
    uses: ${SHARED_REPO}/.github/workflows/release-on-merge.yml@main
    with:
      version-source: ${VERSION_SOURCE}
EOF
echo "  Created .github/workflows/release-on-merge.yml"

echo ""
echo "Done. Files created:"
echo "  newsfragments/.gitkeep"
echo "  towncrier.toml"
echo "  CHANGELOG.md"
echo "  .github/workflows/require-news-fragment-on-pr.yml"
echo "  .github/workflows/release-on-merge.yml"
echo ""
echo "Next steps:"
echo "  1. Commit these files to your main branch"
echo "  2. Create fragments as newsfragments/TICKET.{breaking,feature,fix}"
echo "  3. PRs with source changes will require a fragment"
echo "  4. Merging to main triggers an automatic release"
