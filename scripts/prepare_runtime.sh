#!/usr/bin/env bash
# Описание: Закреплённый официальный C API для Linux и Android, только при сборке.
set -euo pipefail
cd "$(dirname "$0")/.."
archive="${XOPILOT_LITERT_ARCHIVE:-${TMPDIR:-/tmp}/xopilot-litert-capi-1.0.0.zip}"
digest=1d430d80eaf536f696a4922270ba55eb3d112189ac198c3066d487a45e3b4d4c
if [[ ! -f "$archive" ]]; then
  curl --fail --location --retry 3 --output "$archive.part" https://github.com/google-ai-edge/LiteRT-LM/releases/download/v0.19.1/litert_lm_c_api-1.0.0.zip
  mv "$archive.part" "$archive"
fi
printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status
mkdir -p App/native
unzip -oq "$archive" 'lib/linux_*/*' 'lib/android_*/*' 'lib/windows_x86_64/*' 'LICENSE' 'licenses/*' -d App/native/sdk
for platform in linux_x86_64 linux_arm64 android_arm64 android_x86_64; do
  mkdir -p "App/native/$platform"
  # Официальные .so приходят с правами 0555: при повторной сборке заменяем файл, а не пишем в него.
  cp -f "App/native/sdk/lib/$platform/liblitert-lm.so" "App/native/$platform/"
done
mkdir -p App/native/windows_x86_64
cp -f App/native/sdk/lib/windows_x86_64/bin/litert-lm.dll App/native/windows_x86_64/
(cd App/native/sdk && zip -qr ../runtime-licenses.zip LICENSE licenses)
printf 'LiteRT C API 1.0.0 готов для Linux и Android.\n'
