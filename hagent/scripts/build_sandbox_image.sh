#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${HAGENT_SANDBOX_IMAGE:-hagent/sandbox:dev}"
ROOT="$(cd "$(dirname "$0")/../sandbox/docker/images/hagent-base" && pwd)"

echo "[build_sandbox_image] building ${IMAGE_TAG} from ${ROOT}"
docker build -t "${IMAGE_TAG}" "${ROOT}"
docker images "${IMAGE_TAG}"
