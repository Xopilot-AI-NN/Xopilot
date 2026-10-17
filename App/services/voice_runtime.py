"""
Файл: /App/services/voice_runtime.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Проверенная отдельная среда подготовки голоса для установленного Xopilot.
"""
import os
import platform
from pathlib import Path
import tarfile
import tempfile
import zipfile
from concurrent.futures import CancelledError

from .paths import app_data_dir
from .voice_installer import download_verified

_BASE='https://github.com/astral-sh/python-build-standalone/releases/download/20261013/'
_RUNTIMES={
    ('Linux','x86_64'):('cpython-3.12.15%2B20261013-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz',
                         '178d3d83b6e8e99285a65d3fce9c16b87952cc5efdb4d1a0e3ff3be18ff0fc9c'),
    ('Windows','x86_64'):('cpython-3.12.15%2B20261013-x86_64-pc-windows-msvc-install_only_stripped.tar.gz',
                           '7a2aef48e5ee569e310b29b32681debbc5d888e92790d85331a47736c6b06aad'),
}


def export_runtime(on_progress, *, on_download=None, cancelled=None):
    machine=platform.machine().lower()
    machine='x86_64' if machine in {'amd64','x64','x86_64'} else machine
    spec=_RUNTIMES.get((platform.system(),machine))
    if spec is None:raise RuntimeError('Автоматическая подготовка Miku пока доступна на Linux и Windows x64.')
    name,digest=spec
    root=app_data_dir()/'runtime'/'miku-python-3.12.15'
    python=root/('python.exe' if os.name=='nt' else 'bin/python3')
    marker=root/'xopilot-runtime.sha256'
    if python.is_file() and marker.is_file() and marker.read_text()==digest:return python
    root.parent.mkdir(parents=True,exist_ok=True)
    on_progress('Скачиваю отдельную среду подготовки Miku…')
    with tempfile.TemporaryDirectory(dir=root.parent,prefix='voice-python-') as temporary:
        stage=Path(temporary);archive=stage/'python.tar.gz'
        download_verified(_BASE+name,archive,digest,on_download=on_download,cancelled=cancelled)
        on_progress('Распаковываю среду подготовки Miku…')
        with tarfile.open(archive) as source:source.extractall(stage/'unpacked',filter='data')
        candidate=stage/'unpacked'/'python'
        executable=candidate/('python.exe' if os.name=='nt' else 'bin/python3')
        if not executable.is_file() or not executable.resolve().is_relative_to(candidate.resolve()):
            raise RuntimeError('В архиве среды отсутствует интерпретатор Python.')
        if cancelled is not None and cancelled.is_set():raise CancelledError()
        (candidate/'xopilot-runtime.sha256').write_text(digest)
        previous=stage/'previous-runtime'
        if root.exists():os.replace(root,previous)
        try:os.replace(candidate,root)
        except BaseException:
            if previous.exists():os.replace(previous,root)
            raise
    return python


def stage_export_sources(destination):
    """The child interpreter must not depend on the app's Python bytecode version."""
    archive=Path(__file__).resolve().parents[1]/'assets'/'voice'/'miku-export-source.zip'
    package=Path(destination)/'_rvc_export';package.mkdir(parents=True)
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            name=member.filename
            if '/' in name or '\\' in name or name in {'.','..'}:
                raise RuntimeError('Повреждён комплект подготовки Miku.')
            (package/name).write_bytes(source.read(member))
    return Path(destination)
