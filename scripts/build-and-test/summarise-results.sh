#!/usr/bin/env bash
# Reads PACKAGES, BUILD_ROOT, BUILD_OUTCOME, TEST_OUTCOME, TEST_RC and
# GITHUB_STEP_SUMMARY from the environment.
set -uo pipefail

sudo chown -R "$(id -u):$(id -g)" build log 2>/dev/null || true

exec python3 "$(dirname "$0")/summarise_test_results.py"
