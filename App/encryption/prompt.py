"""
Файл: /App/encryption/prompt.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __Строка ввода__
        клеится снизу в окне.
        Фон поля задаётся обёрткой в main.py.
"""



import secrets
import flet as ft
from .buttons.send import build_send_button

MASK_SYMBOLS = "*()_+@!$%^&=-~"

def _build_mask(length: int) -> str:
    return "".join(secrets.choice(MASK_SYMBOLS) for _ in range(length))

def _apply_mask_edit(old_actual: str, old_mask: str, current: str) -> str:
    prefix = 0
    while (
        prefix < len(old_mask)
        and prefix < len(current)
        and old_mask[prefix] == current[prefix]
    ):
        prefix += 1

    suffix = 0
    while (
        suffix < len(old_mask) - prefix
        and suffix < len(current) - prefix
        and old_mask[len(old_mask) - suffix - 1] == current[len(current) - suffix - 1]
    ):
        suffix += 1

    current_end = len(current) - suffix if suffix else len(current)
    old_end = len(old_mask) - suffix if suffix else len(old_mask)
    inserted = current[prefix:current_end]

    return old_actual[:prefix] + inserted + old_actual[old_end:]

def build_prompt() -> ft.TextField:
    state = {
        "actual": "",
        "mask": "",
        "updating": False,
    }

    def on_change(e):
        if state["updating"]:
            return

        prompt = e.control
        current = prompt.value or ""
        old_mask = state["mask"]
        old_actual = state["actual"]

        actual = _apply_mask_edit(old_actual, old_mask, current)

        state["actual"] = actual
        state["mask"] = _build_mask(len(actual))
        prompt.data = actual

        state["updating"] = True
        prompt.value = state["mask"]
        prompt.update()
        state["updating"] = False

    prompt = ft.TextField(
        can_reveal_password=False,
        multiline=True,
        min_lines=1,
        max_lines=3,
        border_radius=10,
        bgcolor=ft.Colors.TRANSPARENT,
        color=ft.Colors.BLACK,
        cursor_color=ft.Colors.BLACK,
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.TRANSPARENT,
        content_padding=ft.padding.Padding.symmetric(horizontal=4, vertical=8),
        on_change=on_change,
        expand=True,
    )
    prompt.data = ""
    return prompt

def build_prompt_container(prompt: ft.TextField, on_send) -> ft.Container:
    return ft.Container(
        expand=True,
        border_radius=10,
        border=ft.border.Border.all(2, "#d9ffe6"),
        gradient=ft.LinearGradient(
            begin=ft.alignment.Alignment.TOP_LEFT,
            end=ft.alignment.Alignment.BOTTOM_RIGHT,
            colors=["#00c753", "#0083e8"],
        ),
        padding=ft.padding.Padding.symmetric(horizontal=8, vertical=4),
        content=ft.Row(
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                prompt,
                build_send_button(on_send),
            ],
        ),
    )
