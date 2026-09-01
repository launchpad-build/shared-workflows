#!/usr/bin/env bash
# Reads WORKER and BUILD_ARGS from the environment.
#
# --packages-up-to, not --packages-select. A selected package that depends on a
# sibling in the same repository cannot configure unless that sibling is built
# first, and --packages-select refuses to build it.
#
# An empty PACKAGES means build everything colcon crawls, so the selection flag
# is left off altogether rather than passed an empty argument.
set -euo pipefail

docker exec -e BUILD_ARGS "$WORKER" bash -c '
  set -e
  source "/opt/ros/$ROS_DISTRO/setup.bash"
  selection=()
  if [ -n "$PACKAGES" ]; then
    selection=(--packages-up-to $PACKAGES)
  fi
  colcon build \
    --base-paths $BASE_PATHS \
    "${selection[@]}" \
    --event-handlers console_direct+ \
    $BUILD_ARGS
'
