#!/usr/bin/env bash
# Reads WORKER from the environment. PACKAGES, ROS_DISTRO and BASE_PATHS reach
# the container through the environment given to docker run.
set -euo pipefail

docker exec "$WORKER" bash -c '
  set -e
  source "/opt/ros/$ROS_DISTRO/setup.bash"
  apt-get update -qq
  rosdep update -q --rosdistro "$ROS_DISTRO" 2>/dev/null \
    || { rosdep init >/dev/null; rosdep update -q --rosdistro "$ROS_DISTRO"; }
  rosdep install --from-paths $BASE_PATHS --ignore-src -r -y \
    --rosdistro "$ROS_DISTRO"
'
