"""
***************************************************************
               Добро пожаловать в Xopilot-NN+ AI+ 2.0!
***************************************************************

Файл: /App/App.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание:
    Ядро приложения.
"""

import asyncio
import ctypes
import platform
import os
import sys
from pathlib import Path
# Lazy imports during inference must not create __pycache__ inside watched App/.
sys.dont_write_bytecode = True
from services.runtime import configure_runtime
from services.account_deletion import perform_pending_erasure

perform_pending_erasure()
configure_runtime()

import flet as ft
from services.platforms import is_mobile, is_android
from ctypes import wintypes
from app.main import build_app_ui
from services.stats import start_app_session, persist_app_session


class Init():
    def get_screen_size(self):
        from screeninfo import get_monitors
        m = get_monitors()[0]
        return m.width, m.height

    def get_work_area(self):
        if platform.system() != "Windows":
            sw, sh = self.get_screen_size()
            return 0, 0, sw, sh

        class Rect(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", Rect), ("rcWork", Rect), ("dwFlags", ctypes.c_ulong)]

        monitor_info = MonitorInfo()
        monitor_info.cbSize = ctypes.sizeof(MonitorInfo)
        user32 = getattr(ctypes, "windll").user32
        monitor = user32.MonitorFromPoint(wintypes.POINT(0, 0), 2)
        user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info))
        work_area = monitor_info.rcWork
        return work_area.left, work_area.top, work_area.right, work_area.bottom

    def auto_screen_size(self):
        sw, sh = self.get_screen_size()
        w = max(int(sw * 0.1), 380)
        h = max(int(sh * 0.15), 652)

        if platform.system() == "Windows":
            w, h = 380, 652
        else:
            w, h = h * 2, w * 2

        return w, h

    async def animate_position(self, page: ft.Page):
        _, _, work_right, work_bottom = self.get_work_area()
        w = int(page.window.width or 0)
        h = int(page.window.height or 0)

        target_top = work_bottom - h - 10
        target_left = work_right - w - 10

        page.window.left = target_left
        page.window.top = work_bottom
        page.window.visible = True
        page.update()

        for i in range(21):
            t = i / 20
            ease = 1 - (1 - t) ** 2
            page.window.top = int(work_bottom + (target_top - work_bottom) * ease)
            page.update()
            await asyncio.sleep(0.025)

        for i in range(11):
            page.window.top = target_top - i
            page.update()
            await asyncio.sleep(0.015)

        for i in range(10, -1, -1):
            page.window.top = target_top - i
            page.update()
            await asyncio.sleep(0.015)

    async def main(self, page: ft.Page):
        if is_android():
            loading = ft.Column(expand=True, alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[ft.ProgressRing(), ft.Text("Открываем защищённую историю…")])
            page.add(loading)
            try:
                from services.mobile_runtime import initialize
                await initialize()
            except Exception:
                # Do not silently create an unencrypted database or new key
                # when a restored installation has lost its Keystore entry.
                loading.controls = [ft.Icon(ft.Icons.LOCK_OUTLINE), ft.Text(
                    "Не удалось открыть защищённое хранилище. Перезапустите приложение. "
                    "Если данные восстановлены из резервной копии, потребуется исходное устройство.")]
                page.update()
                return
            page.remove(loading)
        from services.support import install as install_support_diagnostics
        install_support_diagnostics()
        start_app_session()

        async def persist_loop():
            last_persist=0
            while True:
                await asyncio.sleep(1)
                try:
                    now=asyncio.get_running_loop().time()
                    if now-last_persist>=30:
                        persist_app_session();last_persist=now
                    if getattr(page,'_xopilot_connected',False) and getattr(page,'_xopilot_can_upload',lambda:False)():
                        # Avoid importing beneath a form the user is editing.
                        dialogs=[dialog for dialog in page._dialogs.controls if dialog.open]
                        if not dialogs or getattr(dialogs[-1],'_xopilot_sync_safe',False):
                            from services import cloud_sync,cloud_account
                            if cloud_account.state():
                                result=await asyncio.to_thread(cloud_sync.run_auto_if_due,
                                    upload_only=not page._xopilot_can_sync())
                                if result and result.get('received'):page._xopilot_sync_refresh()
                except Exception:
                    pass

        page.title = "Xopilot 2.0.11"
        from services.runtime import IdleMemoryCleanup
        idle_memory = IdleMemoryCleanup()
        page._xopilot_memory_activity = idle_memory.activity
        async def memory_cleanup_loop():
            from services.llm import unload_if_idle
            while True:
                await asyncio.sleep(5)
                if getattr(page, '_xopilot_can_release_model', lambda: False)():
                    try:
                        released = await asyncio.to_thread(unload_if_idle)
                        if released:
                            getattr(page, '_xopilot_model_state_changed', lambda: None)()
                        await idle_memory.poll(page, model_released=released)
                    except Exception as exc:
                        import logging
                        logging.getLogger(__name__).warning("Не удалось освободить модель: %s", type(exc).__name__)

        page.theme = ft.Theme(use_material3=True, color_scheme_seed="#5378a5", font_family="Google Sans")
        page.theme_mode = ft.ThemeMode.LIGHT
        desktop_window = not page.web and not is_mobile(page)
        if desktop_window:
            try:
                w, h = self.auto_screen_size()
            except Exception:
                w, h = 1000, 720
            page.window.icon = "Icons/Xopilot-icon-apk.png"
            page.window.width = w
            page.window.height = h
            page.window.min_width = 380
            page.window.min_height = 560
            page.window.visible = False

        page.fonts = {"Google Sans": "./fonts/GoogleSans-Regular.ttf"}

        page.add(build_app_ui(page))
        page.update()
        page.run_task(persist_loop)
        page.run_task(memory_cleanup_loop)
        if not is_android():
            from services.ui_responsiveness import monitor_ui
            page.run_task(monitor_ui, page)
        if not is_android():
            from app.browser.remote_browser import listen_for_pairing
            page.run_task(listen_for_pairing,page)
            from services import remote_tasks
            try:
                remote_tasks.start(guard=lambda:page._xopilot_can_sync() and page._xopilot_can_release_model())
            except Exception:
                pass  # A missing cloud key must not prevent access to local chats.

        if not desktop_window:
            return
        if platform.system() == "Windows":
            await self.animate_position(page)
        else:
            page.window.visible = True
            page.update()

    def __init__(self):
        ft.run(self.main, assets_dir=str(Path(__file__).parent / "assets"),
               no_cdn=os.environ.get("FLET_WEB_NO_CDN") == "1",
               host="127.0.0.1")


Init()
