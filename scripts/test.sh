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
    ./scripts/build_desktop.sh --dev-test
    node scripts/check-ui.cjs
    ;;
  apk)
    if [[ $# -eq 1 ]]; then
      ./scripts/build_android.sh --dev-test
    fi
    node scripts/check-android-ui.cjs "${2:-target/xopilot-dev-test.apk}"
    ;;
  apk-check)
    node scripts/check-android-apk.cjs "${2:-dist/android.apk}"
    ;;
  bridges)
    node scripts/check-mobile-bridges.cjs
    node --test scripts/check-voice.cjs scripts/check-speech.cjs
    ;;
  flowmap)
    node --test tools/flowmap/model.test.cjs
    cargo build --locked -p xopilot --example flowmap_nodes_demo --no-default-features
    node tools/flowmap/check-trace.cjs
    node --test tools/flowmap/launcher.test.cjs
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
  team)
    # Отдельная временная база создаётся примером; личная история не используется.
    if [[ $# -ne 2 ]]; then
      echo 'Использование: ./scripts/test.sh team /путь/gemma-4-E2B-it.litertlm' >&2
      exit 2
    fi
    cargo run -p xopilot --no-default-features --locked --example local_team_smoke -- "$2"
    ;;
  *) echo 'Режимы: quick | full | ui | bridges | flowmap | apk | apk-check [путь/к/APK] | model /путь/к/модели | team /путь/к/модели' >&2; exit 2 ;;
esac
echo 'Проверки завершились успешно.'
