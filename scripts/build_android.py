"""Build the POCO/ChromeOS Android APKs with the correct native libraries.

Run with the same Python environment that provides Flet 1.0.3. The generated
shell is based on Flet's pinned official template; NDK and compile SDK are set consistently across Android plugins.
"""
import argparse
from pathlib import Path
import os
import shutil
import subprocess
import sys
import zipfile
import json
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def android_exclusions():
    """Merge Flet exclusions before CLI overrides them; expand exact paths."""
    configuration = tomllib.loads((ROOT/'pyproject.toml').read_text())['tool']['flet']
    patterns = [*configuration.get('app', {}).get('exclude', []),
                *configuration.get('android', {}).get('app', {}).get('exclude', [])]
    root = ROOT/'App'
    paths = set()
    for pattern in patterns:
        if any(character in pattern for character in '*?['):
            paths.update(path.relative_to(root).as_posix() for path in root.glob(pattern))
        else:
            paths.add(pattern)
    # User data and desktop binaries must never enter an Android artifact,
    # including when a future configuration accidentally omits these paths.
    paths.update(('data', 'native', 'build', '.flet', 'assets/models/sentiment.onnx'))
    paths.update(path.name for pattern in ('advanced_xopilot*.so', 'advanced_xopilot*.pyd')
                 for path in root.glob(pattern))
    return sorted(paths)


ANDROID_PLUGIN_NDK = '\n'.join([
    'subprojects {',
    '    plugins.withId("com.android.library") {',
    '        // file_picker 11 checks AGP version instead of builtInKotlin.',
    '        // Our Flutter shell retains external Kotlin for legacy plugins.',
    '        if (name == "file_picker") {',
    '            plugins.apply("org.jetbrains.kotlin.android")',
    '            tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach {',
    '                compilerOptions.jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)',
    '            }',
    '        }',
    '        val components = extensions.getByName("androidComponents")',
    '        val configureNdk: (Any) -> Unit = { android ->',
    '            android.javaClass.getMethod("setNdkVersion", String::class.java)',
    '                .invoke(android, "29.0.14206865")',
    '            android.javaClass.getMethod("setCompileSdk", Int::class.javaObjectType)',
    '                .invoke(android, 37)',
    '        }',
    '        components.javaClass.getMethod("finalizeDsl", kotlin.jvm.functions.Function1::class.java)',
    '            .invoke(components, configureNdk)',
    '    }',
    '}',
])


def prepare_template(jdk):
    import flet
    from flet_cli.commands.build_base import DEFAULT_TEMPLATE_URL
    from flet_cli.utils.template_cache import get_cached_template_zip
    version = flet.version.flet_version
    if version != '1.0.3':
        raise RuntimeError('This Android bridge requires Flet 1.0.3 and Python runtime 3.14.7')
    archive = get_cached_template_zip(DEFAULT_TEMPLATE_URL.format(version=version), version)
    destination = ROOT / 'build/android-template'
    if destination.exists(): shutil.rmtree(destination)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as source:
        # Treat even cached archives as data. Never extract outside our folder.
        for entry in source.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()): raise ValueError('Unsafe template archive path')
        source.extractall(destination)
    template = next(destination.rglob('cookiecutter.json')).parent
    gradle = next(template.rglob('app/build.gradle.kts'))
    text = gradle.read_text()
    old = 'ndkVersion = flutter.ndkVersion'
    if old not in text: raise RuntimeError('Flet Android template changed: review NDK override')
    text = text.replace(old, 'ndkVersion = "29.0.14206865"').replace('compileSdk = flutter.compileSdkVersion', 'compileSdk = 37')
    gradle.write_text(text)
    root_gradle = next(path for path in template.rglob('android/build.gradle.kts') if '/app/' not in str(path))
    root_gradle.write_text(root_gradle.read_text() + '\n' + ANDROID_PLUGIN_NDK)
    settings = next(template.rglob('android/settings.gradle.kts'))
    settings.write_text(settings.read_text().replace('"8.11.1"', '"9.4.1"').replace('"2.2.20"', '"2.4.20"'))
    wrapper = next(template.rglob('gradle-wrapper.properties'))
    wrapper.write_text(wrapper.read_text().replace('gradle-8.14-all.zip', 'gradle-9.7.1-bin.zip'))
    properties = next(template.rglob('android/gradle.properties'))
    properties.write_text(properties.read_text() + f'\norg.gradle.java.installations.paths={jdk}\n')
    manifest = next(template.rglob('android/app/src/main/AndroidManifest.xml'))
    xml = manifest.read_text()
    if 'xmlns:tools=' not in xml:
        xml = xml.replace('<manifest ', '<manifest xmlns:tools="http://schemas.android.com/tools" ', 1)
    # Camera snapshots and picked documents use private cache/SAF. CameraX's
    # legacy shared-storage permission also implies a broad READ permission.
    removals = '\n'.join(f'<uses-permission android:name="android.permission.{name}" tools:node="remove" />'
                         for name in ('READ_EXTERNAL_STORAGE', 'WRITE_EXTERNAL_STORAGE'))
    # required flags merge with logical OR; false alone cannot override
    # CameraX's implicit true. Replace that element from the main manifest.
    optional_camera = '<uses-feature android:name="android.hardware.camera.any" android:required="false" tools:node="replace" />'
    xml = xml.replace('<application', removals + '\n' + optional_camera + '\n<application', 1)
    browser_query = '<intent><action android:name="android.intent.action.VIEW" /><data android:scheme="https" /></intent>'
    xml = xml.replace('<queries>', '<queries>\n' + browser_query, 1)
    manifest.write_text(xml)
    return template


def android_environment(jdk):
    if jdk is None:
        java = shutil.which('java')
        jdk = Path(os.environ['JAVA_HOME']) if os.environ.get('JAVA_HOME') else (Path(java).resolve().parents[1] if java else None)
    if jdk is None or not (jdk/'bin/javac').is_file():
        raise RuntimeError('Install JDK 21 and pass --jdk /path/to/jdk')
    version = subprocess.run([str(jdk/'bin/java'), '-version'], text=True, capture_output=True, check=True)
    match = re.search(r'version "(\d+)', version.stdout + version.stderr)
    if not match or int(match[1]) != 21:
        raise RuntimeError('LiteRT-LM 0.18 requires JDK 21; pass --jdk /path/to/jdk21')
    # Flutter's saved jdk-dir takes precedence over JAVA_HOME. Use build-local
    # settings instead of altering the user's desktop Flutter configuration.
    config = ROOT/'build/android-flutter-config'
    config.mkdir(parents=True, exist_ok=True)
    (config/'settings').write_text(json.dumps({'jdk-dir': str(jdk.resolve())}))
    return dict(os.environ, JAVA_HOME=str(jdk.resolve()), XDG_CONFIG_HOME=str(config))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, default=Path(os.environ.get('ANDROID_NDK_ROOT', '/opt/android-sdk/ndk/29.0.14206865')))
    parser.add_argument('--jdk', type=Path, help='JDK 21 directory used only for Android builds')
    parser.add_argument('--arch', nargs='+', choices=('arm64-v8a', 'x86_64'), default=['arm64-v8a', 'x86_64'])
    parser.add_argument('--skip-native', action='store_true', help='Reuse already built Android DB libraries')
    parser.add_argument('--build-number', type=int, help='Positive Android versionCode, e.g. CI run number')
    parser.add_argument('--build-version', help='Application version, e.g. 2.0.7')
    args = parser.parse_args()
    if args.build_number is not None and not 0 < args.build_number <= 2100000000:
        parser.error('--build-number must be between 1 and 2100000000')
    if args.build_version is not None and not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?', args.build_version):
        parser.error('--build-version must be a semantic version, e.g. 2.0.7')
    environment = android_environment(args.jdk)
    if not args.skip_native:
        subprocess.run([sys.executable, str(ROOT/'scripts/build_android_native.py'), '--ndk', str(args.ndk), '--arch', *args.arch], check=True)
    libs = ROOT/'extensions/flet_xopilot_mobile/src/flutter/flet_xopilot_mobile/android/src/main/jniLibs'
    for abi in args.arch:
        if not (libs/abi/'libadvanced_xopilot.so').is_file(): raise RuntimeError(f'Missing encrypted DB for {abi}')
    template = prepare_template(environment['JAVA_HOME'])
    # Flet hashes a local template's path, not its files. Invalidate only its
    # generated-shell stamps so changes to our pinned NDK reach Gradle.
    # The shell recreation restores Flet's launcher resources. Their generation
    # stamps must also be invalidated, even when the source artwork is unchanged.
    for name in ('template-1', 'template-2', 'package', 'icons', 'splashes'):
        (ROOT/'build/.hash'/name).unlink(missing_ok=True)
    # Desktop and Android share Flet's staging folder. Excludes prevent new
    # copies, but cannot remove an old desktop .so left by a previous build.
    shutil.rmtree(ROOT/'build/python-app', ignore_errors=True)
    # serious_python's --exclude accepts exact relative paths, not globs.
    # Expand the host-native patterns before passing them to Flet.
    exclude = ['--exclude', *android_exclusions()]
    numbering = ['--build-number', str(args.build_number)] if args.build_number is not None else []
    if args.build_version is not None:
        numbering += ['--build-version', args.build_version]
    subprocess.run([str(Path(sys.executable).parent / 'flet'), 'build', 'apk', str(ROOT),
                    '--template', str(template), '--python-version', '3.14',
                    '--arch', *args.arch, '--yes', '--skip-flutter-doctor', *numbering, *exclude], cwd=ROOT, env=environment, check=True)
    artifacts = [ROOT/'build/apk'/f'Xopilot-{abi}.apk' for abi in args.arch]
    sdk = Path(environment.get('ANDROID_HOME', environment.get('ANDROID_SDK_ROOT', '/opt/android-sdk')))
    tools = sorted(sdk.glob('build-tools/*/aapt'), key=lambda path: tuple(int(part) for part in re.findall(r'\d+', path.parent.name)))
    if not tools: raise RuntimeError('Android SDK aapt required to verify the final APK manifest')
    subprocess.run([sys.executable, str(ROOT/'scripts/verify_android_apk.py'),
                    '--aapt', str(tools[-1]),
                    '--launcher-foreground', str(ROOT/'build/flutter/android/app/src/main/res/drawable-xxxhdpi/ic_launcher_foreground.png'),
                    *(str(path) for path in artifacts)], cwd=ROOT, check=True)


if __name__ == '__main__': main()
