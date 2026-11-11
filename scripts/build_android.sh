#!/usr/bin/env bash
# Описание: Release APK из Rust с прежним application ID и постоянной подписью.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${ANDROID_HOME:?Укажите каталог Android SDK}"
: "${ANDROID_NDK_HOME:?Укажите каталог Android NDK}"
: "${JAVA_HOME:?Укажите каталог JDK 21}"
./scripts/prepare_runtime.sh
# Как в прежнем пререлизе, сохраняем ARM64 и x86_64, но упаковываем их в один android.apk.
# Копия jniLibs не даёт второй сборке DX затереть библиотеку первой архитектуры.
native_bundle=target/android-native-bundle
rm -rf "$native_bundle"
mkdir -p "$native_bundle"
for target in ${XOPILOT_ANDROID_TARGETS:-aarch64-linux-android x86_64-linux-android}; do
  case "$target" in
    aarch64-linux-android) abi=arm64-v8a ;;
    x86_64-linux-android) abi=x86_64 ;;
    *) echo "Неподдерживаемая Android-архитектура: $target" >&2; exit 2 ;;
  esac
  # DX сначала собирает свой служебный APK и возвращает стандартные WebP-иконки.
  # Убираем PNG от предыдущей упаковки, чтобы повторный запуск не создавал два
  # ресурса с одним Android ID. Фирменную иконку вернём после сборки обеих ABI.
  res=target/dx/xopilot/release/android/app/app/src/main/res
  if [[ -d "$res" ]]; then
    find "$res" -path '*/mipmap-*/ic_launcher.png' -delete
  fi
  dx build --android --release -p xopilot --no-default-features --features mobile --target "$target" "$@"
  mkdir -p "$native_bundle/$abi"
  cp target/dx/xopilot/release/android/app/app/src/main/jniLibs/"$abi"/*.so "$native_bundle/$abi/"
done
rm -rf target/dx/xopilot/release/android/app/app/src/main/jniLibs
cp -R "$native_bundle" target/dx/xopilot/release/android/app/app/src/main/jniLibs
node scripts/package_android.cjs --profile release
