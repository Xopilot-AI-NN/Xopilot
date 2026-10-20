"""
Файл: /App/app/chat/memory/memory_capture.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент memory_capture интерфейса Xopilot.
"""
"""Best-effort cancellable background capture, without delaying the AI reply."""
import asyncio
import logging
import threading
import flet as ft
try:
    from ....services import user_memory
except ImportError:
    from services import user_memory


class MemoryCapture:
    def __init__(self, page):
        self.page = page
        self.task = None
        self.cancelled = threading.Event()
        self._running = 0

    @property
    def busy(self):
        return self._running > 0

    def cancel(self):
        self.cancelled.set()

    def submit(self, message, generate, *, private=False, workspace_id=None):
        self.cancel()
        cancelled = self.cancelled = threading.Event()
        async def collect():
            self._running += 1
            try:
                notes = await asyncio.to_thread(user_memory.capture, message, generate,
                    cancelled=cancelled, private=private,workspace_id=workspace_id)
                if notes and not cancelled.is_set() and getattr(self.page, '_xopilot_connected', True):
                    notice = ft.SnackBar(ft.Text('Сохранено в память: ' + '; '.join(notes)), action='Посмотреть')
                    def view(_):
                        notice.open = False
                        getattr(self.page, '_xopilot_open_memory', lambda: None)()
                    notice.on_action = view
                    self.page.show_dialog(notice)
                    async def dismiss():
                        await asyncio.sleep(4)
                        if notice.open and getattr(self.page, '_xopilot_connected', True):
                            notice.open = False
                            self.page.update()
                    self.page.run_task(dismiss)
            except asyncio.CancelledError:
                cancelled.set()
            except Exception as exc:
                logging.getLogger(__name__).info('Memory capture skipped: %s', type(exc).__name__)
            finally:
                self._running -= 1
        if not private:
            self.task = self.page.run_task(collect)
