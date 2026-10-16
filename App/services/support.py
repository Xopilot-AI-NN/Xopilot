"""
Файл: /App/services/support.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Безопасная диагностика и подготовка письма поддержки без автоматической отправки.
"""
import asyncio
import base64
import json
import logging
from logging.handlers import RotatingFileHandler
import platform
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import urlencode
from .paths import app_data_dir
from .platforms import is_android

RECIPIENT='support@xopilot.by'

class SafeFormatter(logging.Formatter):
    def format(self,record):
        # Never collect free-form messages, prompts, paths, URLs, credentials or traceback locals.
        kind=record.exc_info[0].__name__ if record.exc_info else 'event'
        message=record.getMessage()
        code=re.search(r'HTTP\s+([45]\d\d)',message)
        logger=re.sub(r'[^A-Za-z0-9_.]','',record.name)[:80]
        return f'{self.formatTime(record)} {record.levelname} {logger} {kind}'+(' HTTP '+code[1] if code else '')


def install():
    root=logging.getLogger()
    if any(getattr(h,'_xopilot_safe_log',False) for h in root.handlers):return
    folder=app_data_dir()/'diagnostics';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    handler=RotatingFileHandler(folder/'events.log',maxBytes=65536,backupCount=1,encoding='utf-8')
    handler.setFormatter(SafeFormatter());handler.setLevel(logging.WARNING);handler._xopilot_safe_log=True
    root.addHandler(handler)


def collect():
    folder=app_data_dir()/'diagnostics';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=folder/'xopilot-support.zip'
    import flet as ft
    info={'app':'Xopilot','version':'2.0.8','system':platform.system(),'system_release':platform.release(),
          'python':platform.python_version(),'flet':ft.version.flet_version,
          'privacy':'No chats, databases, files, keys, account identifiers or free-form log messages included.'}
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('system.json',json.dumps(info,ensure_ascii=False,indent=2))
        # Only this application's allowlisted diagnostic file, never arbitrary logs or logcat.
        for name in ('events.log','events.log.1'):
            path=folder/name
            if path.is_file() and not path.is_symlink():archive.writestr(name,path.read_bytes()[-65536:])
    return target


def template(nickname,reason):
    return f'Ник: {nickname.strip()}\nПричина обращения: {reason.strip()}\n\nЧто ожидалось:\n\nЧто произошло:\n\nШаги воспроизведения:\n1.\n2.\n\nДиагностика Xopilot приложена. Перед отправкой можно просмотреть вложение и дополнить письмо.'


async def compose(nickname,reason):
    if not nickname.strip() or not reason.strip():raise ValueError('Укажите ник и причину обращения.')
    path=await asyncio.to_thread(collect);body=template(nickname,reason);subject='Xopilot — обращение в поддержку'
    if is_android():
        from .mobile_runtime import call_async
        await call_async('supportEmail',{'archive':base64.b64encode(path.read_bytes()).decode(),
                                        'subject':subject,'body':body})
        return path
    if shutil.which('xdg-email'):
        process=await asyncio.create_subprocess_exec('xdg-email','--utf8','--attach',str(path),'--subject',subject,'--body',body,RECIPIENT,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if await process.wait()==0:return path
    import flet as ft
    url='mailto:'+RECIPIENT+'?'+urlencode({'subject':subject,'body':body+'\n\nДобавьте вложение вручную: '+str(path)})
    if not await ft.UrlLauncher().launch_url(url):raise RuntimeError('Почтовый клиент недоступен. Диагностика сохранена: '+str(path))
    return path


def open_support(page):
    import flet as ft
    try:
        from ..app.palette import color,modern_input
        from ..app.buttons.actions import action_button
    except ImportError:
        from app.palette import color,modern_input
        from app.buttons.actions import action_button
    name=modern_input(ft.TextField(label='Ваш ник',max_length=80))
    reason=modern_input(ft.TextField(label='Причина обращения',multiline=True,min_lines=2,max_lines=4,max_length=2000))
    feedback=ft.Text(size=12,color=color('#47747a'));send=action_button('Подготовить письмо',icon=ft.Icons.MAIL_OUTLINE)
    async def prepare(_):
        send.disabled=True;feedback.value='Готовим диагностику…';page.update()
        try:
            path=await compose(name.value or '',reason.value or '')
            feedback.value='Письмо открыто. Проверьте текст и вложение перед отправкой. Диагностика: '+str(path)
        except Exception as exc:feedback.value=str(exc)
        finally:send.disabled=False;page.update()
    send.on_click=prepare
    page.show_dialog(ft.AlertDialog(title=ft.Text('Поддержка Xopilot'),content=ft.Column(width=400,tight=True,spacing=12,
        controls=[ft.Text('Получатель: '+RECIPIENT),name,reason,
                  ft.Text('Во вложении — версия, система и технические коды ошибок. Переписка, ключи и материалы не собираются.',size=12),feedback]),
        actions=[ft.TextButton(content='Назад',on_click=lambda _:page.pop_dialog()),send]))
