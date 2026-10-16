"""
Файл: /App/app/theme/button_colors.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Компонент button_colors интерфейса Xopilot.
"""
"""Airy Material You inspired action colours with gentle pastel gradients."""
# Subtle tonal gradients; foregrounds stay readable in both theme modes.
LIGHT = {
    'create': (('#c9e8ff', '#e0f1ff'), '#204b70', '#abcde5'),
    'navigate': (('#dcecf4', '#ebf5fa'), '#354f60', '#bdd4e0'),
    'ai': (('#dedaff', '#efeaff'), '#494477', '#c7beeb'),
    'danger': (('#f8dde1', '#fbe6e9'), '#833b48', '#e8bbc3'),
}
DARK = {
    'create': (('#82b8e2', '#a1cef0'), '#133a55', '#729dbf'),
    'navigate': (('#a1c6d7', '#b7d8e5'), '#234251', '#88aeba'),
    'ai': (('#b5aff0', '#cbc6ff'), '#363465', '#9791c9'),
    'danger': (('#e9aeb9', '#f4c7d0'), '#632b38', '#bf8995'),
}


def button_tones(role, dark=False):
    return (DARK if dark else LIGHT)[role]


def action_role(icon=None, label=''):
    key = str(getattr(icon, 'name', icon) or '').casefold()
    text = str(label or '').casefold()
    if any(word in text for word in ('удал', 'очист', 'заверш', 'останов', 'сброс')) or any(word in key for word in ('delete', 'stop', 'call_end')):
        return 'danger'
    if any(word in key for word in ('smart_toy', 'draw', 'auto_awesome', 'mic', 'graphic_eq', 'videocam')) or any(word in text for word in ('canvas', 'агент', 'модель', 'голос', 'live')):
        return 'ai'
    if any(word in key for word in ('add', 'save', 'send', 'check')) or any(word in text for word in ('созда', 'сохран', 'подтверд', 'примен', 'синхронизировать', 'войти', 'начать')):
        return 'create'
    return 'navigate'
