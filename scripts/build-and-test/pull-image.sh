#!/usr/bin/env bash
# Reads IMAGE from the environment.
set -euo pipefail

docker pull "$IMAGE"
