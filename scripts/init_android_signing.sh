#!/usr/bin/env bash
# Описание: Один постоянный закрытый ключ на проект; никогда не пересоздаём его при автосборке.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p .signing
chmod 700 .signing
if [[ -f .signing/xopilot-release.jks ]]; then
  if [[ -f .signing/store-password && ! -f .signing/key-password ]]; then
    cp .signing/store-password .signing/key-password
  fi
  echo 'Постоянный ключ уже существует. Он не изменён.'
  exit 0
fi
openssl rand -base64 48 > .signing/store-password
cp .signing/store-password .signing/key-password
signing_keytool="${JAVA_HOME:+$JAVA_HOME/bin/}keytool"
"$signing_keytool" -genkeypair -keystore .signing/xopilot-release.jks -storetype PKCS12 \
  -alias xopilot -keyalg RSA -keysize 4096 -validity 10000 \
  -dname 'CN=Xopilot, OU=Release, O=Xopilot' \
  -storepass:file .signing/store-password -keypass:file .signing/store-password
chmod 600 .signing/xopilot-release.jks .signing/store-password .signing/key-password
echo 'Ключ создан в .signing. Сохраните его резервную копию; не добавляйте ключ или пароль в Git.'
