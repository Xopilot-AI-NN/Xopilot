"""Materialize a GitHub secret keystore without logging its contents."""
import base64
import os
from pathlib import Path


def main():
    secret = os.environ.get('APK_KEYSTORE_BASE64', '')
    names = ('FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD', 'FLET_ANDROID_SIGNING_KEY_PASSWORD', 'FLET_ANDROID_SIGNING_KEY_ALIAS')
    if not secret:
        if any(os.environ.get(name) for name in names):
            raise SystemExit('Incomplete Android signing secrets')
        print('No release keystore configured; APKs use a disposable debug signature.')
        return
    if not all(os.environ.get(name) for name in names):
        raise SystemExit('All four Android signing secrets must be configured')
    path = Path(os.environ['RUNNER_TEMP'])/'xopilot-upload.jks'
    try:
        data = base64.b64decode(secret, validate=True)
    except ValueError:
        raise SystemExit('Invalid base64 keystore') from None
    if not 32 <= len(data) <= 1024*1024:
        raise SystemExit('Invalid keystore size')
    with path.open('wb') as file:
        os.chmod(path, 0o600)
        file.write(data)
    with Path(os.environ['GITHUB_ENV']).open('a') as file:
        file.write(f'FLET_ANDROID_SIGNING_KEY_STORE={path}\n')


if __name__ == '__main__':
    main()
