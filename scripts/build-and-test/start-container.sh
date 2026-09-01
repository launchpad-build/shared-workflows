#!/usr/bin/env bash
# Reads WORKER, IMAGE, GITHUB_WORKSPACE, PACKAGES, ROS_DISTRO and BASE_PATHS.
#
# One long-lived container serves every later step. A package installed by
# rosdep lives only inside the running container, so a fresh docker run per
# step would throw those installs away before the build could use them.
set -euo pipefail

docker run -d --name "$WORKER" \
  -v "$GITHUB_WORKSPACE":/ws -w /ws \
  -e PACKAGES -e ROS_DISTRO -e BASE_PATHS \
  "$IMAGE" sleep infinity
