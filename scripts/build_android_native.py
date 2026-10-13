"""Cross-compile encrypted DB libraries bundled by the Android Flet extension.

Requires Android NDK r29, Rust Android targets and Perl for vendored OpenSSL.
No host .so, user database, model or credentials are copied into the APK.
"""
import argparse
import os
from pathlib import Path
import subprocess
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {'arm64-v8a': ('aarch64-linux-android', 'aarch64-linux-android'),
           'x86_64': ('x86_64-linux-android', 'x86_64-linux-android')}
DESTINATION = ROOT / 'extensions/flet_xopilot_mobile/src/flutter/flet_xopilot_mobile/android/src/main/jniLibs'


def python_library(abi):
    # Match the runtime pinned by Flet 1.0.3 / serious_python 5.0.0. The DB must
    # have a DT_NEEDED for libpython, rather than rely on global dlopen symbols.
    root = ROOT / 'build/android-native/python' / abi
    root.mkdir(parents=True, exist_ok=True)
    library = root / 'libpython3.14.so'
    if library.exists(): return root
    archive = root / 'python.tar.gz'
    url = f'https://github.com/flet-dev/python-build/releases/download/20260921/python-android-dart-3.14.7-{abi}.tar.gz'
    if not archive.exists():
        temporary = archive.with_suffix('.part')
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as output:
            shutil.copyfileobj(response, output)
        temporary.replace(archive)
    with tarfile.open(archive) as source:
        member = source.getmember('./libpython3.14.so')
        if not member.isfile(): raise ValueError('Invalid Python runtime library')
        with source.extractfile(member) as data, library.open('wb') as output:
            shutil.copyfileobj(data, output)
    return root


def build(abi, ndk):
    target, clang_target = TARGETS[abi]
    toolchain = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    compiler = toolchain / f'{clang_target}24-clang'
    if not compiler.is_file():
        raise RuntimeError(f'Android NDK compiler not found: {compiler}')
    build_dir = ROOT / 'build/android-native'
    build_dir.mkdir(parents=True, exist_ok=True)
    config = build_dir / 'pyo3-config.txt'
    python_dir = python_library(abi)
    config.write_text('implementation=CPython\nversion=3.14\nshared=true\nabi3=false\npointer_width=64\n' + f'lib_name=python3.14\nlib_dir={python_dir}\n', encoding='utf-8')
    env = dict(os.environ)
    env.update(PYO3_CONFIG_FILE=str(config), ANDROID_NDK_ROOT=str(ndk), ANDROID_NDK_HOME=str(ndk))
    env['PATH'] = str(toolchain) + os.pathsep + env.get('PATH', '')
    env['CC_' + target.replace('-', '_')] = str(compiler)
    env['AR_' + target.replace('-', '_')] = str(toolchain / 'llvm-ar')
    env['CARGO_TARGET_' + target.upper().replace('-', '_') + '_LINKER'] = str(compiler)
    # 16 KiB page support for modern Android devices; SQLite/OpenSSL are linked
    # statically into this shared object.
    env['CARGO_TARGET_' + target.upper().replace('-', '_') + '_RUSTFLAGS'] = '-C link-arg=-Wl,-z,max-page-size=16384'
    subprocess.run(['cargo', 'build', '--jobs', '1', '--locked', '--release', '--no-default-features',
                    '--manifest-path', str(ROOT/'Services/Cargo.toml'), '--target', target],
                   cwd=ROOT, env=env, check=True)
    source = ROOT / 'Services/target' / target / 'release/libadvanced_xopilot.so'
    destination = DESTINATION / abi / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    print(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, default=Path(os.environ.get('ANDROID_NDK_ROOT', '/opt/android-sdk/ndk/29.0.14206865')))
    parser.add_argument('--arch', choices=TARGETS, nargs='+', default=list(TARGETS))
    args = parser.parse_args()
    for abi in args.arch: build(abi, args.ndk.resolve())


if __name__ == '__main__': main()
