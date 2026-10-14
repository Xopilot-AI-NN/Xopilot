"""
Файл: /App/services/project_tools.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Доступ к выбранной папке и отслеживаемые команды с подтверждением.
"""
"""Device-local project folders and reviewed process execution.

File tools are confined to a selected folder. Approved processes run with the
user's OS permissions, not in a sandbox; cwd confinement is not OS isolation.
"""
from concurrent.futures import CancelledError
from collections import deque
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from .db import get_db
from .platforms import is_android
from . import workspaces

SKIP={'.git','.ssh','.gnupg','node_modules','target','build','__pycache__','.venv','venv'}


def settings(identifier):
    raw=get_db().get_setting('project_access:'+identifier)
    return json.loads(raw) if raw else {'root':'','enabled':False}


def approval_mode(identifier):
    return 'automatic' if get_db().get_setting('project_approval:'+identifier) == 'automatic' else 'manual'


def set_approval_mode(identifier, mode):
    if identifier == workspaces.DEFAULT or identifier not in {w['id'] for w in workspaces.list_workspaces()}:
        raise ValueError('Автоматическое подтверждение доступно только для выбранного проекта')
    if mode not in {'manual','automatic'}:raise ValueError('Неизвестный режим подтверждения')
    get_db().set_setting('project_approval:'+identifier, mode)


def chat_approval_mode(chat_id):
    if not isinstance(chat_id,int) or chat_id<=0:return 'manual'
    return 'automatic' if get_db().get_setting('chat_approval:'+str(chat_id))=='automatic' else 'manual'


def set_chat_approval_mode(chat_id,mode):
    if type(chat_id) is not int or chat_id<=0:raise ValueError('Режим действий доступен в обычном чате')
    if mode not in {'manual','automatic'}:raise ValueError('Неизвестный режим подтверждения')
    get_db().set_setting('chat_approval:'+str(chat_id),mode)
    if mode=='automatic':get_db().set_setting('chat_approval_consent:'+str(chat_id),'true')


def chat_approval_consent(chat_id):
    return type(chat_id) is int and chat_id>0 and get_db().get_setting('chat_approval_consent:'+str(chat_id))=='true'


def configure(identifier,path,enabled=True):
    if identifier=='all' or identifier not in {w['id'] for w in workspaces.list_workspaces()}:
        raise ValueError('Выберите рабочее пространство')
    if not enabled:
        get_db().set_setting('project_access:'+identifier,json.dumps({'root':'','enabled':False}));return
    root=Path(path).expanduser().resolve(strict=True)
    if not root.is_dir() or root in (Path(root.anchor),Path.home().resolve()):
        raise ValueError('Выберите отдельную папку проекта, не корень диска или домашнюю папку')
    get_db().set_setting('project_access:'+identifier,json.dumps({'root':str(root),'enabled':True}))


def root(identifier):
    cfg=settings(identifier)
    if not cfg.get('enabled') or not cfg.get('root'):raise ValueError('Подключите папку в пространстве → Работа с проектом')
    value=Path(cfg['root']).resolve(strict=True)
    if not value.is_dir():raise ValueError('Папка проекта недоступна')
    return value


def resolve(identifier,name):
    base=root(identifier);relative=Path(name)
    if not name or relative.is_absolute() or '..' in relative.parts or any(p in SKIP for p in relative.parts):
        raise ValueError('Укажите относительный путь внутри проекта')
    if any(p.startswith('.') and p not in ('.github','.gitignore','.env.example') for p in relative.parts):
        raise ValueError('Скрытые личные файлы и секреты недоступны инструментам')
    candidate=base/relative
    if not candidate.resolve().is_relative_to(base):raise ValueError('Путь выходит за пределы проекта')
    current=candidate
    while current!=base:
        if current.is_symlink():raise ValueError('Символические ссылки недоступны инструментам проекта')
        current=current.parent
    return candidate


def list_files(identifier):
    base=root(identifier);result=[]
    for folder,dirs,files in os.walk(base,followlinks=False):
        dirs[:]=[d for d in sorted(dirs) if d not in SKIP and not d.startswith('.') and not (Path(folder)/d).is_symlink()]
        for name in sorted(files):
            if name.startswith('.') or (Path(folder)/name).is_symlink():continue
            path=Path(folder)/name;result.append({'path':path.relative_to(base).as_posix(),'bytes':path.stat().st_size})
    return result


def read_file(identifier,name):
    path=resolve(identifier,name)
    with path.open('rb') as source:data=source.read(1024*1024+1)
    if len(data)>1024*1024:raise ValueError('Файл слишком большой для текстового редактора (1 МБ)')
    return {'path':name,'content':data.decode('utf-8')}


def write_file(identifier,name,content,cancelled,approve):
    if not isinstance(content,str) or len(content.encode())>1024*1024:raise ValueError('Текстовый файл должен быть не больше 1 МБ')
    path=resolve(identifier,name)
    before=path.read_bytes() if path.exists() and path.stat().st_size<=1024*1024 else None
    if path.exists() and before is None:raise ValueError('Файл слишком большой для безопасного редактирования')
    request={'kind':'file','path':str(path),'cwd':str(root(identifier)),'before':before.decode('utf-8') if before is not None else '',
             'after':content,'exists':path.exists()}
    if not approve or not approve(request):raise ValueError('Пользователь не подтвердил запись файла')
    if cancelled.is_set():raise CancelledError()
    reviewed_path=path
    path=resolve(identifier,name)
    if path!=reviewed_path:raise ValueError('Папка проекта изменилась после подготовки действия')
    if (path.read_bytes() if path.exists() else None)!=before:raise ValueError('Файл изменился после подготовки. Прочитайте его заново')
    path.parent.mkdir(parents=True,exist_ok=True)
    import tempfile
    fd,temporary=tempfile.mkstemp(dir=path.parent,prefix='.xopilot-write-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as target:
            target.write(content);target.flush();os.fsync(target.fileno())
        if path.exists():os.chmod(temporary,path.stat().st_mode & 0o777)
        os.replace(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {'path':name,'saved':True,'bytes':len(content.encode())}


def start_command(identifier, argv, cancelled, approve, owner):
    if is_android():raise ValueError('Запуск системных команд доступен в приложении Linux/Windows')
    base=root(identifier)
    if not isinstance(argv,list) or not argv or not all(isinstance(a,str) and a and '\0' not in a for a in argv):
        raise ValueError('Команда должна быть массивом аргументов, например ["python", "main.py"]')
    if len(argv)>100 or sum(map(len,argv))>16000:raise ValueError('Команда слишком длинная')
    if not approve or not approve({'kind':'command','argv':argv,'cwd':str(base)}):
        raise ValueError('Пользователь не подтвердил запуск команды')
    if cancelled.is_set():raise CancelledError()
    if root(identifier)!=base:raise ValueError('Папка проекта изменилась после подготовки команды')
    from . import task_processes
    return task_processes.start(owner, identifier, argv, base)


def run_command(identifier,argv,cancelled,approve,owner=None):
    from . import task_processes
    import uuid
    owner=owner or uuid.uuid4().hex
    started=start_command(identifier,argv,cancelled,approve,owner)
    return task_processes.wait(started['id'],owner,identifier,cancelled)
