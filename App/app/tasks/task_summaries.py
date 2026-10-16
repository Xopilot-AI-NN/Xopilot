"""
Файл: /App/app/tasks/task_summaries.py
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Короткие понятные результаты инструментов и сохранение ленты действий.
"""
import json
import re
import shlex
from urllib.parse import urlsplit

PREFIX='[XOPILOT_ACTION_V1]\n'


def links_in(value):
    result=[]
    for url in re.findall(r'https?://[^\s<>"\]]+',str(value)):
        url=url.rstrip(').,;!?')
        try:
            parts=urlsplit(url)
            if parts.hostname and not parts.username and not parts.password and url not in result:result.append(url)
        except ValueError:pass
    return result[:3]


def describe(tool,args):
    if args.get('argv'):return shlex.join(args['argv'])
    value=next((args[k] for k in ('query','url','title','name','path','action') if args.get(k)),None)
    if value is None and args.get('id') and not re.fullmatch(r'[0-9a-f]{32}',str(args['id'])):value=args['id']
    return str(value or '')


def summarize(tool,result):
    links=[]
    if isinstance(result,dict):
        if tool=='computer_start':return 'Доступ разрешён до завершения задачи',[]
        if tool=='computer_view':return 'Экран просмотрен · элементов: '+str(len(result.get('controls',[]))),[]
        if tool=='computer_input':return 'Выполнено: '+str(result.get('target_name') or result.get('action','действие')),[]
        if tool=='launch_app':return 'Открыто: '+str(result.get('name') or result.get('package','приложение')),[]
        if 'chats' in result:
            rows=result['chats'];titles=' · '.join(str(r.get('title','Чат')) for r in rows[:2])
            links=links_in(' '.join(str(m.get('excerpt','')) for r in rows for m in r.get('matches',[])))
            return ('Найдено: '+titles if rows else 'Подходящих чатов нет'),links
        if tool=='search_web':
            rows=result.get('results',[])
            return ('Найдено: '+' · '.join(r.get('title',r['url']) for r in rows[:2]) if rows else 'Результатов нет'),[r['url'] for r in rows[:2]]
        if tool=='read_website':
            return f"{result.get('title') or 'Содержимое страницы'} · {len(result.get('text',''))} символов",links_in(result.get('url',''))
        if tool=='read_chat':
            return f"Чат «{result.get('title','')}» · {len(result.get('messages',[]))} сообщений",links_in(' '.join(m.get('content','') for m in result.get('messages',[])))
        if 'pid' in result:return (result.get('output','').strip()[:180] or 'Вывод ещё не поступил'),[]
        if result.get('saved') is True:return 'Сохранено: '+str(result.get('title') or result.get('name') or result.get('path') or 'документ'),[]
        if tool=='create_document':return 'Создан файл: '+str(result.get('name','')),[]
        if tool in {'inspect_canvas','interact_canvas'}:return str(result.get('text','')).strip()[:180] or 'Страница просмотрена',[]
    if isinstance(result,list):return f'Найдено элементов: {len(result)}',[]
    return 'Готово',[]


def decode(value):
    if not isinstance(value,str) or not value.startswith(PREFIX):return None
    try:
        record=json.loads(value[len(PREFIX):])
        if not isinstance(record,dict) or any(not isinstance(record.get(k),str) for k in ('tool','label','title','state','summary','detail','arguments_text')):return None
        if not isinstance(record.get('links',[]),list) or any(not isinstance(url,str) for url in record.get('links',[])):return None
        return record
    except (ValueError,TypeError):return None


def context(value):
    record=decode(value)
    if not record:return value
    return 'Результат инструмента (данные): '+record['label']+' · '+record['title']+'\n'+record['state']+'\n'+record['summary']+'\n'+record['detail']
