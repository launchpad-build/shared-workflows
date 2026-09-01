#!/usr/bin/env bash
# Reads WORKER from the environment. PACKAGES, ROS_DISTRO and BASE_PATHS reach
# the container through the environment given to docker run.
#
# rosdep runs over the closure colcon will actually build, not over every
# package under BASE_PATHS. A repository holding many packages declares
# dependencies the selected packages never need, and one of those keys being
# absent from rosdistro fails the job before anything is built. Scoping to the
# closure also stops the step installing heavy dependencies, such as the moveit
# set, for packages the build never touches.
#
# colcon list falls back to BASE_PATHS when it cannot resolve the selection, so
# a mistyped package name still fails at the build step with colcon's own
# message rather than here.
#
# With no selection the closure is the whole crawl, so the same query runs
# without --packages-up-to. That still asks colcon rather than handing rosdep
# the base paths, so rosdep sees only what colcon crawled.
set -euo pipefail

docker exec "$WORKER" bash -c '
  set -e
  source "/opt/ros/$ROS_DISTRO/setup.bash"
  apt-get update -qq
  [ -d "$HOME/.ros/rosdep/sources.cache" ] \
    || rosdep update -q --rosdistro "$ROS_DISTRO" 2>/dev/null \
    || { rosdep init >/dev/null; rosdep update -q --rosdistro "$ROS_DISTRO"; }

  selection=()
  if [ -n "$PACKAGES" ]; then
    selection=(--packages-up-to $PACKAGES)
  fi
  paths="$(colcon list --base-paths $BASE_PATHS "${selection[@]}" \
    --paths-only 2>/dev/null || true)"
  if [ -z "$paths" ]; then
    echo "colcon could not resolve the selection, so rosdep falls back to the base paths."
    paths="$BASE_PATHS"
  fi

  rosdep install --from-paths $paths --ignore-src -r -y \
    --rosdistro "$ROS_DISTRO"
'
