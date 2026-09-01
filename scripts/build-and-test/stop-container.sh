#!/usr/bin/env bash
# Reads WORKER from the environment.
set -uo pipefail

docker rm -f "$WORKER" || true
