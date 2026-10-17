"""
Файл: /App/app/models/model_download.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент model_download интерфейса Xopilot.
"""
"""Shared model download UI: bytes, progress, pause and persistent continuation."""
import asyncio
import inspect
import flet as ft
from ..theme.palette import color
try:
    from ...services.model_installer import model_download
except ImportError:
    from services.model_installer import model_download


class ModelDownloadPanel(ft.Column):
    def __init__(self, model, on_installed=None):
        self.model = model
        self.job = model_download(model.id)
        self.on_installed = on_installed
        self._mounted = False
        self._notified = False
        self.label = ft.Text(size=11, color=color('#47747a'))
        self.bar = ft.ProgressBar(value=0, color=color('#087f8c'), visible=False)
        self.action = ft.OutlinedButton(content='Скачать', icon=ft.Icons.DOWNLOAD, on_click=self._action)
        super().__init__(spacing=6, controls=[self.label, self.bar, self.action])
        self.refresh()

    def refresh(self):
        state = self.job.state
        running = state in {'downloading', 'waiting', 'verifying'}
        installed = self.model.installed and state in {'idle', 'installed'}
        chip=getattr(self,'_xopilot_status_chip',None)
        if chip is not None:
            chip.content.value='Установлено' if installed else 'Не установлено'
            chip.bgcolor=color('#d8f5e7' if installed else '#fff0d8')
            chip.content.color=color('#08734d' if installed else '#8a5a00')
        self.bar.visible = running or state == 'paused'
        self.bar.value = min(1, self.job.downloaded / self.job.total) if self.job.total else (None if running else 0)
        size = f'{self.job.downloaded / 1024**2:.1f} МБ'
        if self.job.total:
            size += f' / {self.job.total / 1024**2:.1f} МБ · {self.bar.value * 100:.0f}%'
        self.label.value = {
            'downloading': 'Скачивание · ' + size,
            'waiting': 'Ожидаю сеть · ' + size + '. Продолжу автоматически.',
            'verifying': 'Проверяю целостность файла…',
            'paused': 'На паузе · ' + size + '. Загруженная часть сохранена.',
            'error': self.job.error,
        }.get(state, 'Модель установлена' if installed else '')
        self.action.content = 'Пауза' if running else ('Продолжить' if state == 'paused' else 'Переустановить' if installed else 'Скачать')
        self.action.icon = ft.Icons.PAUSE if running else ft.Icons.DOWNLOAD
        pausing = self.job.pause_requested.is_set() and self.job.worker is not None and self.job.worker.is_alive()
        self.action.disabled = pausing
        if pausing:
            self.action.content = 'Приостанавливаю…'

    def _action(self, _):
        if self.job.state in {'downloading', 'waiting', 'verifying'}:
            self.job.pause()
        else:
            self._notified = False
            self.job.start()
        self.refresh()
        self.update()

    def did_mount(self):
        self._mounted = True
        self.page.run_task(self._watch)

    def will_unmount(self):
        self._mounted = False

    async def _watch(self):
        while self._mounted:
            self.refresh()
            self.update()
            if self.job.state == 'installed' and not self._notified:
                self._notified = True
                try:
                    from ...services.platforms import is_android
                    from ...services.mobile_runtime import refresh_capabilities
                except ImportError:
                    from services.platforms import is_android
                    from services.mobile_runtime import refresh_capabilities
                if is_android():
                    await refresh_capabilities()
                if not self._mounted:
                    return
                if self.on_installed:
                    result = self.on_installed()
                    if inspect.isawaitable(result):
                        await result
            await asyncio.sleep(.5)
