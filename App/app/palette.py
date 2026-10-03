"""The existing aqua palette with a matching dark appearance."""
from dataclasses import fields, is_dataclass, replace
import flet as ft
from flet.controls.base_control import BaseControl

DARK = {
    '#b3f2ff': '#10262e', '#d9ffe6': '#152f31', '#eafffa': '#17343a',
    '#f3fffc': '#203e44', '#f5fffc': '#203e44', '#effffc': '#203e44',
    '#ffffff': '#24434b', '#e6ffffff': '#e624434b', '#dff8f3': '#26494d',
    '#c9f1e9': '#30575a', '#edfbf8': '#31565b', '#e3f7f2': '#31565b',
    '#d7f1eb': '#365e63', '#bcefe5': '#365e63', '#123b43': '#e4f6f7',
    '#47747a': '#a8c8cd', '#087f8c': '#65d5d8', '#000000': '#edf6f7',
    '#b9eee4': '#3b6266', '#b6e5df': '#3b6266', '#a8ddd7': '#487277',
    '#ffe9e9': '#4d303b', '#ffd2d2': '#623f4a', '#c94b4b': '#ff9b9b',
    '#ecfffa': '#244b50', '#ddf8f2': '#315b60', '#d8f5ee': '#365e63',
    '#eafbfa': '#203e44', '#d8f5e7': '#315b50', '#fff0d8': '#493e28',
    '#08734d': '#87dfba', '#8a5a00': '#f5cb84', '#6a8d91': '#a8c8cd',
    '#b3261e': '#ffaaa6', '#d9364f': '#ff9baf',
}
_mode = 'light'
THEMES = {
    'light': ('Аква · светлая', False, {}),
    'dark': ('Аква · тёмная', True, DARK),
}
for key, title, dark, values in [
    ('midnight', 'Полночь', True, ('#111425', '#181d32', '#21283e', '#2c3550', '#eef0ff', '#aab6da', '#b5a4ff')),
    ('ocean', 'Океан', True, ('#081d2b', '#102b3d', '#173e53', '#255368', '#e5f7ff', '#a0c5d8', '#75d5ff')),
    ('forest', 'Лес', True, ('#14211c', '#1d3027', '#294438', '#3b5c4b', '#edf9ee', '#b2cebb', '#8fe3ac')),
    ('lavender', 'Лаванда', False, ('#ebe7f5', '#f5f1ff', '#ffffff', '#ded5ef', '#302547', '#75658e', '#7753bd')),
    ('sunset', 'Закат', False, ('#f5e4dc', '#fff3e9', '#fffaf5', '#edcbbc', '#4b2d2b', '#8b6660', '#b64e61')),
]:
    background, surface, raised, border, text, muted, accent = values
    mapping = {source: raised for source in DARK}
    mapping.update({'#b3f2ff': background, '#d9ffe6': surface, '#eafffa': surface,
                    '#e6ffffff': '#e6' + raised[1:], '#123b43': text, '#000000': text,
                    '#47747a': muted, '#6a8d91': muted, '#087f8c': accent,
                    '#b9eee4': border, '#b6e5df': border, '#a8ddd7': border,
                    '#b3261e': '#ffaaa6' if dark else '#b3261e',
                    '#c94b4b': '#ff9b9b' if dark else '#c94b4b',
                    '#d9364f': '#ff9baf' if dark else '#d9364f',
                    '#ffe9e9': '#4d303b' if dark else '#ffe9e9',
                    '#ffd2d2': '#623f4a' if dark else '#ffd2d2',
                    '#08734d': '#87dfba' if dark else '#08734d',
                    '#8a5a00': '#f5cb84' if dark else '#8a5a00'})
    THEMES[key] = (title, dark, mapping)


class PaletteColor(str):
    def __new__(cls, value, original):
        instance = super().__new__(cls, value)
        instance.original = original
        return instance

    def __getnewargs__(self):
        return str(self), self.original


def color(value):
    source = getattr(value, 'original', value.lower())
    return PaletteColor(THEMES[_mode][2].get(source, source), source)


def apply_palette(root):
    reverse = {v: k for _, _, mapping in THEMES.values() for k, v in mapping.items()}
    seen = set()
    def source(value):
        return getattr(value, 'original', value.lower() if value.lower() in DARK else reverse.get(value.lower(), value.lower()))

    def style_value(obj):
        if isinstance(obj, PaletteColor):
            return color(obj)
        # Reconstruct value styles before assigning them to a mounted control.
        # Copying Flet's mutation hooks also copies their old change history.
        if isinstance(obj, list):
            return [style_value(item) for item in obj]
        if isinstance(obj, dict):
            return {key: style_value(value) for key, value in obj.items()}
        if not is_dataclass(obj) or isinstance(obj, BaseControl):
            return obj
        originals = dict(obj.__dict__.get('_xopilot_palette', {}))
        values = {}
        for field in fields(obj):
            if not field.init or field.name.startswith('_'):
                continue
            value = getattr(obj, field.name)
            if isinstance(value, str) and (value.lower() in DARK or value.lower() in reverse):
                original = originals.get(field.name, source(value))
                originals[field.name] = original
                values[field.name] = color(original)
            else:
                values[field.name] = style_value(value)
        result = replace(obj, **values)
        result.__dict__['_xopilot_palette'] = originals
        return result

    def visit(obj):
        if getattr(obj, '__dict__', {}).get('_xopilot_fixed_colors'):
            return
        if id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, list):
            for value in obj:
                visit(value)
        elif is_dataclass(obj):
            if isinstance(obj, ft.TextField) and not obj.__dict__.get('_xopilot_borderless'):
                modern_input(obj)
            elif isinstance(obj, ft.Dropdown):
                obj.border = {state: ft.OutlineInputBorder(border_radius=16,
                    side=ft.BorderSide(width=2 if state == ft.ControlState.FOCUSED else 1,
                        color=color('#087f8c' if state == ft.ControlState.FOCUSED else '#a8ddd7')))
                    for state in (ft.ControlState.DEFAULT, ft.ControlState.FOCUSED, ft.ControlState.DISABLED)}
                obj.bgcolor = color('#f3fffc')
                obj.color = color('#123b43')
                obj.content_padding = ft.Padding.symmetric(horizontal=16, vertical=14)
                obj.menu_style = ft.MenuStyle(bgcolor=color('#f3fffc'), padding=8,
                    side=ft.BorderSide(1, color('#a8ddd7')),
                    shape=ft.RoundedRectangleBorder(radius=16), elevation=8)
                for option in obj.options:
                    option.style = ft.ButtonStyle(color=color('#123b43'),
                        bgcolor={ft.ControlState.HOVERED: color('#ddf8f2'),
                                 ft.ControlState.FOCUSED: color('#ddf8f2')},
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10))
            originals = obj.__dict__.setdefault('_xopilot_palette', {})
            for field in fields(obj):
                if field.name.startswith('_') or field.name in {'data', 'page'}:
                    continue
                value = getattr(obj, field.name)
                if isinstance(value, str) and (value.lower() in DARK or value.lower() in reverse):
                    original = originals.get(field.name, source(value))
                    originals[field.name] = original
                    setattr(obj, field.name, color(original))
                elif isinstance(value, dict):
                    for k, v in value.items():
                        if isinstance(v, str) and (v.lower() in DARK or v.lower() in reverse):
                            value[k] = color(source(v))
                        else:
                            visit(v)
                elif is_dataclass(value) and not isinstance(value, BaseControl):
                    setattr(obj, field.name, style_value(value))
                elif is_dataclass(value) or isinstance(value, list):
                    visit(value)
    visit(root)
    return root


def set_theme(page, mode):
    global _mode
    _mode = mode if mode in THEMES else 'light'
    page.theme_mode = ft.ThemeMode.DARK if THEMES[_mode][1] else ft.ThemeMode.LIGHT
    page.bgcolor = color('#b3f2ff')
    for control in [*page.controls, *page.overlay, *page.__dict__.get('_xopilot_dialogs', [])]:
        apply_palette(control)


def modern_input(control):
    control.border = {state: ft.OutlineInputBorder(border_radius=16, side=ft.BorderSide(
        width=2 if state == ft.ControlState.FOCUSED else 1,
        color=color('#b3261e' if state == ft.ControlState.ERROR else
                    '#087f8c' if state == ft.ControlState.FOCUSED else '#a8ddd7')))
        for state in (ft.ControlState.DEFAULT, ft.ControlState.FOCUSED, ft.ControlState.ERROR, ft.ControlState.DISABLED)}
    control.filled = True
    control.bgcolor = color('#f3fffc')
    control.color = color('#123b43')
    control.cursor_color = color('#087f8c')
    control.content_padding = ft.Padding.symmetric(horizontal=16, vertical=14)
    return control


def install_theme(page, mode):
    set_theme(page, mode)
    show = page.show_dialog
    def show_dialog(dialog, *args, **kwargs):
        dialogs = page.__dict__.setdefault('_xopilot_dialogs', [])
        dialogs[:] = [item for item in dialogs if item.open]
        dialogs.append(dialog)
        return show(apply_palette(dialog), *args, **kwargs)
    page.show_dialog = show_dialog
