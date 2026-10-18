"""Файл: /App/app/shared/components/reply_activity.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Плавная анимация ожидания ответа; кадры анимирует Flutter.
"""
import asyncio
import flet as ft
from ...theme.palette import color


class ReplyActivity(ft.Row):
    def __init__(self):
        super().__init__(width=44, height=20, spacing=4, visible=False,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[ft.Container(width=8, height=14, border_radius=4,
                bgcolor=color(tone), scale=.6, opacity=.45,
                animate_scale=ft.Animation(480, ft.AnimationCurve.EASE_IN_OUT),
                animate_opacity=ft.Animation(480, ft.AnimationCurve.EASE_IN_OUT))
                for tone in ('#087f8c', '#5378a5', '#7657ff')])
        self._active = asyncio.Event()
        self._task = None

    def set_active(self, value):
        self.visible = value
        if value:
            self._active.set()
        else:
            self._active.clear()
            for bar in self.controls:
                bar.scale, bar.opacity = .6, .45

    def did_mount(self):
        self._task = self.page.run_task(self.pulse)

    def will_unmount(self):
        if self._task is not None:
            self._task.cancel()
        self._task = None

    async def pulse(self):
        phase = 0
        while True:
            await self._active.wait()
            for index, bar in enumerate(self.controls):
                bar.scale = 1 if index == phase else .6
                bar.opacity = 1 if index == phase else .45
            self.update()
            phase = (phase + 1) % len(self.controls)
            await asyncio.sleep(.52)
