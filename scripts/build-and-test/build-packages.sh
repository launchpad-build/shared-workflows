#!/usr/bin/env bash
# Reads WORKER and BUILD_ARGS from the environment.
#
# --packages-up-to, not --packages-select. A selected package that depends on a
# sibling in the same repository cannot configure unless that sibling is built
# first, and --packages-select refuses to build it.
set -euo pipefail

docker exec -e BUILD_ARGS "$WORKER" bash -c '
  set -e
  source "/opt/ros/$ROS_DISTRO/setup.bash"
  colcon build \
    --base-paths $BASE_PATHS \
    --packages-up-to $PACKAGES \
    --event-handlers console_direct+ \
    $BUILD_ARGS
'
