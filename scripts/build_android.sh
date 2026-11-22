#!/usr/bin/env bash
# Собирает Xopilot с постоянной подписью. --dev-test включает изолированный режим UI-тестов.
set -euo pipefail
cd "$(dirname "$0")/.."
dev_test=false
case "$#:${1:-}" in
  0:) ;;
  1:--dev-test) dev_test=true ;;
  *) echo "Использование: $0 [--dev-test]" >&2; exit 2 ;;
esac
if [[ -d target/android-toolchain ]]; then
  export JAVA_HOME="${JAVA_HOME:-$PWD/target/android-toolchain/jdk21}"
  export ANDROID_HOME="${ANDROID_HOME:-$PWD/target/android-toolchain/sdk}"
  export ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-$ANDROID_HOME/ndk/27.2.12479018}"
  export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$PWD/target/gradle-home}"
fi
: "${ANDROID_HOME:?Укажите каталог Android SDK}"
: "${ANDROID_NDK_HOME:?Укажите каталог Android NDK}"
: "${JAVA_HOME:?Укажите каталог JDK 21}"
export PATH="$JAVA_HOME/bin:$PATH"
profile=release
features=mobile
build_flags=(--release)
package_flags=()
if $dev_test; then
  profile=debug
  features=mobile,dev-test
  build_flags=()
  package_flags=(--dev-test)
fi
./scripts/prepare_runtime.sh
project="target/dx/xopilot/$profile/android/app"
mkdir -p target
native_bundle="$(mktemp -d target/android-native-XXXXXX)"
trap 'rm -rf "$native_bundle"' EXIT
# Собираем обе ABI в промежуточный APK, затем выпускаем отдельные файлы с прежними именами.
# Копия jniLibs не даёт второй сборке DX затереть библиотеку первой архитектуры.
for target in ${XOPILOT_ANDROID_TARGETS:-aarch64-linux-android x86_64-linux-android}; do
  case "$target" in
    aarch64-linux-android) abi=arm64-v8a ;;
    x86_64-linux-android) abi=x86_64 ;;
    *) echo "Неподдерживаемая Android-архитектура: $target" >&2; exit 2 ;;
  esac
  # DX сначала собирает свой служебный APK и возвращает стандартные WebP-иконки.
  # Убираем PNG от предыдущей упаковки, чтобы повторный запуск не создавал два
  # ресурса с одним Android ID. Фирменную иконку вернём после сборки обеих ABI.
  res="$project/app/src/main/res"
  if [[ -d "$res" ]]; then
    find "$res" -path '*/mipmap-*/ic_launcher.png' -delete
  fi
  dx build --android "${build_flags[@]}" -p xopilot --no-default-features --features "$features" --target "$target"
  mkdir -p "$native_bundle/$abi"
  cp "$project/app/src/main/jniLibs/$abi/"*.so "$native_bundle/$abi/"
done
rm -rf "$project/app/src/main/jniLibs"
cp -R "$native_bundle" "$project/app/src/main/jniLibs"
node scripts/package_android.cjs --profile "$profile" "${package_flags[@]}"
if ! $dev_test; then
  ./scripts/split_android_release.sh
fi
