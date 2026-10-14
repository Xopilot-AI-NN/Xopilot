"""
Файл: /scripts/verify_android_apk.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Состав APK, исправленные зависимости и ABI; проверка пакета не заменяет проверку устройства.
"""
import argparse
import hashlib
import io
import re
import subprocess
from pathlib import Path
import struct
import zipfile
from email.parser import BytesParser

PATCHED_DEPENDENCIES = {'pillow': '12.3.0', 'cryptography': '50.0.2'}
OPENSSL_VERSION = '3.5.7'


def verify_dependencies(data):
    """Inspect the installed metadata, not just requirements or wheel names."""
    versions = {}
    with zipfile.ZipFile(io.BytesIO(data)) as packages:
        for name in packages.namelist():
            if name.endswith('.dist-info/METADATA'):
                meta = BytesParser().parsebytes(packages.read(name))
                key = (meta['Name'] or '').lower()
                if key in PATCHED_DEPENDENCIES:
                    if key in versions:
                        raise RuntimeError(f'Duplicate Android dependency metadata: {key}')
                    versions[key] = meta['Version']
    for name, expected in PATCHED_DEPENDENCIES.items():
        if versions.get(name) != expected:
            raise RuntimeError(f'Unsafe/unexpected Android dependency: {name}={versions.get(name)}, expected {expected}')
    return versions


def verify_openssl(data):
    # OpenSSL is supplied by the Flet Python runtime, not installed as a Python
    # distribution. Inspect the actual shared library shipped in the APK.
    versions = set(re.findall(rb'OpenSSL ([0-9]+\.[0-9]+\.[0-9]+) ', data))
    if versions != {OPENSSL_VERSION.encode('ascii')}:
        raise RuntimeError(f'Unexpected Android OpenSSL library version: {versions}')

MACHINES = {'arm64-v8a': 183, 'x86_64': 62}


def dex_defined_methods(data):
    """Read defined (not merely referenced) method names from a standard DEX."""
    if not data.startswith(b'dex\n'):raise RuntimeError('Unexpected Android DEX format')
    def uleb(offset):
        result=shift=0
        while True:
            value=data[offset];offset+=1;result|=(value&127)<<shift
            if not value&128:return result,offset
            shift+=7
            if shift>28:raise RuntimeError('Invalid DEX integer')
    def table(offset):return struct.unpack_from('<II',data,offset)
    count,offset=table(56)
    strings=[]
    for i in range(count):
        _,start=uleb(struct.unpack_from('<I',data,offset+i*4)[0])
        strings.append(data[start:data.index(b'\0',start)].decode('utf-8',errors='replace'))
    count,offset=table(64)
    types=[strings[struct.unpack_from('<I',data,offset+i*4)[0]] for i in range(count)]
    count,offset=table(88)
    methods=[(types[c],strings[n]) for c,_,n in
             (struct.unpack_from('<HHI',data,offset+i*8) for i in range(count))]
    count,offset=table(96)
    defined=set()
    for i in range(count):
        start=struct.unpack_from('<I',data,offset+i*32+24)[0]
        if not start:continue
        counts=[]
        for _ in range(4):value,start=uleb(start);counts.append(value)
        for _ in range(counts[0]+counts[1]):
            _,start=uleb(start);_,start=uleb(start)
        for size in counts[2:]:
            identifier=0
            for _ in range(size):
                delta,start=uleb(start);identifier+=delta
                _,start=uleb(start);code,start=uleb(start)
                if code:defined.add(methods[identifier])
    return defined


def verify_litert_jni(apk):
    methods=set()
    for name in apk.namelist():
        if re.fullmatch(r'classes\d*\.dex',name):methods.update(dex_defined_methods(apk.read(name)))
    required={'ThinkingConfig':('getEnableThinking','getThinkingTokenBudget'),
              'SamplerConfig':('getTopK','getTopP','getTemperature','getSeed')}
    for cls,names in required.items():
        for name in names:
            if ('Lcom/google/ai/edge/litertlm/'+cls+';',name) not in methods:
                raise RuntimeError(f'R8 removed/renamed LiteRT JNI method: {cls}.{name}')


def verify(path, aapt=None, launcher_foreground=None):
    with zipfile.ZipFile(path) as apk:
        if apk.testzip() is not None:
            raise RuntimeError('Corrupt APK archive')
        verify_litert_jni(apk)
        dependencies = verify_dependencies(apk.read('assets/sitepackages.zip'))
        abis = {name.split('/')[1] for name in apk.namelist() if name.startswith('lib/')}
        if len(abis) != 1 or not abis <= MACHINES.keys():
            raise RuntimeError(f'Expected one supported ABI, found {abis}')
        abi = next(iter(abis))
        verify_openssl(apk.read(f'lib/{abi}/libcrypto_python.so'))
        required = ('libadvanced_xopilot.so', 'libpython3.14.so', 'liblitertlm_jni.so', 'libflutter.so')
        for library in required:
            if f'lib/{abi}/{library}' not in apk.namelist():
                raise RuntimeError(f'Missing native library: {library}')
        for name in apk.namelist():
            if not name.startswith(f'lib/{abi}/') or not name.endswith('.so'): continue
            data = apk.read(name)
            if data[:5] != b'\x7fELF\x02' or struct.unpack_from('<H', data, 18)[0] != MACHINES[abi]:
                raise RuntimeError(f'Wrong ELF architecture: {name}')
            offset = struct.unpack_from('<Q', data, 32)[0]
            size, count = struct.unpack_from('<HH', data, 54)
            for index in range(count):
                header = offset + index * size
                kind = struct.unpack_from('<I', data, header)[0]
                alignment = struct.unpack_from('<Q', data, header + 48)[0]
                if kind == 1 and alignment < 16384:
                    raise RuntimeError(f'Native library lacks 16 KiB page alignment: {name}')
        with zipfile.ZipFile(io.BytesIO(apk.read('assets/app.zip'))) as app:
            forbidden = [name for name in app.namelist()
                         if name.endswith(('.so', '.pyd', '.db', '.sqlite', '.sqlite3', '.gguf', '.litertlm', '.onnx'))
                         or Path(name).name.startswith(('client_secret_', '.env'))
                         or name.startswith('data/')]
            if forbidden:
                raise RuntimeError(f'Unexpected native library, model or user data in Python app: {forbidden}')
            for module in ('App.pyc', 'services/mobile_runtime.pyc', 'services/mobile_litert.pyc', 'services/mobile_audio.pyc',
                           'services/external_browser.pyc', 'services/billing.pyc', 'services/image_safety.pyc'):
                if module not in app.namelist():
                    raise RuntimeError(f'Missing mobile module: {module}')
        with path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if launcher_foreground:
            from PIL import Image
            with Image.open(launcher_foreground) as source:
                expected = source.convert('RGBA')
                size, pixels = expected.size, expected.tobytes()
            found = False
            for name in apk.namelist():
                if not name.startswith('res/') or not name.endswith('.png'):
                    continue
                with Image.open(io.BytesIO(apk.read(name))) as candidate:
                    if candidate.size == size and candidate.convert('RGBA').tobytes() == pixels:
                        found = True
                        break
            if not found:
                raise RuntimeError('Generated Xopilot launcher artwork is absent from the APK')
        if aapt:
            badging = subprocess.check_output([str(aapt), 'dump', 'badging', str(path)], text=True)
            if "sdkVersion:'26'" not in badging:
                raise RuntimeError('Unexpected Android minimum SDK')
            for permission in ('READ_EXTERNAL_STORAGE', 'WRITE_EXTERNAL_STORAGE'):
                if f'android.permission.{permission}' in badging:
                    raise RuntimeError(f'Unexpected shared-storage permission: {permission}')
            if re.search(r"^\s*uses-feature: name='android.hardware.(camera[^']*|microphone|touchscreen)'", badging, re.MULTILINE):
                raise RuntimeError('Camera, microphone or touchscreen became mandatory during manifest merge')
            tree = subprocess.check_output([str(aapt), 'dump', 'xmltree', str(path), 'AndroidManifest.xml'], text=True)
            if not re.search(r'android:icon[^\n]*=@0x[0-9a-f]+', tree):
                raise RuntimeError('Android application icon is missing')
            if not re.search(r'android:allowBackup[^\n]*=\(type 0x12\)0x0\s*$', tree, re.MULTILINE):
                raise RuntimeError('Android backup must be disabled')
            if not re.search(r'android:resizeableActivity[^\n]*=\(type 0x12\)0xffffffff\s*$', tree, re.MULTILINE):
                raise RuntimeError('Android app must support resizing')
        checks = 'contents/JNI/ELF 16 KiB' + ('/manifest' if aapt else '')
        print(f'{path.name}: {abi}, {path.stat().st_size / 1024**2:.1f} MiB, {checks} OK, dependencies {dependencies}, SHA256 {digest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aapt', type=Path, help='Also check the final binary manifest with Android SDK aapt')
    parser.add_argument('--launcher-foreground', type=Path, help='Verify generated launcher pixels reached the APK')
    parser.add_argument('apk', nargs='+', type=Path)
    args = parser.parse_args()
    for path in args.apk:
        verify(path, args.aapt, args.launcher_foreground)
