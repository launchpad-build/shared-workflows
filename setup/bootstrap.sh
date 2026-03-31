#!/usr/bin/env bash
# Bootstrap a repository for the shared news-fragment versioning workflow.
#
# Usage:
#   curl -sL https://raw.githubusercontent.com/launchpad-build/shared-workflows/main/setup/bootstrap.sh | bash
#
# Or clone and run locally:
#   ./bootstrap.sh [--version-source package-xml|package-json|pyproject-toml] [--ref TAG]
set -euo pipefail

SHARED_REPO="launchpad-build/shared-workflows"
VERSION_SOURCE="package-xml"
WORKFLOW_REF=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version-source) VERSION_SOURCE="$2"; shift 2 ;;
    --ref) WORKFLOW_REF="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Resolve workflow ref and template source
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "${SCRIPT_DIR}/templates" ]; then
  if [ -z "$WORKFLOW_REF" ]; then
    WORKFLOW_REF=$(git -C "$SCRIPT_DIR" describe --tags --exact-match 2>/dev/null || echo "main")
  fi
  fetch_template() { cat "${SCRIPT_DIR}/templates/$1"; }
else
  if [ -z "$WORKFLOW_REF" ]; then
    WORKFLOW_REF="main"
  fi
  TEMPLATE_BASE="https://raw.githubusercontent.com/${SHARED_REPO}/${WORKFLOW_REF}/setup/templates"
  fetch_template() { curl -sfL "${TEMPLATE_BASE}/$1"; }
fi

echo "Setting up news-fragment versioning (version-source: $VERSION_SOURCE, ref: $WORKFLOW_REF)"

# ── newsfragments directory ────────────────────────────────────────
mkdir -p newsfragments
touch newsfragments/.gitkeep
echo "  Created newsfragments/"

# ── towncrier.toml ────────────────────────────────────────────────
if [ ! -f towncrier.toml ]; then
  fetch_template "towncrier.toml" > towncrier.toml
  echo "  Created towncrier.toml"
else
  echo "  towncrier.toml already exists, skipping"
fi

# ── CHANGELOG.md seed ─────────────────────────────────────────────
if [ ! -f CHANGELOG.md ]; then
  fetch_template "CHANGELOG.md" > CHANGELOG.md
  echo "  Created CHANGELOG.md"
else
  echo "  CHANGELOG.md already exists, skipping"
fi

# ── Caller workflows ──────────────────────────────────────────────
mkdir -p .github/workflows

export SHARED_REPO VERSION_SOURCE WORKFLOW_REF

fetch_template ".github/workflows/require-news-fragment-on-pr.yml" \
  | envsubst '${SHARED_REPO} ${WORKFLOW_REF}' \
  > .github/workflows/require-news-fragment-on-pr.yml
echo "  Created .github/workflows/require-news-fragment-on-pr.yml"

fetch_template ".github/workflows/release-on-merge.yml" \
  | envsubst '${SHARED_REPO} ${VERSION_SOURCE} ${WORKFLOW_REF}' \
  > .github/workflows/release-on-merge.yml
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
