#!/usr/bin/env bash
# Confirm the scripts were checked out at the ref the caller invoked.
#
# The scripts ref cannot be derived inside the callee: github.job_workflow_sha
# and github.job_workflow_ref are OIDC claims and evaluate to empty in a
# reusable workflow's steps. The caller therefore states the ref, and this
# check fails the job when that statement disagrees with the caller's own
# uses: line, so the scripts can never quietly drift from the workflow.
#
# Reads GITHUB_WORKFLOW_REF, CALLER_PATH, WORKFLOW_PATH and SCRIPTS_REF.
set -euo pipefail

caller_workflow_ref="${GITHUB_WORKFLOW_REF:-}"
if [ -z "$caller_workflow_ref" ]; then
  echo "::error::GITHUB_WORKFLOW_REF is empty, so the caller workflow cannot be read."
  exit 1
fi

caller_file="${caller_workflow_ref%@*}"
caller_file="${caller_file#*/}"
caller_file="${caller_file#*/}"
caller_file="$CALLER_PATH/$caller_file"

if [ ! -f "$caller_file" ]; then
  echo "::error::Caller workflow $caller_file is not in the checkout."
  exit 1
fi

declared="$(grep -o "$WORKFLOW_PATH@[^\"' ]*" "$caller_file" | sed 's|.*@||' | sort -u || true)"
count="$(printf '%s' "$declared" | grep -c . || true)"

if [ "$count" -ne 1 ]; then
  echo "::error::Expected one $WORKFLOW_PATH reference in $caller_file, found $count."
  exit 1
fi

if [ "$declared" != "$SCRIPTS_REF" ]; then
  echo "::error::shared-workflows-ref is $SCRIPTS_REF but the caller invokes the workflow at $declared. Set both to the same ref."
  exit 1
fi

echo "Workflow scripts checked out at $SCRIPTS_REF, matching the caller."
