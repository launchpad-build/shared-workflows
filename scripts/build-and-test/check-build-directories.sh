#!/usr/bin/env bash
# Reads PACKAGE_LIST and BUILD_ROOT from the environment.
#
# The list is the packages the run covers, whether they came from the package
# input or from colcon's crawl. A missing list, or an empty one, fails the job:
# with nothing to check against, a broken crawl and a clean run look the same,
# which is the green-on-nothing-built outcome this guard exists to stop.
set -uo pipefail

build_root="${BUILD_ROOT:-build}"
list="${PACKAGE_LIST:-}"

if [ -z "$list" ] || [ ! -s "$list" ]; then
  echo "::error::No package list was resolved, so no build directory could be checked."
  exit 1
fi

missing=""
while read -r package; do
  if [ -n "$package" ] && [ ! -d "$build_root/$package" ]; then
    missing="$missing $package"
  fi
done < "$list"

if [ -n "$missing" ]; then
  echo "::error::colcon found no package named:$missing. Check the package input and base-paths."
  exit 1
fi
