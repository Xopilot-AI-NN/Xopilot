"""
Файл: /App/services/device_actions.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Открытие приложений Android и команды медиаплеера после
          подтверждения пользователя; без доступа ИИ к shell или произвольным Intent.
"""
from concurrent.futures import CancelledError
from .platforms import is_android
from . import mobile_runtime

MEDIA = {'next', 'previous', 'pause', 'play', 'play_pause', 'stop'}


def apps():
    if not is_android():
        from . import desktop_control
        return desktop_control.apps()
    return mobile_runtime.call('listApps')


def perform(action, arguments, cancelled, approve):
    if not is_android():
        if action=='launch_app':
            from . import desktop_control
            return desktop_control.launch(str(arguments.get('package','')),cancelled,approve)
        raise ValueError('Управление медиаплеером здесь доступно на Android')
    if action == 'launch_app':
        package = str(arguments.get('package', ''))
        entry = next((item for item in apps() if item['package'] == package), None)
        if not entry: raise ValueError('Выберите package из list_apps; приложение недоступно')
        request = {'kind': 'device', 'title': 'Открыть приложение «'+entry['name']+'»?',
                   'action': action, 'arguments': {'package': package}}
        method, payload = 'launchApp', {'package': package}
    elif action == 'control_media':
        command = arguments.get('action')
        if command not in MEDIA: raise ValueError('Действия медиаплеера: '+', '.join(sorted(MEDIA)))
        request = {'kind': 'device', 'title': 'Управлять текущим медиаплеером?',
                   'action': action, 'arguments': {'action': command}}
        method, payload = 'controlMedia', {'action': command}
    else: raise ValueError('Неизвестное действие устройства')
    if not approve or not approve(request): raise ValueError('Действие устройства не подтверждено')
    if cancelled.is_set(): raise CancelledError()
    return mobile_runtime.call(method, payload)
