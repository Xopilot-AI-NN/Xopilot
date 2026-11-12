#!/usr/bin/env bash
# Отдельный debug APK не заменяет ни production, ни ранее установленный preview.
set -euo pipefail
cd "$(dirname "$0")/.."
# При повторном запуске используем уже подготовленный локальный toolchain.
# В CI и у разработчика явно заданные переменные всегда имеют приоритет.
if [[ -d target/android-toolchain ]]; then
  export JAVA_HOME="${JAVA_HOME:-$PWD/target/android-toolchain/jdk21}"
  export ANDROID_HOME="${ANDROID_HOME:-$PWD/target/android-toolchain/sdk}"
  export ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-$ANDROID_HOME/ndk/27.2.12479018}"
  export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$PWD/target/gradle-home}"
  export PATH="$JAVA_HOME/bin:$PATH"
fi
: "${ANDROID_HOME:?Укажите Android SDK}"
: "${ANDROID_NDK_HOME:?Укажите Android NDK}"
: "${JAVA_HOME:?Укажите JDK 21}"
./scripts/prepare_runtime.sh
res=target/dx/xopilot/debug/android/app/app/src/main/res
if [[ -d "$res" ]]; then find "$res" -path '*/mipmap-*/ic_launcher.png' -delete; fi
dx build --android -p xopilot --no-default-features --features mobile --target aarch64-linux-android
node scripts/package_android.cjs --profile debug --ui-test --output target/android-ui-test.apk
