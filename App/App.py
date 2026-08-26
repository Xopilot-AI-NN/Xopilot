"""
***************************************************************
               Добро пожаловать в Xopilot-NN+ AI+ 2.0!
***************************************************************

Файл: /App/App.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание:
    Ядро приложения.
    Отвечает за обработку сервисов упровлением по нажатию клавишь
        а также интерфейса и видом окна
"""



import asyncio
import ctypes
import platform
import flet as ft
from screeninfo import get_monitors
from ctypes import wintypes
from app.main import build_app_ui



class Init():
    def get_screen_size(self):
        m = get_monitors()[0]
        return m.width, m.height

    def get_work_area(self):
        if platform.system() != "Windows":
            sw, sh = self.get_screen_size()
            return 0, 0, sw, sh

        class Rect(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("rcMonitor", Rect),
                ("rcWork", Rect),
                ("dwFlags", ctypes.c_ulong),
            ]

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
            # Linux/Wayland не даёт точно позиционировать окно
            # (как на Windows через animate_position), поэтому вместо
            # узкого вертикального виджета делаем широкое горизонтальное
            # окно — ширина и высота меняются местами и удваиваются.
            w, h = h * 2, w * 2

        return w, h

    async def animate_position(self, page: ft.Page):
        _, _, work_right, work_bottom = self.get_work_area()
        w = int(page.window.width or 0)
        h = int(page.window.height or 0)

        target_top  = work_bottom - h - 10
        target_left = work_right - w - 10

        page.window.left    = target_left
        page.window.top     = work_bottom
        page.window.visible = True
        page.update()

        for i in range(21):
            t    = i / 20
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
        w, h = self.auto_screen_size()

        # Настройка окна — только ядро
        page.title            = "Xopilot-NN+ AI+ 2.0"
        page.window.icon      = "./Icons/Xopilot-icon-apk.png"
        page.window.width     = w
        page.window.height    = h
        page.window.min_width = w
        page.window.max_width = w
        page.window.visible   = False
        page.update()

        # Шрифт
        page.fonts = {
            "Google Sans": "./fonts/GoogleSans-Regular.ttf"
        }

        # Монтируем интерфейс
        page.add(build_app_ui(page))
        page.update()

        # Анимация — только ядро решает
        if platform.system() == "Windows":
            await self.animate_position(page)
        else:
            page.window.visible = True
            page.update()

    def __init__(self):
        ft.run(self.main)

Init()