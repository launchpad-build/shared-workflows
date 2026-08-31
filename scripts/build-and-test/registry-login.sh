#!/usr/bin/env bash
# Reads REGISTRY, REGISTRY_USER and REGISTRY_TOKEN from the environment.
set -euo pipefail

printf '%s' "$REGISTRY_TOKEN" \
  | docker login "$REGISTRY" -u "$REGISTRY_USER" --password-stdin
