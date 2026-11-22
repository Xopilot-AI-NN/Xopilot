#!/usr/bin/env bash
# Собирает основной Xopilot. Dev-режим доступен только с явным флагом.
set -euo pipefail
cd "$(dirname "$0")/.."
case "$#:${1:-}" in
  0:) dx build --desktop --release -p xopilot ;;
  1:--dev-test) dx build --desktop -p xopilot --features dev-test ;;
  *) echo "Использование: $0 [--dev-test]" >&2; exit 2 ;;
esac
