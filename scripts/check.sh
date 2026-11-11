#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}"
# Не допускаем возврата старых исходников и байткода в дерево приложения.
legacy="$(find App/app App/services App/settings Services/src scripts tests \( -name '*.py' -o -name '*.pyc' -o -name '__pycache__' \) -print -quit)"
if [[ -n "$legacy" ]]; then
  echo "Обнаружен устаревший файл: $legacy" >&2
  exit 1
fi
cargo fmt --all --check
cargo test --workspace --no-default-features --locked
cargo clippy --workspace --all-targets --no-default-features --locked -- -D warnings
