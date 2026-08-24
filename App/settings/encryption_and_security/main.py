"""
Файл: /App/settings/encryption_and_security/main.py
Описание: __Страница шифрования и безопасности__.
           Объединяет переключатель шифрования истории и поле пароля.
"""

import flet as ft

from ..common import section_title, setting_row
from .password_field import build_password_field
from .buttons.toggle import build_encryption_toggle


def build_security_page(on_status) -> ft.Column:
    password = build_password_field()

    def change(_):
        password.disabled = not encryption.value
        password.update()
        on_status("Настройки безопасности обновлены")

    encryption = build_encryption_toggle(change)
    return ft.Column(
        spacing=2,
        controls=[
            section_title("Безопасность"),
            setting_row(
                ft.Icons.LOCK_OUTLINE,
                "Шифрование истории",
                "Защитить локально сохранённые чаты",
                encryption,
            ),
            ft.Container(padding=ft.padding.Padding.only(left=47, bottom=5), content=password),
        ],
    )
