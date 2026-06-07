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
import platform
import flet as ft
import setproctitle
from screeninfo import get_monitors
from encryption.main import build_encryption_ui

print("Привет всем!")

class Init():
    def get_screen_size(self):
        m = get_monitors()[0]
        return m.width, m.height

    def auto_screen_size(self):
        sw, sh = self.get_screen_size()
        w = max(int(sw * 0.1), 380)
        h = max(int(sh * 0.15), 652)
        return w, h

    async def animate_position(self, page: ft.Page):
        sw, sh = self.get_screen_size()
        w = int(page.window.width or 0)
        h = int(page.window.height or 0)

        target_top  = sh - h - 10
        target_left = (sw - w) // 2

        page.window.left    = target_left
        page.window.top     = sh
        page.window.visible = True
        page.update()

        for i in range(21):
            t    = i / 20
            ease = 1 - (1 - t) ** 2
            page.window.top = int(sh + (target_top - sh) * ease)
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
        page.window.icon      = "./Icons/Xopilot-icon-apk.ico"
        page.window.width     = w
        page.window.height    = h
        page.window.min_width = w
        page.window.max_width = w
        page.window.visible   = False
        page.update()

        # Монтируем первый интерфейс
        page.add(build_encryption_ui(page))
        page.update()

        # Анимация — только ядро решает
        if platform.system() == "Windows":
            await self.animate_position(page)
        else:
            page.window.visible = True
            page.update()

    def __init__(self):
        setproctitle.setproctitle("Xopilot")
        ft.run(self.main)

Init()