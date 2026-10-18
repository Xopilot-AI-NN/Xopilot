"""Файл: /App/services/ui_responsiveness.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Локальная диагностика блокировки цикла интерфейса во время работы ИИ.
"""
import asyncio
import logging
from pathlib import Path
import sys
import threading
import time


async def monitor_ui(page):
    # Do not capture locals, source lines, prompts, keys or screen contents.
    loop_thread = threading.get_ident()
    root = Path(__file__).resolve().parents[1]
    stopped = threading.Event()
    heartbeat = [time.monotonic()]
    active = [False]

    def watch():
        reported = False
        while not stopped.wait(.25):
            lag = time.monotonic() - heartbeat[0]
            busy = bool(getattr(page, '_xopilot_ai_busy', lambda: False)())
            if not busy or lag < 1:
                reported = False
                continue
            if reported:
                continue
            reported = True
            frame = sys._current_frames().get(loop_thread)
            stack = []
            while frame is not None:
                try:
                    path = Path(frame.f_code.co_filename).resolve().relative_to(root)
                except ValueError:
                    pass
                else:
                    stack.append(f'{path}:{frame.f_lineno}:{frame.f_code.co_name}')
                frame = frame.f_back
            logging.getLogger(__name__).warning('UI loop blocked during AI: %.2fs; %s',
                lag, ' <- '.join(stack[:12]) or 'outside application code',
                extra={'ui_frames': stack[:12]})

    worker = threading.Thread(target=watch, name='xopilot-ui-watch', daemon=True)
    worker.start()
    try:
        while True:
            active[0] = bool(getattr(page, '_xopilot_ai_busy', lambda: False)())
            heartbeat[0] = time.monotonic()
            await asyncio.sleep(.1 if active[0] else .5)
    finally:
        stopped.set()
        worker.join(timeout=.5)
