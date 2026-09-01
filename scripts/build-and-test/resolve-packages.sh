#!/usr/bin/env bash
# Reads PACKAGES, BASE_PATHS, WORKER and PACKAGE_LIST from the environment.
#
# Every later step works from the resolved list rather than from the input, so
# the two selection modes share one code path. An explicit input is written out
# as it stands. An empty input means build everything, and the list then comes
# from colcon's own crawl over BASE_PATHS.
#
# colcon list is the right source for that crawl: colcon build shares the same
# crawler, so the two agree on where colcon stops descending, and the guard on
# the build directories then checks the same set the build was given.
#
# With no input list there is nothing to check a bad base path against, so the
# crawl itself is checked twice. A base path holding no package fails. So does a
# crawl that stopped at a package with more packages buried under it, which is
# what a repository carrying a package.xml at its root does to the default base
# path: colcon builds the root package alone and reports a clean run. Failing
# there is deliberate, because that green is the outcome this guard exists to
# stop. A repository that vendors a package.xml as test data has to point
# base-paths below it or name its packages explicitly.
#
# Neither check runs on the explicit path, where the per-package
# build-directory guard already catches both.
#
# The word splitting of PACKAGES is deliberate: the input is a space-separated
# list, so it reaches printf as one word per package.
set -euo pipefail

if [ -n "${PACKAGES// /}" ]; then
  # shellcheck disable=SC2086
  printf '%s\n' $PACKAGES > "$PACKAGE_LIST"
else
  docker exec "$WORKER" bash -c '
    set -e
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    colcon list --base-paths $BASE_PATHS --names-only
  ' | sort > "$PACKAGE_LIST"

  buried="$(docker exec "$WORKER" bash -c '
    set -e
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    for path in $(colcon list --base-paths $BASE_PATHS --paths-only); do
      find "$path" -mindepth 2 -name package.xml -printf "%h\n" | while read -r found; do
        [ -f "$found/COLCON_IGNORE" ] || echo "$found"
      done
    done
  ' | sort)"
  if [ -n "$buried" ]; then
    echo "::error::colcon stopped descending at a package and never saw the packages below it, so the crawl covers less than the repository. Point base-paths below the outer package, or name the packages explicitly. Directories colcon missed:"
    echo "$buried"
    exit 1
  fi
fi

count="$(grep -c . "$PACKAGE_LIST" || true)"
if [ "$count" -eq 0 ]; then
  echo "::error::colcon found no package under base-paths '$BASE_PATHS'. Check the base-paths input."
  exit 1
fi

echo "$count package(s) selected:"
cat "$PACKAGE_LIST"
