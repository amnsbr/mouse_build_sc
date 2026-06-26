#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

git submodule update --init --recursive # to get the mouse_connectivity_models submodule

mkdir -p aba_cache
docker build --platform linux/amd64 -t amnsbr/mouse_build_sc .
