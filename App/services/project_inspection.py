"""
Файл: /App/services/project_inspection.py
Разработчик: DenBroLiik
Версия: 2.0.12
Описание: Ищу исходный код и читаю Git-изменения только внутри подключённого проекта.
"""
import fnmatch
import os
import shutil
import subprocess
from pathlib import Path
from . import project_tools
from .platforms import is_android


def search(identifier,query,*,pattern='*',offset=0,limit=40,cancelled=None):
    if not isinstance(query,str) or not query.strip() or len(query)>500:raise ValueError('Введите строку поиска до 500 символов')
    if type(offset) is not int or offset<0:raise ValueError('Неверная страница поиска')
    if not isinstance(pattern,str) or len(pattern)>200:raise ValueError('Неверная маска файлов')
    limit=max(1,min(100,int(limit)));needle=query.casefold();matches=[];seen=0;scanned=0;skipped=0
    for row in project_tools.iter_files(identifier):
        if cancelled and cancelled.is_set():
            from concurrent.futures import CancelledError
            raise CancelledError()
        name=row['path']
        if not fnmatch.fnmatchcase(name,pattern or '*'):continue
        try:
            if row['bytes']>1024*1024:skipped+=1;continue
            text=project_tools.read_file(identifier,name)['content']
            if '\0' in text:skipped+=1;continue
        except (OSError,UnicodeError,ValueError):skipped+=1;continue
        scanned+=1
        for line_number,line in enumerate(text.splitlines(),1):
            if cancelled and cancelled.is_set():
                from concurrent.futures import CancelledError
                raise CancelledError()
            pos=line.casefold().find(needle)
            if pos<0:continue
            if seen>=offset:
                if len(matches)==limit:
                    return dict(matches=matches,has_more=True,next_offset=offset+len(matches),scanned_files=scanned,skipped_files=skipped)
                start=max(0,pos-90)
                matches.append(dict(path=name,line=line_number,text=('…' if start else '')+line[start:start+300]))
            seen+=1
    return dict(matches=matches,has_more=False,next_offset=offset+len(matches),scanned_files=scanned,skipped_files=skipped)


def git(identifier,mode='status',*,path=None):
    if is_android():raise ValueError('Git-инструменты доступны на ПК; с телефона выберите режим связанного ПК')
    if mode not in ('status','diff','staged_diff'):raise ValueError('Доступны status, diff и staged_diff')
    base=project_tools.root(identifier);executable=shutil.which('git')
    if not executable:raise ValueError('Установите Git на компьютере')
    environment={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    environment['GIT_TERMINAL_PROMPT']='0';environment['GIT_OPTIONAL_LOCKS']='0'
    command=[executable,'--literal-pathspecs','--no-pager','-c','core.fsmonitor=false','-c','diff.external=','-c','core.quotePath=false']
    def run(args):
        try:result=subprocess.run([*command,*args],cwd=base,env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=12)
        except subprocess.TimeoutExpired:raise ValueError('Git не ответил за 12 секунд') from None
        if result.returncode:raise ValueError('Git не смог прочитать репозиторий. Проверьте выбранную папку и доступ к ней.')
        return result.stdout
    top=Path(os.fsdecode(run(['rev-parse','--show-toplevel'])).strip()).resolve()
    if top!=base:raise ValueError('Подключите корень Git-репозитория, чтобы не читать данные родительского проекта')
    # Даже git diff/status могут вызывать clean/process-фильтры репозитория.
    # Для инструментов чтения отключаю их вместе с fsmonitor и внешним diff.
    config=subprocess.run([*command,'config','--null','--name-only','--get-regexp',r'^filter\..*\.(clean|smudge|process|required)$'],cwd=base,env=environment,
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=12)
    if config.returncode not in (0,1):raise ValueError('Не удалось проверить Git-фильтры')
    for raw_key in config.stdout.split(b'\0'):
        if raw_key:
            key=raw_key.decode('utf-8')
            command.extend(['-c',key+('=false' if key.endswith('.required') else '=')])
    if mode=='status':
        raw=run(['status','--porcelain=v1','--branch','-z','--untracked-files=normal','--ignore-submodules=all']).decode('utf-8','replace').split('\0')
        branch=raw.pop(0).removeprefix('## ') if raw and raw[0].startswith('## ') else ''
        files=[];i=0
        while i<len(raw):
            item=raw[i];i+=1
            if not item:continue
            state=item[:2];name=item[3:]
            original=None
            if 'R' in state or 'C' in state:
                if i<len(raw):original=raw[i];i+=1
            try:
                project_tools.resolve(identifier,name)
                if original:project_tools.resolve(identifier,original)
            except (ValueError,OSError):continue
            files.append(dict(path=name,status=state,original=original))
        return dict(branch=branch,files=files[:200],truncated=len(files)>200,mode=mode)
    if not isinstance(path,str) or not path:raise ValueError('Для diff укажите путь файла из Git-статуса')
    project_tools.resolve(identifier,path)
    args=['diff','--no-ext-diff','--no-textconv','--no-color','--ignore-submodules=all']
    if mode=='staged_diff':args.append('--cached')
    raw=run([*args,'--',path]).decode('utf-8','replace')
    return dict(path=path,mode=mode,diff=raw[:60000],truncated=len(raw)>60000)
