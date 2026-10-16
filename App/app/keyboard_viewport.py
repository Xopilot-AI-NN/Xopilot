"""
Файл: /App/app/keyboard_viewport.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Нативное изменение высоты чата при клавиатуре без покадровых обновлений Python.
"""
import flet as ft


@ft.control('XopilotKeyboardViewport')
class KeyboardViewport(ft.LayoutControl):
    content: ft.Control
