"""Open the generated Flutter project with its staged Python runtime.

Run build_android.py first. This launcher never repackages or changes user data.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def studio_environment(root=ROOT):
    project = root/'build/flutter'
    app = root/'build/python-app'
    packages = root/'build/site-packages'
    for path in (project/'pubspec.yaml', project/'android/local.properties', app, packages):
        if not path.exists():
            raise RuntimeError('Сначала подготовьте Android-проект: scripts/build_android.py --jdk /путь/к/jdk-21')
    properties = dict(line.split('=', 1) for line in (project/'android/local.properties').read_text().splitlines()
                      if '=' in line and not line.lstrip().startswith('#'))
    flutter = Path(properties['flutter.sdk'])
    sdk = Path(properties['sdk.dir'])
    if not (flutter/'bin/flutter').is_file() or not sdk.is_dir():
        raise RuntimeError('Пути Flutter/Android SDK в build/flutter/android/local.properties недоступны')
    environment = dict(os.environ, SERIOUS_PYTHON_VERSION='3.14', SERIOUS_PYTHON_APP=str(app.resolve()),
        SERIOUS_PYTHON_SITE_PACKAGES=str(packages.resolve()), ANDROID_HOME=str(sdk),
        PATH=str(flutter/'bin') + os.pathsep + os.environ.get('PATH', ''))
    return project, environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio', help='Path to Android Studio bin/studio.sh or an installed launcher')
    parser.add_argument('--check', action='store_true', help='Validate project paths without opening the IDE')
    args = parser.parse_args()
    try:
        project, environment = studio_environment()
        if args.check:
            print(f'Flutter project: {project}')
            for name in ('SERIOUS_PYTHON_VERSION', 'SERIOUS_PYTHON_APP', 'SERIOUS_PYTHON_SITE_PACKAGES', 'ANDROID_HOME'):
                print(f'{name}={environment[name]}')
            return
        launcher = args.studio or shutil.which('android-studio') or shutil.which('studio') or shutil.which('studio.sh')
        if not launcher:
            raise RuntimeError('Укажите установленную Android Studio: --studio /путь/android-studio/bin/studio.sh')
        subprocess.run([launcher, str(project)], env=environment, check=True)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
