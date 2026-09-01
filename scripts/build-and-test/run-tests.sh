#!/usr/bin/env bash
# Reads WORKER, TEST_ARGS and GITHUB_OUTPUT from the environment.
#
# Only the selected packages are tested, so a sibling pulled in by
# --packages-up-to does not add its results to this repository's check.
set -uo pipefail

docker exec -e TEST_ARGS "$WORKER" bash -c '
  source "/opt/ros/$ROS_DISTRO/setup.bash"
  colcon test \
    --base-paths $BASE_PATHS \
    --packages-select $PACKAGES \
    --event-handlers console_cohesion+ \
    --return-code-on-test-failure \
    $TEST_ARGS
  rc=$?
  colcon test-result --all --verbose || true
  exit $rc
'
rc=$?
echo "rc=$rc" >> "$GITHUB_OUTPUT"
exit "$rc"
