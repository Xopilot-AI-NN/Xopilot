"""Файл: /scripts/flet_android_cli.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Запуск Flet CLI с уже проверенным JDK 21 вместо его автозагрузки JDK 17.
"""
import os
from pathlib import Path
import subprocess


def configured_jdk():
    root=Path(os.environ.get('JAVA_HOME',''))
    if not (root/'bin/javac').is_file():raise RuntimeError('JAVA_HOME must point to the configured JDK 21')
    result=subprocess.run([str(root/'bin/javac'),'-version'],capture_output=True,text=True,check=True)
    if not (result.stdout+result.stderr).strip().startswith('javac 21.'):
        raise RuntimeError('LiteRT-LM requires JDK 21')
    return str(root.resolve())


def main():
    root=configured_jdk()
    from flet_cli.utils import jdk
    # Scope the compatibility adapter to this child process. Flet otherwise
    # rejects JAVA_HOME=21 as a JRE and replaces Flutter's build-local settings.
    jdk.install_jdk=lambda log,progress=None: root
    from flet_cli.cli import main as cli
    cli()


if __name__=='__main__':main()
