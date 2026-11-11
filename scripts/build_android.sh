#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:?Укажите каталог Android SDK}"
: "${ANDROID_NDK_HOME:?Укажите каталог Android NDK}"
: "${JAVA_HOME:?Укажите каталог JDK 17 или новее}"
./scripts/prepare_runtime.sh
exec dx build --android -p xopilot --no-default-features --features mobile --target aarch64-linux-android "$@"
