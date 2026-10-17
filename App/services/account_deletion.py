"""
Файл: /App/services/account_deletion.py
Разработчик: DenBroLiik
Версия: 2.0.10
Описание: Удаление своего облачного аккаунта и очистка закрытых данных при перезапуске.
"""
import shutil
from .paths import app_data_dir

MARKER = '.erase-personal-data'


def schedule_local_erasure():
    root = app_data_dir()
    if root.name != 'Xopilot' or root.is_symlink():
        raise ValueError('Не удалось безопасно определить каталог данных')
    root.mkdir(parents=True, exist_ok=True)
    (root / MARKER).write_text('erase on next launch', encoding='utf-8')


def perform_pending_erasure():
    """Run before runtime/database startup, when no writers can recreate personal data."""
    root = app_data_dir()
    if root.name != 'Xopilot' or root.is_symlink():
        raise ValueError('Небезопасный каталог данных')
    if not (root / MARKER).is_file():
        return False
    # Keep the marker until every other entry is gone, allowing a failed wipe to resume.
    for item in root.iterdir():
        if item.name == MARKER:
            continue
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()
    (root / MARKER).unlink()
    return True


def delete_account(confirmation, password=''):
    from . import cloud_account as cloud
    account = cloud.state()
    if not account or confirmation.strip() != account['email']:
        raise ValueError('Введите почту своего аккаунта без изменений')
    result = cloud.request('/me', method='DELETE', body={
        'confirmation': confirmation.strip(), 'password': password})
    if result.get('deleted') is not True or result.get('account_id') != account['account_id']:
        raise ValueError('Сервер не подтвердил удаление аккаунта')
    # Do not wipe if the server failed. No password or deletion token is persisted.
    schedule_local_erasure()
    cloud._save(None)
    return result
