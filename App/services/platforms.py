"""Runtime platform checks shared by Android storage and the adaptive UI."""
import platform
import sys


def is_android():
    return sys.platform == "android" or platform.system() == "Android" or hasattr(sys, "getandroidapilevel")


def is_mobile(page=None):
    value = getattr(page, "platform", None)
    return is_android() or getattr(value, "value", value) in ("android", "ios")


def compact_layout(width):
    return isinstance(width, (int, float)) and 0 < width < 600


def available_height(page):
    """Android reports the keyboard separately from the full logical page height."""
    height = getattr(page, "height", None)
    native = page.__dict__.get('_xopilot_available_height')
    if is_android() and isinstance(native, (int, float)):
        return min(height, native) if isinstance(height, (int, float)) else native
    if not isinstance(height, (int, float)) or not is_android():
        return height
    inset = getattr(getattr(getattr(page, "media", None), "view_insets", None), "bottom", 0)
    return max(0, height - inset) if isinstance(inset, (int, float)) else height


def dialog_width(page, maximum=600):
    width = getattr(page, "width", None)
    return min(maximum, max(180, width - 80)) if isinstance(width, (int, float)) else maximum


def fit_dialog(page, dialog):
    """Fit fixed-size desktop forms to the current mobile/resizable viewport."""
    import flet as ft
    from dataclasses import fields, is_dataclass
    if not isinstance(dialog, ft.AlertDialog):
        return dialog
    edge_layout = compact_layout(getattr(page, 'width', None)) and dialog.__dict__.get('_xopilot_full_width', False)
    available = max(180, page.width - 24) if edge_layout else dialog_width(page, 10000)
    height = available_height(page)
    max_height = max(120, height - (48 if edge_layout else 120)) if isinstance(height, (int, float)) else None
    seen = set()

    def visit(control):
        if id(control) in seen or not isinstance(control, ft.BaseControl): return
        seen.add(id(control))
        width = getattr(control, 'width', None)
        if isinstance(width, (int, float)):
            original = control.__dict__.setdefault('_xopilot_form_width', width)
            control.width = min(original, available)
        if control is dialog.content and max_height is not None:
            current = getattr(control, 'height', None)
            if isinstance(current, (int, float)):
                original = control.__dict__.setdefault('_xopilot_form_height', current)
                control.height = min(original, max_height)
        if is_dataclass(control):
            for field in fields(control):
                if field.name.startswith('_') or field.name in ('data', 'page'): continue
                child = getattr(control, field.name, None)
                if isinstance(child, list):
                    for item in child: visit(item)
                else: visit(child)
    visit(dialog.content)
    fit_content=dialog.__dict__.get('_xopilot_fit_content')
    if callable(fit_content):fit_content()
    if compact_layout(getattr(page, 'width', None)):
        dialog.actions_alignment = ft.MainAxisAlignment.END
        dialog.inset_padding = ft.Padding.all(12)
    return dialog
