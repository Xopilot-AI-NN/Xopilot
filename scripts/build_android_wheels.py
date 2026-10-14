"""
Файл: /scripts/build_android_wheels.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Исправленные Android-библиотеки из закреплённых исходников Flet Mobile Forge.
"""
import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
FORGE_COMMIT = '0fadbfab0d63d11164030dfddc955ed980e32e2c'
CROSSENV_COMMIT = 'e5e615651f794d060d9484eab463861fef2a2019'
VERSIONS = {'pillow': '12.3.0', 'cryptography': '50.0.2', 'openssl': '3.5.7'}
ABIS = ('arm64-v8a', 'x86_64')
SOURCES = {
    'python-android-mobile-forge-3.14.6.tar.gz': (
        'https://github.com/flet-dev/python-build/releases/download/20260730/python-android-mobile-forge-3.14.6.tar.gz',
        '48383c67932f53bd1e767b3b27e8fddcf3f3c61c31513e6c5382654be165c864'),
    'Pillow-12.3.0.tar.gz': (
        'https://files.pythonhosted.org/packages/1c/3d/bb7fca845737cf9d7dbde16ed1843984665ff2e0a518f5db43e77ec540b9/pillow-12.3.0.tar.gz',
        '3b8182a766685eaa002637e28b4ec8d6b18819a0c71f579bf0dbaa5830297cce'),
    'cryptography-50.0.2.tar.gz': (
        'https://files.pythonhosted.org/packages/9d/af/182eb91b0df3fe75c4d9f26fe70684569566745f6ba7e5c9c73a862c5252/cryptography-50.0.2.tar.gz',
        '7b46165bb56eb4704e2eaaf86f3c940d19154535d9b0ca7d6d590b04060e00d5'),
}


def wheel_metadata(path):
    with ZipFile(path) as wheel:
        entries = [n for n in wheel.namelist() if n.endswith('.dist-info/METADATA')]
        if len(entries) != 1:
            raise ValueError(f'Invalid wheel metadata: {path.name}')
        return BytesParser().parsebytes(wheel.read(entries[0]))


def validate_wheelhouse(directory, arch=ABIS):
    selected = []
    for abi in arch:
        tag = abi.replace('-', '_')
        for name, version in VERSIONS.items():
            matches = list(directory.glob(f'{name}-{version}-*-android_24_{tag}.whl'))
            if len(matches) != 1:
                raise ValueError(f'Missing/ambiguous patched Android wheel: {name} {version} {abi}')
            metadata = wheel_metadata(matches[0])
            if metadata['Name'].lower() != name or metadata['Version'] != version:
                raise ValueError(f'Incorrect patched wheel version: {matches[0].name}')
            selected.append(matches[0])
    return selected


def download_checked(url, path, digest):
    if not path.exists():
        temporary = path.with_suffix('.part')
        try:
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    with path.open('rb') as source:
        actual = hashlib.file_digest(source, 'sha256').hexdigest()
    if actual != digest:
        raise ValueError(f'Source checksum mismatch: {path.name}; remove the cached file and retry')


def build(directory, ndk, arch=ABIS):
    directory = directory.resolve()
    try:
        return validate_wheelhouse(directory, arch)
    except ValueError:
        pass
    # All source/build state stays inside the generated build tree.
    workspace = ROOT / 'build/android-wheel-build'
    workspace.mkdir(parents=True, exist_ok=True)
    forge = workspace / 'mobile-forge'
    if not forge.exists():
        subprocess.run(['git', 'clone', '--no-checkout', 'https://github.com/flet-dev/mobile-forge.git', str(forge)], check=True)
    subprocess.run(['git', 'checkout', '--detach', FORGE_COMMIT], cwd=forge, check=True)
    config = forge / 'pyproject.toml'
    text = config.read_text().replace('crossenv@flet', 'crossenv@' + CROSSENV_COMMIT)
    config.write_text(text)
    downloads = forge / 'downloads'
    downloads.mkdir(exist_ok=True)
    for name, (url, digest) in SOURCES.items():
        download_checked(url, downloads / name, digest)
    tools = workspace / 'tools'
    if not (tools / 'bin/uv').exists():
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--target', str(tools), 'uv==0.13.1'], check=True)
    env = dict(os.environ, NDK_HOME=str(ndk.resolve()), ANDROID_ABIS=' '.join(arch),
               CARGO_BUILD_JOBS='2', CPU_COUNT='2')
    env['PATH'] = str(tools / 'bin') + os.pathsep + env.get('PATH', '')
    # Fixed command strings; paths/user input travel only as environment values.
    subprocess.run(['bash', '-e', '-c', 'source ./setup.sh 3.14 android\nforge android pillow:12.3.0 cryptography:50.0.2'],
                   cwd=forge, env=env, check=True)
    directory.mkdir(parents=True, exist_ok=True)
    files = validate_wheelhouse(forge / 'dist', arch)
    for path in files:
        shutil.copy2(path, directory / path.name)
    files = validate_wheelhouse(directory, arch)
    record = {'forge_commit': FORGE_COMMIT, 'crossenv_commit': CROSSENV_COMMIT, 'versions': VERSIONS,
              'sources': {name: digest for name, (_, digest) in SOURCES.items()},
              'wheels': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (directory / 'provenance.json').write_text(json.dumps(record, indent=2) + '\n')
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel-house', type=Path, default=ROOT / 'build/android-wheels')
    parser.add_argument('--ndk', type=Path, default=Path('/opt/android-sdk/ndk/29.0.14206865'))
    parser.add_argument('--arch', nargs='+', choices=ABIS, default=list(ABIS))
    args = parser.parse_args()
    for path in build(args.wheel_house, args.ndk, args.arch):
        print(path)
