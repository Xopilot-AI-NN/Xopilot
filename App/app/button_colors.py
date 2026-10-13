"""Action colours derived from the teal, blue and violet Xopilot logo."""
COLOURS = {
    'create': ('#007c69', '#008473'),
    'navigate': ('#126b9e', '#2378ac'),
    'ai': ('#6550ae', '#7661ba'),
    'danger': ('#b33b51', '#c14b60'),
}


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
