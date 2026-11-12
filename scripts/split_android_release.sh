#!/usr/bin/env bash
# Публикуем прежние отдельные APK по ABI, подписанные тем же постоянным ключом.
# Исходный универсальный APK сохраняется для локальной проверки сборки.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:?Укажите Android SDK}"
tools="$ANDROID_HOME/build-tools/$(ls "$ANDROID_HOME/build-tools" | sort -V | tail -n 1)"
keystore="${XOPILOT_KEYSTORE:-.signing/xopilot-release.jks}"
store_password="${XOPILOT_STORE_PASSWORD_FILE:-.signing/store-password}"
key_password="${XOPILOT_KEY_PASSWORD_FILE:-.signing/key-password}"
key_alias="${XOPILOT_KEY_ALIAS:-xopilot}"
source_apk="${1:-dist/android.apk}"
work="$(mktemp -d target/android-split-XXXXXX)"
trap 'rm -rf "$work"' EXIT
for abi in arm64-v8a x86_64; do
  if [[ "$abi" == arm64-v8a ]]; then other=x86_64; else other=arm64-v8a; fi
  cp "$source_apk" "$work/unsigned.apk"
  # zip пересобирает центральный каталог. Старые v1-подписи удаляются перед новой подписью.
  zip -dq "$work/unsigned.apk" "lib/$other/*" 'META-INF/*.SF' 'META-INF/*.RSA' 'META-INF/*.DSA' 'META-INF/MANIFEST.MF'
  "$tools/zipalign" -f -P 16 4 "$work/unsigned.apk" "$work/aligned.apk"
  "$tools/apksigner" sign --v4-signing-enabled false --ks "$keystore" --ks-key-alias "$key_alias" \
    --ks-pass "file:$store_password" --key-pass "file:$key_password" \
    --out "dist/Xopilot-Android-$abi.apk" "$work/aligned.apk"
  "$tools/apksigner" verify "dist/Xopilot-Android-$abi.apk"
  ./scripts/test.sh apk-check "dist/Xopilot-Android-$abi.apk"
done
(cd dist && sha256sum Xopilot-Android-arm64-v8a.apk Xopilot-Android-x86_64.apk > SHA256SUMS-Android.txt)
