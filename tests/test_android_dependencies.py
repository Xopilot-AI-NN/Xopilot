"""
Файл: /tests/test_android_dependencies.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Codex проверяет отказ сборки при старых/подменённых Android-зависимостях.
"""
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile
from scripts import build_android_wheels as wheels, verify_android_apk as apk


def packages(versions):
    stream = io.BytesIO()
    with ZipFile(stream, 'w') as archive:
        for name, version in versions.items():
            archive.writestr(f'{name}-{version}.dist-info/METADATA', f'Name: {name}\nVersion: {version}\n')
    return stream.getvalue()


class AndroidDependencyTests(unittest.TestCase):
    def test_apk_versions_must_come_from_installed_metadata(self):
        self.assertEqual(apk.verify_dependencies(packages(wheels.VERSIONS)), apk.PATCHED_DEPENDENCIES)
        for name, version in [('pillow', '12.2.0'), ('cryptography', '48.0.0')]:
            with self.subTest(name=name):
                with self.assertRaisesRegex(RuntimeError, name):
                    apk.verify_dependencies(packages({**wheels.VERSIONS, name: version}))
        with self.assertRaises(RuntimeError):
            apk.verify_dependencies(packages({'pillow': '12.3.0'}))

    def test_actual_openssl_binary_must_have_patched_version(self):
        apk.verify_openssl(b'\0OpenSSL 3.5.7 9 Jun 2026\0')
        for data in (b'OpenSSL 3.5.6 old\0', b'no OpenSSL version',
                     b'OpenSSL 3.5.7 patched\0OpenSSL 3.5.6 old\0'):
            with self.subTest(data=data):
                with self.assertRaises(RuntimeError):
                    apk.verify_openssl(data)

    def test_new_wheel_filename_cannot_hide_old_metadata(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for abi in wheels.ABIS:
                for name, version in wheels.VERSIONS.items():
                    path = root / f'{name}-{version}-1-cp314-cp314-android_24_{abi.replace("-", "_")}.whl'
                    path.write_bytes(packages({name: version}))
            self.assertEqual(len(wheels.validate_wheelhouse(root)), 6)
            next(root.glob('pillow*arm64_v8a.whl')).write_bytes(packages({'pillow': '12.2.0'}))
            with self.assertRaisesRegex(ValueError, 'version'):
                wheels.validate_wheelhouse(root)

    def test_cached_source_checksum_is_checked_before_execution(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'source.tar.gz'
            path.write_bytes(b'changed cached archive')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                wheels.download_checked('https://example.invalid/not-requested', path, '0' * 64)


if __name__ == '__main__':
    unittest.main()
