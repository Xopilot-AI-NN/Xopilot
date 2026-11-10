#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cargo fmt --all --check
cargo test --workspace --no-default-features --locked
cargo clippy --workspace --all-targets --no-default-features --locked -- -D warnings
