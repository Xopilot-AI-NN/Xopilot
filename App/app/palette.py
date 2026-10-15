"""The existing aqua palette with a matching dark appearance."""
from dataclasses import fields, is_dataclass, replace
from weakref import WeakValueDictionary
import flet as ft
from flet.controls.base_control import BaseControl

DARK = {
    '#fefefe': '#3b6266', '#b3f2ff': '#10262e', '#d9ffe6': '#152f31', '#eafffa': '#17343a',
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

def is_dark_theme():
    return THEMES[_mode][1]


def outline_color():
    return color('#fefefe')


def menu_tones():
    """Raised neutral surfaces let the pastel selection stand out."""
    return (('#253344', '#e5edf8', '#506477') if is_dark_theme() else
            ('#f7faff', '#203950', '#c5d6e8'))

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
                    '#fefefe': border if dark else '#ffffff', '#b9eee4': border, '#b6e5df': border, '#a8ddd7': border,
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
        role = getattr(obj, '__dict__', {}).get('_xopilot_button_role')
        if role:
            from .buttons.brand import style_brand_button
            style_brand_button(obj, role)
            return
        if getattr(obj, '__dict__', {}).get('_xopilot_fixed_colors'):
            if getattr(obj, 'border', None):
                obj.border = style_value(obj.border)
            return
        if id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, list):
            for value in obj:
                visit(value)
        elif is_dataclass(obj):
            if isinstance(obj, (ft.FilledButton, ft.Button, ft.OutlinedButton, ft.TextButton)):
                from .button_colors import action_role, button_tones
                label = obj.content if isinstance(obj.content, str) else getattr(obj.content, 'value', '')
                tones, ink, outline = button_tones(action_role(obj.icon, label), is_dark_theme())
                style = obj.style or ft.ButtonStyle()
                changes = {'shape': ft.RoundedRectangleBorder(radius=20), 'elevation': 0,
                           'overlay_color': ft.Colors.with_opacity(.10, ink)}
                close_action = isinstance(obj, ft.TextButton) and str(label).strip().casefold() == 'закрыть'
                if isinstance(obj, (ft.FilledButton, ft.Button)) or close_action:
                    changes.update(bgcolor={ft.ControlState.DEFAULT: tones[0], ft.ControlState.HOVERED: tones[1], ft.ControlState.DISABLED: color('#dff8f3')},
                                   color={ft.ControlState.DEFAULT: ink, ft.ControlState.DISABLED: color('#47747a')})
                    if close_action:
                        changes.update(side=ft.BorderSide(1, outline),
                                       padding=ft.Padding.symmetric(horizontal=20, vertical=12))
                else:
                    # Tonal ink belongs on its light fill. Transparent actions
                    # need a light foreground on dark dialog surfaces.
                    changes['color'] = tones[1] if is_dark_theme() else ink
                    if isinstance(obj, ft.OutlinedButton):
                        changes['side'] = ft.BorderSide(1, outline)
                obj.style = replace(style, **changes)
            if isinstance(obj, ft.TextField) and not obj.__dict__.get('_xopilot_borderless'):
                modern_input(obj)
            elif isinstance(obj, ft.Markdown):
                # Syntax tokens inherit the chat text colour. A light Github
                # background with dark-theme foreground makes code unreadable.
                obj.code_theme = ft.MarkdownCodeTheme.ATOM_ONE_DARK if THEMES[_mode][1] else ft.MarkdownCodeTheme.GITHUB
            elif isinstance(obj, ft.Dropdown):
                from .button_colors import button_tones
                surface, text, edge = menu_tones()
                tones, ink, focus = button_tones('ai', is_dark_theme())
                obj.border = {state: ft.OutlineInputBorder(border_radius=16,
                    side=ft.BorderSide(width=2 if state == ft.ControlState.FOCUSED else 1,
                        color=focus if state == ft.ControlState.FOCUSED else edge))
                    for state in (ft.ControlState.DEFAULT, ft.ControlState.FOCUSED, ft.ControlState.DISABLED)}
                obj.bgcolor = surface
                obj.fill_color = color('#f3fffc')
                obj.filled = True
                obj.color = text
                obj.text_style = ft.TextStyle(color=text, size=obj.text_size or 13)
                obj.label_style = ft.TextStyle(color=text)
                obj.trailing_icon = ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
                obj.selected_trailing_icon = ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
                obj.content_padding = ft.Padding.symmetric(horizontal=16, vertical=14)
                obj.menu_style = ft.MenuStyle(bgcolor=surface, padding=8,
                    side=ft.BorderSide(1, edge), shadow_color='#30000000',
                    shape=ft.RoundedRectangleBorder(radius=20), elevation=6)
                for option in obj.options:
                    option.style = ft.ButtonStyle(color={ft.ControlState.DEFAULT: text,
                        ft.ControlState.HOVERED: ink, ft.ControlState.FOCUSED: ink,
                        ft.ControlState.SELECTED: ink, ft.ControlState.DISABLED: color('#47747a')},
                        bgcolor={ft.ControlState.HOVERED: tones[1],
                                 ft.ControlState.FOCUSED: tones[1], ft.ControlState.SELECTED: tones[0]},
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(horizontal=14, vertical=10))
            elif isinstance(obj, ft.PopupMenuButton):
                surface, text, edge = menu_tones()
                obj.bgcolor = surface
                obj.shape = ft.RoundedRectangleBorder(radius=20, side=ft.BorderSide(1, edge))
                obj.menu_padding = ft.Padding.all(6)
                obj.elevation = 6
                obj.shadow_color = '#30000000'
                obj.popup_animation_style = ft.AnimationStyle(duration=160, reverse_duration=120)
                for item in obj.items:
                    if isinstance(item, ft.PopupMenuItem):
                        item.padding = ft.Padding.symmetric(horizontal=14, vertical=10)
                        item.label_text_style = ft.TextStyle(color=text, size=14)
                        if isinstance(item.content, ft.Text):
                            from .button_colors import action_role
                            item.content.color = (color('#c94b4b') if action_role(item.icon, item.content.value) == 'danger' else text)
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
    for control in [*page.controls, *page.overlay, *open_dialogs(page)]:
        apply_palette(control)


def open_dialogs(page):
    registry = page.__dict__.get('_xopilot_dialogs')
    return tuple(dialog for dialog in registry.values() if dialog.open) if registry is not None else ()


def modern_input(control):
    control.border = {state: ft.OutlineInputBorder(border_radius=16, side=ft.BorderSide(
        width=2 if state == ft.ControlState.FOCUSED else 1,
        color=color('#b3261e' if state == ft.ControlState.ERROR else
                    '#087f8c' if state == ft.ControlState.FOCUSED else '#a8ddd7')))
        for state in (ft.ControlState.DEFAULT, ft.ControlState.FOCUSED, ft.ControlState.ERROR, ft.ControlState.DISABLED)}
    control.filled = True
    control.bgcolor = control.fill_color = color('#f3fffc')
    control.color = color('#123b43')
    control.cursor_color = color('#087f8c')
    control.content_padding = ft.Padding.symmetric(horizontal=16, vertical=14)
    return control


def install_theme(page, mode):
    set_theme(page, mode)
    show = page.show_dialog
    def show_dialog(dialog, *args, **kwargs):
        # Flet owns the dismissal animation. Theme/resize tracking must not
        # retain the last closed editor, its image bytes or callback closures.
        dialogs = page.__dict__.setdefault('_xopilot_dialogs', WeakValueDictionary())
        dialogs[id(dialog)] = dialog
        getattr(page, '_xopilot_memory_activity', lambda: None)()
        try:
            from ..services.platforms import fit_dialog
        except ImportError:
            from services.platforms import fit_dialog
        return show(apply_palette(fit_dialog(page, dialog)), *args, **kwargs)
    page.show_dialog = show_dialog
