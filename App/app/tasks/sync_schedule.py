"""Файл: /App/app/tasks/sync_schedule.py
Разработчик: DenBroLiik
Версия: 2.0.11
Описание: Отправка завершённых изменений при открытой форме без изменения её содержимого извне.
"""


def upload_only(page):
    dialogs=[dialog for dialog in page._dialogs.controls if dialog.open]
    safe=not dialogs or getattr(dialogs[-1],'_xopilot_sync_safe',False)
    return not safe or not page._xopilot_can_sync()
