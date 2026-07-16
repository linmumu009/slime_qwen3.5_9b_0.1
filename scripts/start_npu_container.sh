#!/usr/bin/env bash
set -euo pipefail

: "${WORK_ROOT:?Set WORK_ROOT to the persistent experiment directory}"
: "${MODEL_DIR:?Set MODEL_DIR to the local Qwen3.5-9B directory}"

CONTAINER_NAME="${CONTAINER_NAME:-slime-qwen35-rl-dev}"
IMAGE="${IMAGE:-quay.io/ascend/ms-swift@sha256:0116ad4e0b2b440b3ff7353f24fca741a3173b1e9fcea595c99d358347f47952}"

for path in "${WORK_ROOT}" "${MODEL_DIR}" /usr/local/Ascend/driver /usr/local/Ascend/add-ons; do
  if [[ ! -e "${path}" ]]; then
    echo "Required path does not exist: ${path}" >&2
    exit 1
  fi
done

if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
  echo "Container already exists: ${CONTAINER_NAME}" >&2
  exit 1
fi

device_args=(
  --device /dev/davinci_manager
  --device /dev/devmm_svm
  --device /dev/hisi_hdc
)
for index in $(seq 0 15); do
  device="/dev/davinci${index}"
  if [[ ! -e "${device}" ]]; then
    echo "Required NPU device does not exist: ${device}" >&2
    exit 1
  fi
  device_args+=(--device "${device}")
done

docker run -d \
  --name "${CONTAINER_NAME}" \
  --init \
  --network host \
  --ipc host \
  --shm-size 128g \
  "${device_args[@]}" \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /usr/local/Ascend/add-ons:/usr/local/Ascend/add-ons:ro \
  -v /usr/local/sbin:/usr/local/sbin:ro \
  -v "${WORK_ROOT}:/workspace" \
  -v "${MODEL_DIR}:/models/Qwen3.5-9B:ro" \
  "${IMAGE}" \
  sleep infinity
