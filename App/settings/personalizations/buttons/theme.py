"""Seven persistent palettes, shared by the main view and open dialogs."""
import flet as ft
try:
    from ....services.db import get_setting, get_db
    from ....app.palette import set_theme, color, THEMES
except ImportError:
    from services.db import get_setting, get_db
    from app.palette import set_theme, color, THEMES


def build_theme_switch(page, on_status):
    choice = ft.Dropdown(value=get_setting('theme', 'light'), width=250,
        options=[ft.DropdownOption(key=key, text=title) for key, (title, _, _) in THEMES.items()],
        color=color('#123b43'), bgcolor=color('#f3fffc'),
        border=ft.OutlineInputBorder(border_radius=16, side=ft.BorderSide(color=color('#a8ddd7'))))
    saved = choice.value
    def change(_):
        nonlocal saved
        try:
            get_db().set_setting('theme', choice.value)
            saved = choice.value
            set_theme(page, saved)
            on_status('Тема применена')
        except Exception as exc:
            choice.value = saved
            on_status(f'Не удалось сохранить тему: {exc}')
        page.update()
    choice.on_select = change
    return choice
