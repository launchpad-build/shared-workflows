#!/usr/bin/env bash
# Reads PACKAGES and BUILD_ROOT from the environment.
set -uo pipefail

build_root="${BUILD_ROOT:-build}"
missing=""
for package in $PACKAGES; do
  if [ ! -d "$build_root/$package" ]; then
    missing="$missing $package"
  fi
done

if [ -n "$missing" ]; then
  echo "::error::colcon found no package named:$missing. Check the package input and base-paths."
  exit 1
fi
