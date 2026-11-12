#!/usr/bin/env bash
# Описание: Одна команда для проверки сервисов, интерфейса или настоящей модели.
set -euo pipefail
cd "$(dirname "$0")/.."
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}"
case "${1:-quick}" in
  quick)
    cargo test --workspace --no-default-features --locked
    ;;
  full)
    ./scripts/check.sh
    ;;
  ui)
    dx build --desktop -p xopilot --example interface_interaction
    node scripts/check-ui.cjs
    ;;
  apk)
    ./scripts/build_android_test.sh
    node scripts/check-android-ui.cjs "${2:-target/android-ui-test.apk}"
    ;;
  apk-check)
    node scripts/check-android-apk.cjs "${2:-target/dx/xopilot/debug/android/app/app/build/outputs/apk/debug/app-debug.apk}"
    ;;
  bridges)
    node scripts/check-mobile-bridges.cjs
    ;;
  model)
    if [[ $# -ne 2 ]]; then
      echo 'Использование: ./scripts/test.sh model /путь/gemma-4-E2B-it.litertlm' >&2
      exit 2
    fi
    task_data="$(mktemp -d "${TMPDIR:-/tmp}/xopilot-model-test-XXXXXX")"
    trap 'rm -rf "$task_data"' EXIT
    export XOPILOT_DATA_DIR="$task_data"
    cargo run -p xopilot --no-default-features --locked --example local_context_smoke -- "$2"
    cargo run -p xopilot --no-default-features --locked --example local_agent_smoke -- "$2"
    cargo run -p xopilot --no-default-features --locked --example local_canvas_smoke -- "$2"
    ;;
  *) echo 'Режимы: quick | full | ui | bridges | apk | apk-check [путь/к/APK] | model /путь/к/модели' >&2; exit 2 ;;
esac
echo 'Проверки завершились успешно.'
